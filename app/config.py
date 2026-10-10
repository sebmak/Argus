import os
from pathlib import Path

try:
    from pydantic_settings import BaseSettings
except ImportError:
    try:
        from pydantic import BaseSettings
    except ImportError:
        class BaseSettings:
            pass

def _resolve_config_dir() -> str:
    """
    Resolves the persistent configuration and data directory.
    Prioritizes Unraid /config standard, then DATA_DIR, then container /config, then local ./data.
    """
    if os.getenv("CONFIG_DIR"):
        return os.getenv("CONFIG_DIR")
    if os.getenv("DATA_DIR"):
        return os.getenv("DATA_DIR")
    if os.path.exists("/config") and os.path.isdir("/config"):
        return "/config"
    return "./data"

# Rules for Settings class:
# 1. Variables and configuration properties must be declared at the top of the class.
# 2. Defaults are read from environment variables with safe fallbacks.
# 3. Dynamic runtime overrides are synchronized with the SQLite settings table without container restarts.
# 4. Supports detector engine selection ('yolov8_face' or 'scrfd') with dedicated YOLO model parameters.
# 5. Configures real-time stream motion gating and threshold settings to optimize CPU usage on static video feeds.
class Settings(BaseSettings):
    # App Information
    APP_NAME: str = "Household Face Detection API"
    APP_VERSION: str = os.getenv("APP_VERSION", "0.0.14")
    DEBUG: bool = False

    # Storage & Unraid Config Paths
    CONFIG_DIR: str = _resolve_config_dir()
    DATA_DIR: str = CONFIG_DIR  # Backwards compatibility alias
    DB_FILENAME: str = "faces.db"
    
    # Face Recognition Settings
    FACE_MODEL_NAME: str = os.getenv("FACE_MODEL_NAME", "buffalo_l")  # 'buffalo_l' or 'buffalo_s'
    FACE_DETECTOR_TYPE: str = os.getenv("FACE_DETECTOR_TYPE", "yolov8_face")  # 'yolov8_face' or 'scrfd'
    YOLO_FACE_MODEL_NAME: str = os.getenv("YOLO_FACE_MODEL_NAME", "yolov8n-face.onnx")
    SIMILARITY_THRESHOLD: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.45"))
    DETECTION_CONFIDENCE: float = float(os.getenv("DETECTION_CONFIDENCE", "0.60"))
    MAX_SAMPLES_PER_PERSON: int = int(os.getenv("MAX_SAMPLES_PER_PERSON", "50"))
    UNRECOGNIZED_TRACK_WINDOW_SECONDS: int = int(os.getenv("UNRECOGNIZED_TRACK_WINDOW_SECONDS", "15"))
    
    # Latency & Hardware Optimization Settings (Crucial for high core-count servers)
    DET_SIZE: int = int(os.getenv("DET_SIZE", "320"))  # 320 for ultra-fast (~20-50ms), 480 for balanced, 640 for max range
    ORT_NUM_THREADS: int = int(os.getenv("ORT_NUM_THREADS", "8"))  # Limit OpenMP/ONNX threads to prevent 98-core thread thrashing
    MAX_IMAGE_SIZE: int = int(os.getenv("MAX_IMAGE_SIZE", "1280"))  # Downscale 4K/2K frames to max 1280px before inference
    
    # Security & Auth
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secret-household-face-detection-key-change-in-prod")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    DEFAULT_ADMIN_USER: str = os.getenv("DEFAULT_ADMIN_USER", "admin")
    DEFAULT_ADMIN_PASSWORD: str = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")
    
    # UniFi Protect Webhook Security
    WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "")  # Optional token check

    # RTSP Live Stream Ingestion Settings
    RTSP_ENABLED: bool = os.getenv("RTSP_ENABLED", "false").lower() in ("true", "1", "yes")
    RTSP_URL: str = os.getenv("RTSP_URL", "")
    RTSP_CAMERA_NAME: str = os.getenv("RTSP_CAMERA_NAME", "Front Door RTSP")
    RTSP_FPS: float = float(os.getenv("RTSP_FPS", "3.0"))  # Real-time inference frequency (2-5 FPS recommended)
    RTSP_COOLDOWN_SECONDS: int = int(os.getenv("RTSP_COOLDOWN_SECONDS", "30"))  # Cooldown per person before repeating event
    RTSP_MOTION_GATING_ENABLED: bool = os.getenv("RTSP_MOTION_GATING_ENABLED", "true").lower() in ("true", "1", "yes")
    RTSP_MOTION_THRESHOLD: float = float(os.getenv("RTSP_MOTION_THRESHOLD", "0.015"))  # Pixel diff ratio (default: 1.5%)
    RTSP_MOTION_HANGOVER_SECONDS: float = float(os.getenv("RTSP_MOTION_HANGOVER_SECONDS", "2.5"))  # Infer for 2.5s post-motion
    RTSP_WEBHOOK_URL: str = os.getenv("RTSP_WEBHOOK_URL", "")  # Outgoing webhook URL (e.g. Home Assistant automation)
    WEBHOOK_ONLY_KNOWN_FACES: bool = os.getenv("WEBHOOK_ONLY_KNOWN_FACES", os.getenv("RTSP_WEBHOOK_ONLY_KNOWN", "true")).lower() in ("true", "1", "yes")  # Restrict outgoing webhooks strictly to known faces

    # Event Notification Thresholds
    NOTIFICATION_THRESHOLD: float = float(os.getenv("NOTIFICATION_THRESHOLD", "0.55"))  # Min similarity score to emit alert
    NOTIFY_ON_UNKNOWN: bool = os.getenv("NOTIFY_ON_UNKNOWN", "false").lower() in ("true", "1", "yes")  # Alert on unknown faces
    UNKNOWN_MIN_CONFIDENCE: float = float(os.getenv("UNKNOWN_MIN_CONFIDENCE", "0.60"))  # Min confidence for unknown faces

    # MQTT Broker Event Notification Settings
    MQTT_ENABLED: bool = os.getenv("MQTT_ENABLED", "false").lower() in ("true", "1", "yes")
    MQTT_HOST: str = os.getenv("MQTT_HOST", "")
    MQTT_PORT: int = int(os.getenv("MQTT_PORT", "1883"))
    MQTT_USER: str = os.getenv("MQTT_USER", "")
    MQTT_PASSWORD: str = os.getenv("MQTT_PASSWORD", "")
    MQTT_TOPIC: str = os.getenv("MQTT_TOPIC", "facedetection/events")
    MQTT_ONLY_KNOWN_FACES: bool = os.getenv("MQTT_ONLY_KNOWN_FACES", os.getenv("WEBHOOK_ONLY_KNOWN_FACES", "true")).lower() in ("true", "1", "yes")  # Restrict MQTT events strictly to known faces

    @property
    def config_path(self) -> Path:
        dir_name = os.getenv("CONFIG_DIR") or os.getenv("DATA_DIR") or self.CONFIG_DIR
        path = Path(dir_name)
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return path

    @property
    def data_path(self) -> Path:
        return self.config_path

    @property
    def db_path(self) -> str:
        return str(self.config_path / self.DB_FILENAME)

    @property
    def thumbnails_path(self) -> Path:
        path = self.config_path / "thumbnails"
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return path

    @property
    def snapshots_path(self) -> Path:
        path = self.config_path / "snapshots"
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return path

    @property
    def models_path(self) -> Path:
        path = self.config_path / "models"
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return path

settings = Settings()
