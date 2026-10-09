import logging
from typing import Dict, Any, Optional, List
try:
    from pydantic import BaseModel, Field
except ImportError:
    class BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
        def dict(self, **kwargs):
            return self.__dict__
    def Field(default=None, default_factory=None, **kwargs):
        if default_factory is not None:
            return default_factory()
        return default

logger = logging.getLogger(__name__)

# ==============================================================================
# Rules for WebhookPayload:
# 1. Variables and data model properties must be declared at the top of the class.
# 2. Encapsulates normalized UniFi Protect and Home Assistant detection webhook events.
# ==============================================================================
class WebhookPayload(BaseModel):
    person_name: str = ""
    image_base64: str = ""
    camera_id: str = ""
    event_id: str = ""
    confidence: float = 0.0
    source_type: str = "unifi_protect"
    raw_metadata: Dict[str, Any] = Field(default_factory=dict)

def parse_protect_webhook(data: Any) -> Optional[WebhookPayload]:
    """
    Parses incoming webhook payload from UniFi Protect / Home Assistant.
    Supports:
    1. Nested Home Assistant automation trigger dictionary (`trigger.json...`)
    2. Direct Home Assistant webhook body (`{ alarm: ..., triggers: [...], thumbnail: ... }`)
    3. Flat standardized JSON (`{ person_name: ..., snapshot: ... }`)
    """
    if not isinstance(data, dict):
        logger.warning("Webhook payload is not a dictionary: %s", type(data))
        return None

    # Check if payload is wrapped inside Home Assistant `trigger` or `json`
    payload = data
    if "trigger" in payload and isinstance(payload["trigger"], dict):
        payload = payload["trigger"]
    if "json" in payload and isinstance(payload["json"], dict):
        payload = payload["json"]

    # 1. Extract Base64 Image Thumbnail / Snapshot
    image_base64 = ""
    for img_key in ["thumbnail", "snapshot", "image", "picture", "photo"]:
        if img_key in payload and isinstance(payload[img_key], str) and len(payload[img_key]) > 20:
            image_base64 = payload[img_key]
            break
            
    # Check if thumbnail is nested in triggers or sourceEvent
    if not image_base64 and "triggers" in payload and isinstance(payload["triggers"], list) and len(payload["triggers"]) > 0:
        first_trig = payload["triggers"][0]
        if isinstance(first_trig, dict):
            for img_key in ["thumbnail", "snapshot", "image"]:
                if img_key in first_trig and isinstance(first_trig[img_key], str):
                    image_base64 = first_trig[img_key]
                    break

    if not image_base64:
        logger.warning("No image thumbnail or snapshot found in webhook payload")
        return None

    # 2. Extract Person Name
    person_name = ""
    
    # Try Home Assistant triggers structure first
    triggers = payload.get("triggers", [])
    if isinstance(triggers, list) and len(triggers) > 0 and isinstance(triggers[0], dict):
        trig = triggers[0]
        # value field (e.g. "Sebastian")
        if trig.get("value") and isinstance(trig["value"], str):
            person_name = trig["value"]
        # group.name field
        elif isinstance(trig.get("group"), dict) and trig["group"].get("name"):
            person_name = str(trig["group"]["name"])
            
    # Try top-level keys if person_name not yet resolved
    if not person_name:
        for name_key in ["person_name", "person", "name", "identity", "label", "face"]:
            if name_key in payload and isinstance(payload[name_key], str) and payload[name_key].strip():
                person_name = payload[name_key].strip()
                break

    if not person_name or person_name.lower() in ["unknown", "unrecognized", "none", "null"]:
        logger.warning("No known person name found in webhook payload")
        return None

    # 3. Extract Camera, Event ID, and Score
    camera_id = ""
    event_id = ""
    confidence = 0.0

    if isinstance(triggers, list) and len(triggers) > 0 and isinstance(triggers[0], dict):
        trig = triggers[0]
        event_id = str(trig.get("eventId", ""))
        source_event = trig.get("sourceEvent", {})
        if isinstance(source_event, dict):
            camera_id = str(source_event.get("camera", source_event.get("device", "")))
            score = source_event.get("score", 0)
            try:
                score_float = float(score)
                confidence = score_float / 100.0 if score_float > 1.0 else score_float
            except (ValueError, TypeError):
                confidence = 0.0
    else:
        camera_id = str(payload.get("camera_id", payload.get("camera", payload.get("device", ""))))
        event_id = str(payload.get("event_id", payload.get("eventId", payload.get("id", ""))))
        score = payload.get("confidence", payload.get("score", 0))
        try:
            score_float = float(score)
            confidence = score_float / 100.0 if score_float > 1.0 else score_float
        except (ValueError, TypeError):
            confidence = 0.0

    return WebhookPayload(
        person_name=person_name.strip(),
        image_base64=image_base64,
        camera_id=camera_id,
        event_id=event_id,
        confidence=confidence,
        raw_metadata=payload
    )
