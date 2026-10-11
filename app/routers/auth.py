import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends, Response, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from ..core.auth import create_access_token, get_current_user, get_optional_user
from ..core.rate_limiter import check_login_rate_limit, record_login_failure, record_login_success, get_client_ip
from ..db.database import (
    verify_user_credentials,
    verify_password,
    update_user_password,
    is_default_password_used,
    get_system_stats,
    record_event_log
)
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
# 2. Contains signed JWT bearer token, username, and default password warning flag.
class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    is_default_password: bool = False

# Rules for ChangePasswordRequest class:
# 1. Variables and input schema fields must be declared at the top of the class.
# 2. Enforces current password verification and minimum 8-character new password complexity.
class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, description="Minimum 8 characters for remote security")

# Rules for ChangePasswordResponse class:
# 1. Variables and schema fields must be declared at the top of the class.
# 2. Returns status confirmation and refreshed JWT bearer token.
class ChangePasswordResponse(BaseModel):
    status: str = "success"
    message: str
    access_token: str

@router.post("/auth/login", response_model=LoginResponse)
async def login(payload: LoginRequest, request: Request, response: Response):
    """
    Authenticate administrator, enforce rate limiting against brute-force attacks,
    and issue signed JWT access token.
    """
    client_ip = get_client_ip(request)
    check_login_rate_limit(client_ip)

    user = verify_user_credentials(payload.username, payload.password)
    if not user:
        failures, is_locked_out = record_login_failure(client_ip)
        record_event_log(
            level="warning",
            category="security",
            event_type="auth_login_failed",
            message=f"Failed login attempt for '{payload.username}' from {client_ip} (failure count: {failures})",
            details={"ip": client_ip, "username": payload.username, "failures": failures, "locked_out": is_locked_out}
        )
        if is_locked_out:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed attempts. Your IP has been temporarily locked out for 15 minutes."
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )

    # Clear rate limit state on successful login
    record_login_success(client_ip)
    record_event_log(
        level="info",
        category="security",
        event_type="auth_login_success",
        message=f"Administrator '{user['username']}' authenticated from {client_ip}",
        details={"ip": client_ip, "user_id": user["id"]}
    )

    token = create_access_token({"sub": user["username"], "user_id": user["id"]})
    has_default_pw = is_default_password_used(user)

    # Detect if request is over HTTPS or behind reverse proxy
    is_https = (
        request.url.scheme == "https"
        or request.headers.get("x-forwarded-proto", "").lower() == "https"
        or settings.COOKIE_SECURE
    )

    # Set hardened http-only session cookie
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=is_https,
        path="/"
    )

    return LoginResponse(
        access_token=token,
        username=user["username"],
        is_default_password=has_default_pw
    )

@router.post("/auth/change-password", response_model=ChangePasswordResponse)
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    user: dict = Depends(get_current_user)
):
    """
    Safely update administrator password after verifying the existing credentials.
    Re-hashes with bcrypt and issues a refreshed access token.
    """
    client_ip = get_client_ip(request)

    # 1. Verify current password
    if not verify_password(payload.current_password, user.get("password_hash", "")):
        record_event_log(
            level="warning",
            category="security",
            event_type="password_change_rejected",
            message=f"Password update rejected: invalid current password for user '{user['username']}' from {client_ip}",
            details={"ip": client_ip, "user_id": user["id"]}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    # 2. Prevent setting to the exact same password
    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from your current password"
        )

    # 3. Update password in database
    success = update_user_password(user["id"], payload.new_password.strip())
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update password in storage"
        )

    # 4. Generate refreshed token
    refreshed_token = create_access_token({"sub": user["username"], "user_id": user["id"]})

    is_https = (
        request.url.scheme == "https"
        or request.headers.get("x-forwarded-proto", "").lower() == "https"
        or settings.COOKIE_SECURE
    )

    response.set_cookie(
        key="access_token",
        value=refreshed_token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=is_https,
        path="/"
    )

    record_event_log(
        level="info",
        category="security",
        event_type="password_changed",
        message=f"Administrator '{user['username']}' successfully changed password from {client_ip}",
        details={"ip": client_ip, "user_id": user["id"]}
    )

    return ChangePasswordResponse(
        status="success",
        message="Password updated successfully",
        access_token=refreshed_token
    )

@router.post("/auth/logout")
async def logout(response: Response):
    """Clear session cookie."""
    response.delete_cookie(key="access_token", path="/")
    return {"status": "success", "message": "Logged out successfully"}

@router.get("/auth/me")
async def current_user(user: dict = Depends(get_current_user)):
    """Return profile of logged-in user including security status."""
    return {
        "id": user["id"],
        "username": user["username"],
        "is_default_password": is_default_password_used(user)
    }

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
