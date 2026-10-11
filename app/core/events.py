import json
import logging
import time
from typing import Dict, Any, Optional
import httpx
from ..config import settings
from ..db.database import record_event_log

logger = logging.getLogger(__name__)

# MQTT Client singleton & connection state
_mqtt_client = None
_mqtt_connected = False
_mqtt_last_error = None

def get_mqtt_status() -> Dict[str, Any]:
    """Returns current MQTT client connection telemetry and configuration."""
    return {
        "enabled": settings.MQTT_ENABLED,
        "host": settings.MQTT_HOST,
        "port": settings.MQTT_PORT,
        "topic": settings.MQTT_TOPIC,
        "user": settings.MQTT_USER,
        "connected": _mqtt_connected,
        "last_error": _mqtt_last_error,
        "only_known_faces": settings.MQTT_ONLY_KNOWN_FACES
    }

def get_mqtt_client():
    global _mqtt_client, _mqtt_connected, _mqtt_last_error
    if not settings.MQTT_ENABLED or not settings.MQTT_HOST:
        return None

    if _mqtt_client is not None:
        return _mqtt_client

    try:
        import paho.mqtt.client as mqtt
        
        # Paho v2 vs v1 compatibility
        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="facedetection-service")
        except AttributeError:
            client = mqtt.Client(client_id="facedetection-service")

        # Set credentials if username is provided
        if settings.MQTT_USER:
            client.username_pw_set(settings.MQTT_USER, settings.MQTT_PASSWORD or "")
        elif settings.MQTT_PASSWORD:
            client.username_pw_set("", settings.MQTT_PASSWORD)

        def on_connect(c, userdata, flags, rc, properties=None):
            global _mqtt_connected, _mqtt_last_error
            rc_code = getattr(rc, "value", rc)
            if rc_code == 0:
                _mqtt_connected = True
                _mqtt_last_error = None
                logger.info("Connected to MQTT Broker at %s:%d", settings.MQTT_HOST, settings.MQTT_PORT)
                record_event_log(
                    level="success",
                    category="mqtt",
                    event_type="mqtt_connected",
                    message=f"Connected to MQTT broker at {settings.MQTT_HOST}:{settings.MQTT_PORT}",
                    details={"host": settings.MQTT_HOST, "port": settings.MQTT_PORT, "topic": settings.MQTT_TOPIC}
                )
            elif rc_code in (4, 5, 134, 135):
                _mqtt_connected = False
                _mqtt_last_error = "Not authorized (invalid or missing username/password)"
                logger.warning(
                    "MQTT Broker rejected connection: Not Authorized (rc=%s). "
                    "Mosquitto requires credentials. Please enter MQTT Username and Password in Settings.",
                    rc_code
                )
                record_event_log(
                    level="error",
                    category="mqtt",
                    event_type="mqtt_error",
                    message=f"MQTT broker rejected connection: Not Authorized (rc={rc_code})",
                    details={"host": settings.MQTT_HOST, "port": settings.MQTT_PORT, "rc": rc_code, "error": _mqtt_last_error}
                )
            else:
                _mqtt_connected = False
                _mqtt_last_error = f"Connection failed (code {rc_code})"
                logger.warning("Failed to connect to MQTT Broker, return code: %s", rc_code)
                record_event_log(
                    level="error",
                    category="mqtt",
                    event_type="mqtt_error",
                    message=f"Failed to connect to MQTT broker: return code {rc_code}",
                    details={"host": settings.MQTT_HOST, "port": settings.MQTT_PORT, "rc": rc_code}
                )

        def on_disconnect(c, userdata, flags_or_rc, *args):
            global _mqtt_connected
            _mqtt_connected = False
            logger.debug("MQTT client disconnected from broker.")
            record_event_log(
                level="warning",
                category="mqtt",
                event_type="mqtt_disconnected",
                message=f"MQTT client disconnected from broker at {settings.MQTT_HOST}:{settings.MQTT_PORT}",
                details={"host": settings.MQTT_HOST, "port": settings.MQTT_PORT}
            )

        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
        client.connect_async(settings.MQTT_HOST, settings.MQTT_PORT, keepalive=60)
        client.loop_start()
        _mqtt_client = client
        return _mqtt_client
    except Exception as e:
        _mqtt_connected = False
        _mqtt_last_error = str(e)
        logger.warning("Could not initialize MQTT client: %s", e)
        record_event_log(
            level="error",
            category="mqtt",
            event_type="mqtt_error",
            message=f"Could not initialize MQTT client: {e}",
            details={"host": settings.MQTT_HOST, "port": settings.MQTT_PORT, "error": str(e)}
        )
        return None

def reset_mqtt_client():
    """Stops and resets singleton MQTT client so updated credentials or host take effect."""
    global _mqtt_client, _mqtt_connected, _mqtt_last_error
    if _mqtt_client is not None:
        try:
            _mqtt_client.loop_stop()
            _mqtt_client.disconnect()
        except Exception as e:
            logger.debug("Error disconnecting MQTT client: %s", e)
        _mqtt_client = None
    _mqtt_connected = False
    _mqtt_last_error = None

def dispatch_detection_event(event_data: Dict[str, Any]):
    """
    Dispatches detection events to configured outgoing webhook and MQTT broker.
    Runs synchronously or in worker thread.
    """
    payload_json = json.dumps(event_data)
    is_known = bool(event_data.get("match", False))
    person_name = event_data.get("person_name", "Unknown")

    # 1. Dispatch Webhook if configured
    webhook_url = settings.RTSP_WEBHOOK_URL
    if webhook_url:
        if not is_known and (settings.WEBHOOK_ONLY_KNOWN_FACES or not settings.NOTIFY_ON_UNKNOWN):
            logger.debug(
                "Suppressing outgoing webhook for '%s': only known faces allowed (WEBHOOK_ONLY_KNOWN_FACES=%s, NOTIFY_ON_UNKNOWN=%s)",
                person_name, settings.WEBHOOK_ONLY_KNOWN_FACES, settings.NOTIFY_ON_UNKNOWN
            )
        else:
            try:
                with httpx.Client(timeout=4.0) as client:
                    res = client.post(webhook_url, json=event_data)
                    logger.debug("Dispatched webhook to %s (HTTP %d)", webhook_url, res.status_code)
                    record_event_log(
                        level="info",
                        category="webhook",
                        event_type="webhook_broadcast",
                        message=f"Dispatched webhook for '{person_name}' to {webhook_url} (HTTP {res.status_code})",
                        details={
                            "url": webhook_url,
                            "status_code": res.status_code,
                            "person_name": person_name,
                            "camera": event_data.get("camera"),
                            "is_household": event_data.get("is_household")
                        }
                    )
            except Exception as e:
                logger.warning("Failed to post detection webhook to %s: %s", webhook_url, e)
                record_event_log(
                    level="error",
                    category="webhook",
                    event_type="webhook_error",
                    message=f"Failed to post detection webhook to {webhook_url}: {e}",
                    details={"url": webhook_url, "person_name": person_name, "error": str(e)}
                )

    # 2. Dispatch to MQTT if enabled
    if settings.MQTT_ENABLED:
        if not is_known and (settings.MQTT_ONLY_KNOWN_FACES or settings.WEBHOOK_ONLY_KNOWN_FACES or not settings.NOTIFY_ON_UNKNOWN):
            logger.debug(
                "Suppressing MQTT publication for '%s': only known faces allowed (MQTT_ONLY_KNOWN_FACES=%s, NOTIFY_ON_UNKNOWN=%s)",
                person_name, settings.MQTT_ONLY_KNOWN_FACES, settings.NOTIFY_ON_UNKNOWN
            )
        else:
            try:
                client = get_mqtt_client()
                if client:
                    topic = settings.MQTT_TOPIC
                    client.publish(topic, payload_json, qos=0)
                    # Also publish to entity-specific topic if matched
                    if person_name and person_name.lower() != "unknown":
                        sub_topic = f"{topic}/{person_name.lower().replace(' ', '_')}"
                        client.publish(sub_topic, payload_json, qos=0)
                    logger.debug("Published detection to MQTT topic: %s", topic)
                    record_event_log(
                        level="info",
                        category="mqtt",
                        event_type="mqtt_broadcast",
                        message=f"Published detection for '{person_name}' to MQTT topic '{topic}'",
                        details={
                            "topic": topic,
                            "person_name": person_name,
                            "camera": event_data.get("camera"),
                            "is_household": event_data.get("is_household")
                        }
                    )
            except Exception as e:
                logger.warning("Failed to publish detection to MQTT: %s", e)
                record_event_log(
                    level="error",
                    category="mqtt",
                    event_type="mqtt_error",
                    message=f"Failed to publish detection to MQTT broker: {e}",
                    details={"topic": settings.MQTT_TOPIC, "person_name": person_name, "error": str(e)}
                )

