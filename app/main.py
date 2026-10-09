import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .config import settings
from .db.database import init_db, seed_default_settings
from .core.face_engine import face_engine
from .routers import (
    recognition_router,
    webhook_router,
    persons_router,
    detections_router,
    auth_router,
    rtsp_router,
    settings_router
)
from .core.rtsp_worker import rtsp_worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("face_detection_app")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize database, sync settings, and warm up face models
    logger.info("Starting up %s (version: %s)...", settings.APP_NAME, settings.APP_VERSION)
    init_db()
    seed_default_settings()
    try:
        face_engine.initialize()
    except Exception as e:
        logger.warning("Engine warm-up deferred or running in mock mode: %s", e)

    # Auto-start RTSP stream processing if enabled
    if settings.RTSP_ENABLED and settings.RTSP_URL:
        logger.info("Auto-starting RTSP stream worker on background thread...")
        rtsp_worker.start()

    yield
    # Shutdown
    logger.info("Shutting down Face Detection service...")
    rtsp_worker.stop()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Household Face Detection, UniFi Protect Auto-Training Webhook, and Management API",
    lifespan=lifespan
)

# CORS Middleware (supports Home Assistant / LAN origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(recognition_router)
app.include_router(webhook_router)
app.include_router(persons_router)
app.include_router(detections_router)
app.include_router(auth_router)
app.include_router(rtsp_router)
app.include_router(settings_router)

# Static Web Application Files
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/health", tags=["System"])
async def health_check():
    """Service health and model readiness check."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "model": settings.FACE_MODEL_NAME,
        "engine_ready": face_engine.initialized
    }

@app.get("/", include_in_schema=False)
async def serve_index():
    """Serve the Web Dashboard SPA."""
    index_file = static_dir / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    return {
        "message": f"Welcome to {settings.APP_NAME}. API documentation is available at /docs"
    }
