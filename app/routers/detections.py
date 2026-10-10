import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
import cv2
from ..core.face_engine import face_engine
from ..db.database import (
    get_unrecognized_detections,
    assign_detection_to_person,
    dismiss_detection,
    purge_low_confidence_detections,
    deduplicate_unrecognized_detections,
    get_person_by_id,
    get_person_by_name,
    create_person,
    add_face_sample,
    get_db
)
from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/detections", tags=["Detections Queue"])

# ==============================================================================
# Rules for AssignDetectionRequest:
# 1. Variables and data schema properties must be declared at the top of the class.
# 2. Encapsulates request parameters for assigning detections to existing or new members.
# 3. Supports classifying newly created persons as household or non-household members.
# ==============================================================================
class AssignDetectionRequest(BaseModel):
    person_id: Optional[str] = Field(None, description="ID of existing person to assign to")
    new_person_name: Optional[str] = Field(None, description="Name for newly created person if not existing")
    is_household: Optional[bool] = Field(True, description="Classification for newly created person (True=household, False=non-household/visitor)")

@router.get("/unrecognized")
async def list_unrecognized_detections(limit: int = 50, offset: int = 0):
    """
    Retrieve unrecognized face detections for the Web UI Review Inbox.
    Allows household admin to tag unknown faces to known members or create new profiles.
    """
    detections = get_unrecognized_detections(limit=limit, offset=offset)
    for det in detections:
        det["thumbnail_url"] = f"/api/v1/thumbnails/{det['thumbnail_path']}"
    return {
        "count": len(detections),
        "detections": detections
    }

@router.post("/{detection_id}/assign")
async def assign_detection(detection_id: str, payload: AssignDetectionRequest):
    """
    Assign an unrecognized face detection to an existing member or create a new member.
    Automatically extracts and trains the model with this newly verified face crop.
    """
    # 1. Fetch detection details from DB
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM detections WHERE id = ?", (detection_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detection not found")
        detection = dict(row)

    # 2. Resolve Person (Existing or Create New)
    target_person_id = payload.person_id
    if not target_person_id and payload.new_person_name:
        name_clean = payload.new_person_name.strip()
        existing = get_person_by_name(name_clean)
        if existing:
            target_person_id = existing["id"]
        else:
            is_hh = payload.is_household if payload.is_household is not None else True
            new_p = create_person(
                name_clean,
                notes="Created from unrecognized review inbox",
                is_household=is_hh
            )
            target_person_id = new_p["id"]

    if not target_person_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'person_id' or 'new_person_name' must be provided"
        )

    person = get_person_by_id(target_person_id)
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target person not found")

    # 3. Read thumbnail from disk and generate embedding for training
    thumb_path = settings.thumbnails_path / detection["thumbnail_path"]
    if thumb_path.exists():
        try:
            img_bgr = cv2.imread(str(thumb_path))
            if img_bgr is not None:
                detections = face_engine.detect_and_embed(img_bgr)
                if detections:
                    face = max(detections, key=lambda d: d.confidence)
                    add_face_sample(
                        person_id=target_person_id,
                        embedding=face.embedding,
                        thumbnail_path=detection["thumbnail_path"],
                        source="review_assignment",
                        camera_id=detection.get("camera_id", "")
                    )
        except Exception as e:
            logger.warning("Could not auto-train sample from detection thumbnail: %s", e)

    # 4. Mark detection as assigned
    assign_detection_to_person(detection_id, target_person_id)

    return {
        "status": "success",
        "message": f"Detection assigned to {person['name']}",
        "person_id": target_person_id,
        "person_name": person["name"]
    }

@router.delete("/{detection_id}/dismiss")
async def dismiss_unrecognized_detection(detection_id: str):
    """Dismiss or ignore an unrecognized face detection."""
    success = dismiss_detection(detection_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detection not found")
    return {"status": "success", "message": "Detection dismissed"}

@router.post("/clean-low-confidence")
async def clean_low_confidence_detections(threshold: Optional[float] = None):
    """
    Purge unrecognized detections with confidence below threshold.
    Removes database records and deletes associated thumbnail files.
    """
    min_conf = threshold if threshold is not None else settings.UNKNOWN_MIN_CONFIDENCE
    result = purge_low_confidence_detections(min_confidence=min_conf)
    return {
        "status": "success",
        "message": f"Removed {result['deleted_count']} low-confidence detections (<{int(min_conf * 100)}%)",
        **result
    }

@router.post("/deduplicate")
async def deduplicate_detections(time_window_seconds: Optional[int] = None):
    """
    Combines consecutive unrecognized detections within a sliding timeframe window
    for the same camera, keeping only the highest-confidence best-shot and purging
    redundant duplicate frames and their thumbnail files.
    """
    window = time_window_seconds if time_window_seconds is not None else settings.UNRECOGNIZED_TRACK_WINDOW_SECONDS
    result = deduplicate_unrecognized_detections(time_window_seconds=window)
    return {
        "status": "success",
        "message": f"Deduplicated detections: merged {result['deleted_count']} frames into best-shots (window: {window}s)",
        **result
    }
