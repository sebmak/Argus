import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Request, Header, status
from pydantic import BaseModel
from ..core.face_engine import face_engine
from ..core.webhook_parser import parse_protect_webhook
from ..db.database import (
    get_person_by_name,
    create_person,
    add_face_sample,
    get_person_by_id,
    record_detection
)
from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/protect", tags=["UniFi Protect Webhook"])

# Rules for WebhookResponse class:
# 1. Variables and data schema properties must be declared at the top of the class.
# 2. Encapsulates UniFi Protect webhook ingestion confirmation telemetry including household classification.
class WebhookResponse(BaseModel):
    status: str
    message: str
    person_id: str
    person_name: str
    total_samples: int
    is_household: bool = True
    camera_id: str = ""
    event_id: str = ""

@router.post("/webhook", response_model=WebhookResponse)
@router.put("/webhook", response_model=WebhookResponse)
async def ingest_protect_webhook(
    request: Request,
    x_webhook_secret: Optional[str] = Header(None, alias="X-Webhook-Secret")
):
    """
    UniFi Protect / Home Assistant Training Ingestion Webhook.
    Receives automated face detection alerts from UniFi Protect / Home Assistant,
    extracts the face embedding, and automatically updates the person's learned model.
    """
    # 1. Optional Secret Key Check
    if settings.WEBHOOK_SECRET and x_webhook_secret != settings.WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Webhook-Secret header"
        )

    # 2. Extract JSON payload
    try:
        raw_body = await request.json()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON body: {str(e)}"
        )

    # 3. Parse UniFi Protect / Home Assistant Payload
    parsed = parse_protect_webhook(raw_body)
    if not parsed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unable to parse face detection data. Ensure 'thumbnail' or 'snapshot' and a known person name are present."
        )

    # 4. Decode Snapshot Image
    try:
        img_bgr = face_engine.decode_image(parsed.image_base64)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to decode snapshot base64 image: {str(e)}"
        )

    # 5. Extract Face Embedding
    detections = face_engine.detect_and_embed(img_bgr)
    if not detections:
        logger.warning("No face detected in snapshot for %s", parsed.person_name)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No recognizable face could be extracted from snapshot for '{parsed.person_name}'."
        )

    # Pick the most prominent / highest confidence face
    primary_face = max(detections, key=lambda d: d.confidence)

    # 6. Locate or Create Person Entity
    existing_person = get_person_by_name(parsed.person_name)
    if existing_person:
        person_id = existing_person["id"]
        person_name = existing_person["name"]
    else:
        new_person = create_person(
            name=parsed.person_name,
            notes=f"Auto-created from UniFi Protect camera ({parsed.camera_id})"
        )
        person_id = new_person["id"]
        person_name = new_person["name"]

    # 7. Add Face Sample (increments and updates embedding representation)
    sample_id = add_face_sample(
        person_id=person_id,
        embedding=primary_face.embedding,
        thumbnail_path=primary_face.thumbnail_filename,
        source="unifi_protect",
        camera_id=parsed.camera_id,
        event_id=parsed.event_id
    )

    # 8. Log detection history event
    record_detection(
        thumbnail_path=primary_face.thumbnail_filename,
        bbox=primary_face.bbox,
        camera_id=parsed.camera_id,
        matched_person_id=person_id,
        matched_name=person_name,
        similarity=1.0,
        status="matched",
        confidence=primary_face.confidence
    )

    # Retrieve updated person sample count
    updated_person = get_person_by_id(person_id)
    total_samples = updated_person["sample_count"] if updated_person else 1

    logger.info(
        "Successfully ingested UniFi Protect face sample for '%s' (camera: %s, sample: %s, total: %d)",
        person_name, parsed.camera_id, sample_id, total_samples
    )

    return WebhookResponse(
        status="success",
        message=f"Model successfully updated with new face sample for {person_name}.",
        person_id=person_id,
        person_name=person_name,
        total_samples=total_samples,
        camera_id=parsed.camera_id,
        event_id=parsed.event_id
    )
