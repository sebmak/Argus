import time
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from ..core.face_engine import face_engine
from ..db.database import (
    get_all_active_embeddings,
    record_detection
)
from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Recognition"])

class RecognizeRequest(BaseModel):
    image: str = Field(..., description="Base64 encoded image string or Data URI")
    min_confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Minimum face detection confidence")
    similarity_threshold: Optional[float] = Field(None, ge=0.0, le=1.0, description="Cosine similarity threshold for a match")
    camera_id: Optional[str] = Field("", description="Optional camera name or device identifier")
    save_unrecognized: Optional[bool] = Field(True, description="Queue unknown faces to review inbox")

class FaceBox(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int
    width: int
    height: int

class DetectedFace(BaseModel):
    bbox: FaceBox
    detection_confidence: float
    match: bool
    person_id: Optional[str] = None
    name: str
    similarity: float
    distance: float
    sample_count: int
    thumbnail_url: str
    detection_id: Optional[str] = None

class RecognizeResponse(BaseModel):
    count: int
    faces: List[DetectedFace]
    unrecognized_count: int
    latency_ms: float

@router.post("/recognize", response_model=RecognizeResponse)
async def recognize_faces(payload: RecognizeRequest):
    """
    Primary Household Face Recognition Endpoint.
    Accepts a base64 encoded image, detects all faces, extracts 512-d ArcFace embeddings,
    and classifies each face against known household members.
    """
    start_time = time.perf_counter()

    try:
        img_bgr = face_engine.decode_image(payload.image)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image decoding failed: {str(e)}"
        )

    # 1. Run Detection & Feature Extraction
    detections = face_engine.detect_and_embed(
        img_bgr=img_bgr,
        min_confidence=payload.min_confidence
    )

    # 2. Fetch Known Persons & Centroids
    known_persons = get_all_active_embeddings()

    faces_output: List[DetectedFace] = []
    unrecognized_count = 0

    for det in detections:
        # Match against database
        match_info = face_engine.match_face(
            query_embedding=det.embedding,
            known_persons=known_persons,
            similarity_threshold=payload.similarity_threshold
        )

        det_status = "matched" if match_info["match"] else "unrecognized"
        if not match_info["match"]:
            unrecognized_count += 1

        # Record detection event in database
        detection_id = None
        if payload.save_unrecognized or match_info["match"]:
            detection_id = record_detection(
                thumbnail_path=det.thumbnail_filename,
                bbox=det.bbox,
                camera_id=payload.camera_id or "",
                matched_person_id=match_info["person_id"],
                matched_name=match_info["name"] if match_info["match"] else None,
                similarity=match_info["similarity"],
                status=det_status
            )

        box_w = det.bbox[2] - det.bbox[0]
        box_h = det.bbox[3] - det.bbox[1]

        faces_output.append(DetectedFace(
            bbox=FaceBox(
                x1=det.bbox[0],
                y1=det.bbox[1],
                x2=det.bbox[2],
                y2=det.bbox[3],
                width=box_w,
                height=box_h
            ),
            detection_confidence=det.confidence,
            match=match_info["match"],
            person_id=match_info["person_id"],
            name=match_info["name"],
            similarity=match_info["similarity"],
            distance=match_info["distance"],
            sample_count=match_info["sample_count"],
            thumbnail_url=f"/api/v1/thumbnails/{det.thumbnail_filename}",
            detection_id=detection_id
        ))

    latency = round((time.perf_counter() - start_time) * 1000.0, 2)

    return RecognizeResponse(
        count=len(faces_output),
        faces=faces_output,
        unrecognized_count=unrecognized_count,
        latency_ms=latency
    )
