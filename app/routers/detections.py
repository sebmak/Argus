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
    get_person_by_id,
    get_person_by_name,
    create_person,
    add_face_sample,
    get_db
)
from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/detections", tags=["Detections Queue"])

class AssignDetectionRequest(BaseModel):
    person_id: Optional[str] = Field(None, description="ID of existing person to assign to")
    new_person_name: Optional[str] = Field(None, description="Name for newly created person if not existing")

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
            new_p = create_person(name_clean, notes="Created from unrecognized review inbox")
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
