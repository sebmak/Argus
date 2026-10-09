"""Core face detection and recognition services"""
try:
    from .face_engine import FaceEngine, face_engine
except ImportError:
    FaceEngine, face_engine = None, None
from .webhook_parser import parse_protect_webhook, WebhookPayload

try:
    from .auth import create_access_token, get_current_user, verify_token
except ImportError:
    create_access_token, get_current_user, verify_token = None, None, None
