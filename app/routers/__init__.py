"""API Routers package"""
from .recognition import router as recognition_router
from .webhook import router as webhook_router
from .persons import router as persons_router
from .detections import router as detections_router
from .auth import router as auth_router
from .rtsp import router as rtsp_router
from .settings import router as settings_router
from .events import router as events_router
