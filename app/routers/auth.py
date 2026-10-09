import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from ..core.auth import create_access_token, get_current_user, get_optional_user
from ..db.database import verify_user_credentials, get_system_stats
from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Auth & System"])

# Rules for LoginRequest class:
# 1. Variables and input schema fields must be declared at the top of the class.
# 2. Used for administrator authentication with username and password.
class LoginRequest(BaseModel):
    username: str
    password: str

# Rules for LoginResponse class:
# 1. Variables and output schema fields must be declared at the top of the class.
# 2. Contains signed JWT bearer token and username.
class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str

@router.post("/auth/login", response_model=LoginResponse)
async def login(payload: LoginRequest, response: Response):
    """Authenticate administrator and issue JWT access token."""
    user = verify_user_credentials(payload.username, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )

    token = create_access_token({"sub": user["username"], "user_id": user["id"]})
    
    # Also set http-only cookie for seamless browser navigation
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        path="/"
    )

    return LoginResponse(
        access_token=token,
        username=user["username"]
    )

@router.post("/auth/logout")
async def logout(response: Response):
    """Clear session cookie."""
    response.delete_cookie(key="access_token", path="/")
    return {"status": "success", "message": "Logged out successfully"}

@router.get("/auth/me")
async def current_user(user: dict = Depends(get_current_user)):
    """Return profile of logged-in user."""
    return {"id": user["id"], "username": user["username"]}

@router.get("/stats")
async def dashboard_stats(user: dict = Depends(get_current_user)):
    """Retrieve system counts and recent activity feed."""
    stats = get_system_stats()
    # Format URLs for recent activity thumbnails
    for act in stats.get("recent_activity", []):
        act["thumbnail_url"] = f"/api/v1/thumbnails/{act['thumbnail_path']}"
    return stats

@router.get("/thumbnails/{filename}")
async def serve_thumbnail(filename: str, user: dict = Depends(get_current_user)):
    """Serve cropped face thumbnail images."""
    # Sanitize path to prevent directory traversal
    safe_name = Path(filename).name
    file_path = settings.thumbnails_path / safe_name
    if not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thumbnail not found")
    return FileResponse(file_path, media_type="image/jpeg")
