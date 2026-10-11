import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .config import settings
from .db.database import init_db, seed_default_settings
from .core.face_engine import face_engine
from .core.auth import get_current_user
from .routers import (
    recognition_router,
    webhook_router,
    persons_router,
    detections_router,
    auth_router,
    rtsp_router,
    settings_router,
    events_router
)
from .core.rtsp_worker import rtsp_worker
from .db.database import record_event_log

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

    record_event_log(
        level="info",
        category="system",
        event_type="system_start",
        message=f"{settings.APP_NAME} started (v{settings.APP_VERSION}, detector: {settings.FACE_DETECTOR_TYPE})",
        details={"version": settings.APP_VERSION, "detector": settings.FACE_DETECTOR_TYPE, "model": settings.FACE_MODEL_NAME}
    )

    # Auto-start RTSP stream processing if enabled
    if settings.RTSP_ENABLED and settings.RTSP_URL:
        logger.info("Auto-starting RTSP stream worker on background thread...")
        rtsp_worker.start()

    yield
    # Shutdown
    logger.info("Shutting down Face Detection service...")
    record_event_log(
        level="info",
        category="system",
        event_type="system_stop",
        message=f"{settings.APP_NAME} service shutting down",
        details={}
    )
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
app.include_router(auth_router)

# Administrative & Management Routers (gated by authentication cookie or bearer token)
app.include_router(persons_router, dependencies=[Depends(get_current_user)])
app.include_router(detections_router, dependencies=[Depends(get_current_user)])
app.include_router(rtsp_router, dependencies=[Depends(get_current_user)])
app.include_router(settings_router, dependencies=[Depends(get_current_user)])
app.include_router(events_router, dependencies=[Depends(get_current_user)])

# Static Web Application Files
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

assets_dir = static_dir / "assets"
assets_dir.mkdir(parents=True, exist_ok=True)
app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

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
@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(full_path: str = ""):
    """Serve static file or fallback to React SPA index.html."""
    if full_path:
        candidate = static_dir / full_path
        if candidate.is_file():
            return FileResponse(candidate)
    index_file = static_dir / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    return {
        "message": f"Welcome to {settings.APP_NAME}. API documentation is available at /docs"
    }
