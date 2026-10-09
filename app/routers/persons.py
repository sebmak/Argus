import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from ..core.face_engine import face_engine
from ..core.auth import get_optional_user
from ..db.database import (
    get_all_persons,
    get_person_by_id,
    get_person_by_name,
    create_person,
    delete_person,
    add_face_sample,
    delete_face_sample
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/persons", tags=["Persons"])

class CreatePersonRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    notes: Optional[str] = Field("", max_length=500)
    initial_image: Optional[str] = Field(None, description="Optional base64 image to immediately train face")

class AddSampleRequest(BaseModel):
    image: str = Field(..., description="Base64 encoded image containing face")

@router.get("")
async def list_persons():
    """List all registered household members with sample statistics."""
    persons = get_all_persons()
    for p in persons:
        if p.get("primary_thumbnail"):
            p["primary_thumbnail"] = f"/api/v1/thumbnails/{p['primary_thumbnail']}"
    return {"count": len(persons), "persons": persons}

@router.post("", status_code=status.HTTP_201_CREATED)
async def register_person(payload: CreatePersonRequest):
    """Create a new person profile, optionally providing an initial face snapshot."""
    existing = get_person_by_name(payload.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Person with name '{payload.name}' already exists."
        )

    person = create_person(payload.name, payload.notes or "")
    
    # Process initial sample if provided
    samples_added = 0
    if payload.initial_image:
        try:
            img_bgr = face_engine.decode_image(payload.initial_image)
            detections = face_engine.detect_and_embed(img_bgr)
            if detections:
                face = max(detections, key=lambda d: d.confidence)
                add_face_sample(
                    person_id=person["id"],
                    embedding=face.embedding,
                    thumbnail_path=face.thumbnail_filename,
                    source="manual_registration"
                )
                samples_added = 1
        except Exception as e:
            logger.warning("Failed to extract initial face for %s: %s", payload.name, e)

    updated = get_person_by_id(person["id"])
    return {
        "status": "success",
        "person": updated,
        "samples_added": samples_added
    }

@router.get("/{person_id}")
async def get_person_details(person_id: str):
    """Retrieve person profile with full sample gallery."""
    person = get_person_by_id(person_id)
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")

    for sample in person.get("samples", []):
        sample["thumbnail_url"] = f"/api/v1/thumbnails/{sample['thumbnail_path']}"

    return person

@router.post("/{person_id}/samples", status_code=status.HTTP_201_CREATED)
async def upload_person_sample(person_id: str, payload: AddSampleRequest):
    """Add a new training face sample to an existing person."""
    person = get_person_by_id(person_id)
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")

    try:
        img_bgr = face_engine.decode_image(payload.image)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Image decoding failed: {e}")

    detections = face_engine.detect_and_embed(img_bgr)
    if not detections:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No face detected in provided image")

    face = max(detections, key=lambda d: d.confidence)
    sample_id = add_face_sample(
        person_id=person_id,
        embedding=face.embedding,
        thumbnail_path=face.thumbnail_filename,
        source="manual_upload"
    )

    return {
        "status": "success",
        "sample_id": sample_id,
        "thumbnail_url": f"/api/v1/thumbnails/{face.thumbnail_filename}",
        "confidence": face.confidence
    }

@router.delete("/{person_id}")
async def remove_person(person_id: str):
    """Delete a person and all their associated embeddings."""
    success = delete_person(person_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    return {"status": "success", "message": "Person deleted"}

@router.delete("/{person_id}/samples/{sample_id}")
async def remove_sample(person_id: str, sample_id: str):
    """Delete a noisy or outdated face sample."""
    person = get_person_by_id(person_id)
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")

    success = delete_face_sample(sample_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sample not found")

    return {"status": "success", "message": "Sample deleted"}
