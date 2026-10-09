import json
import logging
import time
from typing import Dict, Any, Optional
import httpx
from ..config import settings

logger = logging.getLogger(__name__)

# MQTT Client singleton
_mqtt_client = None

def get_mqtt_client():
    global _mqtt_client
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

        if settings.MQTT_USER and settings.MQTT_PASSWORD:
            client.username_pw_set(settings.MQTT_USER, settings.MQTT_PASSWORD)

        def on_connect(c, userdata, flags, rc, properties=None):
            if rc == 0:
                logger.info("Connected to MQTT Broker at %s:%d", settings.MQTT_HOST, settings.MQTT_PORT)
            else:
                logger.warning("Failed to connect to MQTT Broker, return code: %d", rc)

        client.on_connect = on_connect
        client.connect_async(settings.MQTT_HOST, settings.MQTT_PORT, keepalive=60)
        client.loop_start()
        _mqtt_client = client
        return _mqtt_client
    except Exception as e:
        logger.warning("Could not initialize MQTT client: %s", e)
        return None

def reset_mqtt_client():
    """Stops and resets singleton MQTT client so updated credentials or host take effect."""
    global _mqtt_client
    if _mqtt_client is not None:
        try:
            _mqtt_client.loop_stop()
            _mqtt_client.disconnect()
        except Exception as e:
            logger.debug("Error disconnecting MQTT client: %s", e)
        _mqtt_client = None

def dispatch_detection_event(event_data: Dict[str, Any]):
    """
    Dispatches detection events to configured outgoing webhook and MQTT broker.
    Runs synchronously or in worker thread.
    """
    payload_json = json.dumps(event_data)

    # 1. Dispatch Webhook if configured
    webhook_url = settings.RTSP_WEBHOOK_URL
    if webhook_url:
        try:
            with httpx.Client(timeout=4.0) as client:
                res = client.post(webhook_url, json=event_data)
                logger.debug("Dispatched webhook to %s (HTTP %d)", webhook_url, res.status_code)
        except Exception as e:
            logger.warning("Failed to post detection webhook to %s: %s", webhook_url, e)

    # 2. Dispatch to MQTT if enabled
    if settings.MQTT_ENABLED:
        try:
            client = get_mqtt_client()
            if client:
                topic = settings.MQTT_TOPIC
                client.publish(topic, payload_json, qos=0)
                # Also publish to entity-specific topic if matched
                person_name = event_data.get("person_name")
                if person_name and person_name.lower() != "unknown":
                    sub_topic = f"{topic}/{person_name.lower().replace(' ', '_')}"
                    client.publish(sub_topic, payload_json, qos=0)
                logger.debug("Published detection to MQTT topic: %s", topic)
        except Exception as e:
            logger.warning("Failed to publish detection to MQTT: %s", e)
