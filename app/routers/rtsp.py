import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field
from ..db.database import save_settings_bulk
from ..core.rtsp_worker import rtsp_worker
from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/rtsp", tags=["RTSP Live Stream"])

# Rules for RtspConfigRequest class:
# 1. Variables and payload schema fields must be declared at the top of the class.
# 2. All configuration fields must be optional to support partial updates.
# 3. Numeric constraints must ensure valid operating ranges for FPS and alert cooldowns.
class RtspConfigRequest(BaseModel):
    url: Optional[str] = Field(None, description="RTSP / RTSPS stream URL")
    camera_name: Optional[str] = Field(None, description="Display name for camera")
    fps: Optional[float] = Field(None, ge=0.5, le=15.0, description="Inference sampling frequency (FPS)")
    cooldown_seconds: Optional[int] = Field(None, ge=1, le=3600, description="Cooldown per entity in seconds")
    webhook_url: Optional[str] = Field(None, description="Outgoing webhook URL")
    webhook_only_known_faces: Optional[bool] = Field(None, description="Only dispatch outgoing webhooks when a recognized known face is matched")
    mqtt_enabled: Optional[bool] = Field(None, description="Enable or disable MQTT publishing")
    mqtt_host: Optional[str] = Field(None, description="MQTT broker host IP / hostname")
    mqtt_port: Optional[int] = Field(None, description="MQTT broker port (e.g. 1883)")
    mqtt_topic: Optional[str] = Field(None, description="MQTT publication topic")

@router.get("/status")
async def get_rtsp_status():
    """Returns the current state and telemetry of the RTSP worker thread."""
    status_data = rtsp_worker.get_status()
    status_data["webhook_url"] = settings.RTSP_WEBHOOK_URL
    status_data["webhook_only_known_faces"] = settings.WEBHOOK_ONLY_KNOWN_FACES
    status_data["mqtt"] = {
        "enabled": settings.MQTT_ENABLED,
        "host": settings.MQTT_HOST,
        "port": settings.MQTT_PORT,
        "topic": settings.MQTT_TOPIC
    }
    return status_data

@router.post("/start")
async def start_rtsp():
    """Starts the real-time background RTSP stream processing thread."""
    if not rtsp_worker.url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No RTSP URL configured. Please configure an RTSP URL first."
        )
    rtsp_worker.start()
    return {"status": "success", "message": "RTSP worker started", "worker": rtsp_worker.get_status()}

@router.post("/stop")
async def stop_rtsp():
    """Stops the real-time RTSP stream processing thread."""
    rtsp_worker.stop()
    return {"status": "success", "message": "RTSP worker stopped", "worker": rtsp_worker.get_status()}

@router.post("/config")
async def update_rtsp_config(payload: RtspConfigRequest):
    """Updates RTSP stream, cooldowns, webhook, and MQTT settings at runtime and persists to SQLite."""
    updates = {}
    if payload.url is not None:
        updates["rtsp_url"] = payload.url.strip()
    if payload.camera_name is not None:
        updates["rtsp_camera_name"] = payload.camera_name.strip()
    if payload.fps is not None:
        updates["rtsp_fps"] = payload.fps
    if payload.cooldown_seconds is not None:
        updates["rtsp_cooldown_seconds"] = payload.cooldown_seconds
    if payload.webhook_url is not None:
        updates["rtsp_webhook_url"] = payload.webhook_url.strip()
    if payload.webhook_only_known_faces is not None:
        updates["webhook_only_known_faces"] = payload.webhook_only_known_faces
    if payload.mqtt_enabled is not None:
        updates["mqtt_enabled"] = payload.mqtt_enabled
    if payload.mqtt_host is not None:
        updates["mqtt_host"] = payload.mqtt_host.strip()
    if payload.mqtt_port is not None:
        updates["mqtt_port"] = payload.mqtt_port
    if payload.mqtt_topic is not None:
        updates["mqtt_topic"] = payload.mqtt_topic.strip()

    save_settings_bulk(updates)

    return {
        "status": "success",
        "message": "Configuration updated",
        "settings": {
            "rtsp_url": settings.RTSP_URL,
            "camera_name": settings.RTSP_CAMERA_NAME,
            "fps": settings.RTSP_FPS,
            "cooldown_seconds": settings.RTSP_COOLDOWN_SECONDS,
            "webhook_url": settings.RTSP_WEBHOOK_URL,
            "webhook_only_known_faces": settings.WEBHOOK_ONLY_KNOWN_FACES,
            "mqtt_enabled": settings.MQTT_ENABLED,
            "mqtt_host": settings.MQTT_HOST,
            "mqtt_port": settings.MQTT_PORT,
            "mqtt_topic": settings.MQTT_TOPIC
        }
    }

@router.get("/preview")
async def get_stream_preview():
    """Returns the latest captured frame as JPEG for live UI monitoring."""
    jpeg_bytes = rtsp_worker.get_latest_jpeg()
    if not jpeg_bytes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No video frame available. Ensure RTSP stream is running and connected."
        )
    return Response(content=jpeg_bytes, media_type="image/jpeg")
