import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ..db.database import get_all_settings, save_settings_bulk
from ..config import settings
from ..core.rtsp_worker import rtsp_worker

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/settings", tags=["System Settings"])

# Rules for SettingsUpdateRequest class:
# 1. Variables and input schema fields must be declared at the top of the class.
# 2. All settings fields must be optional to support partial updates.
# 3. Numeric parameters must have valid bounds (e.g. ge, le) to guard against invalid engine configurations.
class SettingsUpdateRequest(BaseModel):
    # Face Recognition
    face_detector_type: Optional[str] = Field(None, description="Detector engine: 'yolov8_face' or 'scrfd'")
    detection_confidence: Optional[float] = Field(None, ge=0.05, le=1.0, description="Minimum face detection confidence (0.05-1.0)")
    similarity_threshold: Optional[float] = Field(None, ge=0.1, le=1.0, description="Cosine similarity threshold for known identity (0.1-1.0)")
    notification_threshold: Optional[float] = Field(None, ge=0.1, le=1.0, description="Minimum confidence/similarity before dispatching notifications (0.1-1.0)")
    notify_on_unknown: Optional[bool] = Field(None, description="Whether to send notifications for unrecognized faces")
    unknown_min_confidence: Optional[float] = Field(None, ge=0.1, le=1.0, description="Minimum face detection confidence for unrecognized face alerts")
    det_size: Optional[int] = Field(None, description="InsightFace detector input size (e.g. 320, 480, 640)")
    ort_num_threads: Optional[int] = Field(None, ge=1, le=96, description="ONNX Runtime CPU threads")
    max_samples_per_person: Optional[int] = Field(None, ge=1, le=500, description="Maximum learned face embeddings per person")
    unrecognized_track_window_seconds: Optional[int] = Field(None, ge=1, le=300, description="Sliding window in seconds to aggregate unknown face detections into a single best-shot")

    # RTSP Camera Stream & Webhook
    rtsp_enabled: Optional[bool] = Field(None, description="Enable real-time background RTSP worker")
    rtsp_url: Optional[str] = Field(None, description="RTSP / RTSPS video stream URL")
    rtsp_camera_name: Optional[str] = Field(None, description="Display name for camera source")
    rtsp_fps: Optional[float] = Field(None, ge=0.5, le=15.0, description="Inference sampling frequency (FPS)")
    rtsp_cooldown_seconds: Optional[int] = Field(None, ge=1, le=3600, description="Cooldown per entity in seconds before repeating alert")
    rtsp_webhook_url: Optional[str] = Field(None, description="Outgoing webhook endpoint URL")
    webhook_only_known_faces: Optional[bool] = Field(None, description="Only dispatch outgoing webhooks when a recognized/known face is matched")

    # MQTT Event Publishing
    mqtt_enabled: Optional[bool] = Field(None, description="Enable MQTT event publishing")
    mqtt_host: Optional[str] = Field(None, description="MQTT broker hostname or IP")
    mqtt_port: Optional[int] = Field(None, ge=1, le=65535, description="MQTT broker port (e.g. 1883)")
    mqtt_topic: Optional[str] = Field(None, description="MQTT publication topic prefix")
    mqtt_user: Optional[str] = Field(None, description="MQTT broker username")
    mqtt_password: Optional[str] = Field(None, description="MQTT broker password")
    mqtt_only_known_faces: Optional[bool] = Field(None, description="Only publish MQTT events when a recognized known face is matched")

@router.get("")
@router.get("/")
async def get_system_settings() -> Dict[str, Any]:
    """Retrieves all dynamically configurable settings stored in SQLite."""
    return get_all_settings()

@router.post("")
@router.post("/")
async def update_system_settings(payload: SettingsUpdateRequest) -> Dict[str, Any]:
    """
    Saves configurable settings into SQLite and updates active runtime memory immediately.
    No container restart required.
    """
    data = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)
    
    updated = save_settings_bulk(data)
    
    # Manage RTSP worker state according to rtsp_enabled setting
    if "rtsp_enabled" in data:
        if settings.RTSP_ENABLED and settings.RTSP_URL and not rtsp_worker.is_running:
            logger.info("Auto-starting RTSP worker due to settings update...")
            rtsp_worker.start()
        elif not settings.RTSP_ENABLED and rtsp_worker.is_running:
            logger.info("Stopping RTSP worker due to settings update...")
            rtsp_worker.stop()

    return {
        "status": "success",
        "message": "Settings updated and applied to active runtime.",
        "settings": updated
    }

# Rules for MigrationRollbackRequest class:
# 1. Variables and payload schema fields must be declared at the top of the class.
# 2. target_version specifies the desired database schema version to safely roll back to.
class MigrationRollbackRequest(BaseModel):
    target_version: str = Field("1.0.0", description="App version to roll back database schema to (e.g. 1.0.0)")

# Rules for MigrationForwardRequest class:
# 1. Variables and payload schema fields must be declared at the top of the class.
# 2. target_version specifies the desired forward schema version or None for current app version.
class MigrationForwardRequest(BaseModel):
    target_version: Optional[str] = Field(None, description="App version to roll forward database schema to (e.g. 1.1.0)")

@router.get("/migrations")
async def get_migrations_telemetry() -> Dict[str, Any]:
    """Returns database migration history, applied versions, and current status."""
    from ..db.migrations import get_migration_status
    return get_migration_status()

@router.post("/migrations/rollback")
async def rollback_schema_version(payload: MigrationRollbackRequest) -> Dict[str, Any]:
    """
    Safely rolls back database schema to a previous application version.
    Preserves core entity and embedding data and creates an atomic backup snapshot.
    """
    from ..db.migrations import rollback_migrations
    result = rollback_migrations(payload.target_version)
    return result

@router.post("/migrations/forward")
async def forward_schema_version(payload: MigrationForwardRequest) -> Dict[str, Any]:
    """
    Reconciles and rolls forward database schema to match target application version.
    """
    from ..db.migrations import run_migrations
    result = run_migrations(target_version=payload.target_version)
    return result

