import time
import logging
from typing import Dict, Tuple
from fastapi import Request, HTTPException, status
from ..config import settings

logger = logging.getLogger(__name__)

# Tracks: ip -> (failure_count, first_attempt_timestamp, lockout_until_timestamp)
_login_attempts: Dict[str, Tuple[int, float, float]] = {}

def get_client_ip(request: Request) -> str:
    """Extracts client IP address, handling reverse proxy headers (X-Forwarded-For, X-Real-IP)."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # X-Forwarded-For may contain a chain: "client, proxy1, proxy2"
        client_ip = forwarded_for.split(",")[0].strip()
        if client_ip:
            return client_ip

    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()

    if request.client and request.client.host:
        return request.client.host

    return "127.0.0.1"

def check_login_rate_limit(client_ip: str) -> None:
    """Checks whether the client IP is currently locked out due to excessive failed login attempts."""
    now = time.time()
    record = _login_attempts.get(client_ip)
    if not record:
        return

    failures, first_time, lockout_until = record
    if now < lockout_until:
        retry_after = int(lockout_until - now)
        logger.warning("Rejected login attempt from locked-out IP %s (cooldown remaining: %ds)", client_ip, retry_after)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts. Your IP has been temporarily locked out for security. Try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)}
        )

def record_login_failure(client_ip: str) -> Tuple[int, bool]:
    """
    Records a failed login attempt for the client IP.
    Returns: (total_failures, is_now_locked_out)
    """
    now = time.time()
    max_attempts = getattr(settings, "RATE_LIMIT_LOGIN_MAX_ATTEMPTS", 5)
    window_seconds = getattr(settings, "RATE_LIMIT_LOGIN_WINDOW_SECONDS", 300)
    lockout_seconds = getattr(settings, "RATE_LIMIT_LOCKOUT_SECONDS", 900)

    record = _login_attempts.get(client_ip)
    if not record:
        _login_attempts[client_ip] = (1, now, 0.0)
        return (1, False)

    failures, first_time, lockout_until = record

    # If the window has expired and wasn't locked out, reset the window
    if now - first_time > window_seconds and now > lockout_until:
        _login_attempts[client_ip] = (1, now, 0.0)
        return (1, False)

    new_failures = failures + 1
    if new_failures >= max_attempts:
        new_lockout = now + lockout_seconds
        _login_attempts[client_ip] = (new_failures, first_time, new_lockout)
        logger.warning(
            "IP %s reached %d failed login attempts; locked out for %d seconds",
            client_ip, new_failures, lockout_seconds
        )
        return (new_failures, True)
    else:
        _login_attempts[client_ip] = (new_failures, first_time, 0.0)
        return (new_failures, False)

def record_login_success(client_ip: str) -> None:
    """Resets failed attempts for client IP after successful authentication."""
    if client_ip in _login_attempts:
        del _login_attempts[client_ip]
