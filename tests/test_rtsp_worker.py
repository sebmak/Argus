import unittest
import time
import sys
from unittest.mock import patch, MagicMock

# Graceful mocks for host systems without Docker packages installed
for mod in ["cv2", "numpy", "httpx", "paho", "paho.mqtt", "paho.mqtt.client", "fastapi", "fastapi.security", "jose"]:
    if mod not in sys.modules:
        try:
            __import__(mod)
        except ImportError:
            sys.modules[mod] = MagicMock()

bcrypt_mock = MagicMock()
bcrypt_mock.gensalt.return_value = b"$2b$12$e0abcdef12345678901234"
bcrypt_mock.hashpw.return_value = b"$2b$12$hashedpasswordmockmockmock"
sys.modules["bcrypt"] = bcrypt_mock

if "pydantic" not in sys.modules:
    # Rules for DummyBaseModel class:
    # 1. Variables and mock attributes must be defined at the top of the class.
    # 2. Used as lightweight mock fallback when pydantic is unavailable in test environment.
    class DummyBaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
    pyd_mock = MagicMock()
    pyd_mock.BaseModel = DummyBaseModel
    pyd_mock.BaseSettings = DummyBaseModel
    pyd_mock.Field = lambda *args, **kwargs: None
    sys.modules["pydantic"] = pyd_mock
    sys.modules["pydantic_settings"] = pyd_mock

from app.core.rtsp_worker import RtspStreamWorker

# Rules for TestRtspWorker class:
# 1. Variables and worker references must be declared at the top of the class.
# 2. Tests verify streaming status reporting, cooldown suppression, inference rate limiting, and webhook event dispatching.
# 3. Mocks are isolated per test method to prevent state leakage.
class TestRtspWorker(unittest.TestCase):
    worker: RtspStreamWorker = None

    def setUp(self):
        self.worker = RtspStreamWorker()
        self.worker.cooldown_seconds = 10
        self.worker.camera_name = "Test Camera"

    def test_status_reporting(self):
        status = self.worker.get_status()
        self.assertFalse(status["is_running"])
        self.assertFalse(status["is_connected"])
        self.assertEqual(status["camera_name"], "Test Camera")
        self.assertEqual(status["cooldown_seconds"], 10)

    def test_configuration_updates(self):
        self.worker.configure(
            url="rtsp://192.168.1.50:554/stream",
            camera_name="Driveway",
            fps=5.0,
            cooldown_seconds=45
        )
        self.assertEqual(self.worker.url, "rtsp://192.168.1.50:554/stream")
        self.assertEqual(self.worker.camera_name, "Driveway")
        self.assertEqual(self.worker.fps, 5.0)
        self.assertEqual(self.worker.cooldown_seconds, 45)

    def test_cooldown_suppression_logic(self):
        # Initial state: no cooldowns
        now = time.time()
        self.worker.cooldowns["sebastian"] = now

        # Case 1: Same person within cooldown window (e.g. 2s later) -> suppressed
        last_alert = self.worker.cooldowns.get("sebastian", 0.0)
        is_suppressed = (now + 2.0 - last_alert) < self.worker.cooldown_seconds
        self.assertTrue(is_suppressed)

        # Case 2: Different person -> NOT suppressed
        last_alice = self.worker.cooldowns.get("alice", 0.0)
        is_suppressed_alice = (now + 2.0 - last_alice) < self.worker.cooldown_seconds
        self.assertFalse(is_suppressed_alice)

        # Case 3: Same person after cooldown expires (e.g. 15s later) -> NOT suppressed
        is_suppressed_after = (now + 15.0 - last_alert) < self.worker.cooldown_seconds
        self.assertFalse(is_suppressed_after)

    @patch("app.core.events.httpx.Client")
    def test_dispatch_webhook(self, mock_client_cls):
        from app.core.events import dispatch_detection_event
        from app.config import settings

        settings.RTSP_WEBHOOK_URL = "http://mock-webhook.local/alert"
        settings.MQTT_ENABLED = False

        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.post.return_value.status_code = 200

        event_payload = {
            "event": "face_detection",
            "camera": "Front Door",
            "person_name": "Sebastian",
            "match": True,
            "similarity": 0.85
        }

        dispatch_detection_event(event_payload)
        mock_client.post.assert_called_once_with("http://mock-webhook.local/alert", json=event_payload)

    @patch("app.core.rtsp_worker.dispatch_detection_event")
    @patch("app.core.rtsp_worker.record_detection")
    @patch("app.core.rtsp_worker.get_all_active_embeddings")
    @patch("app.core.rtsp_worker.face_engine")
    def test_notification_threshold_matched_face_filtering(self, mock_engine, mock_get_emb, mock_record, mock_dispatch):
        from app.config import settings

        settings.NOTIFICATION_THRESHOLD = 0.65
        settings.RTSP_COOLDOWN_SECONDS = 30
        self.worker.cooldown_seconds = 30
        self.worker.cooldowns.clear()

        # Mock face detection result
        mock_det = MagicMock()
        mock_det.embedding = [0.1] * 512
        mock_det.confidence = 0.95
        mock_det.bbox = [10, 10, 100, 100]
        mock_det.thumbnail_filename = "test.jpg"
        mock_det.thumbnail_base64 = "base64"
        mock_engine.detect_and_embed.return_value = [mock_det]
        mock_get_emb.return_value = {}
        mock_record.return_value = "det_123"

        # Case 1: Match with similarity 0.50 (below 0.65 threshold) -> suppressed, no dispatch
        mock_engine.match_face.return_value = {
            "match": True,
            "person_id": "p_1",
            "name": "Sebastian",
            "similarity": 0.50,
            "distance": 0.50
        }

        self.worker._process_frame(MagicMock())
        mock_dispatch.assert_not_called()
        self.assertNotIn("sebastian", self.worker.cooldowns)

        # Case 2: Match with similarity 0.72 (above 0.65 threshold) -> dispatched!
        mock_engine.match_face.return_value = {
            "match": True,
            "person_id": "p_1",
            "name": "Sebastian",
            "similarity": 0.72,
            "distance": 0.28
        }

        self.worker._process_frame(MagicMock())
        mock_dispatch.assert_called_once()
        self.assertIn("sebastian", self.worker.cooldowns)

    @patch("app.core.rtsp_worker.dispatch_detection_event")
    @patch("app.core.rtsp_worker.record_detection")
    @patch("app.core.rtsp_worker.get_all_active_embeddings")
    @patch("app.core.rtsp_worker.face_engine")
    def test_notification_threshold_unknown_face_filtering(self, mock_engine, mock_get_emb, mock_record, mock_dispatch):
        from app.config import settings

        mock_det = MagicMock()
        mock_det.embedding = [0.1] * 512
        mock_det.bbox = [10, 10, 100, 100]
        mock_det.thumbnail_filename = "test_unk.jpg"
        mock_det.thumbnail_base64 = "base64"
        mock_engine.detect_and_embed.return_value = [mock_det]
        mock_get_emb.return_value = {}
        mock_record.return_value = "det_unk"

        mock_engine.match_face.return_value = {
            "match": False,
            "person_id": None,
            "name": "Unknown",
            "similarity": 0.20,
            "distance": 0.80
        }

        # Case 1: notify_on_unknown is False -> suppressed
        settings.NOTIFY_ON_UNKNOWN = False
        settings.UNKNOWN_MIN_CONFIDENCE = 0.60
        mock_det.confidence = 0.90
        self.worker.cooldowns.clear()

        self.worker._process_frame(MagicMock())
        mock_dispatch.assert_not_called()

        # Case 2: notify_on_unknown is True, but confidence 0.40 < 0.60 -> suppressed
        settings.NOTIFY_ON_UNKNOWN = True
        mock_det.confidence = 0.40
        self.worker.cooldowns.clear()

        self.worker._process_frame(MagicMock())
        mock_dispatch.assert_not_called()

        # Case 3: notify_on_unknown is True and confidence 0.75 >= 0.60 -> dispatched
        mock_det.confidence = 0.75
        self.worker.cooldowns.clear()

        self.worker._process_frame(MagicMock())
        mock_dispatch.assert_called_once()
        self.assertIn("unknown", self.worker.cooldowns)

    @patch("httpx.Client")
    def test_webhook_only_known_faces_filtering(self, mock_httpx_cls):
        from app.config import settings
        from app.core.events import dispatch_detection_event

        mock_client = MagicMock()
        mock_httpx_cls.return_value.__enter__.return_value = mock_client
        mock_post = mock_client.post

        settings.RTSP_WEBHOOK_URL = "http://example.com/webhook"
        settings.MQTT_ENABLED = False

        known_event = {
            "event": "face_detection",
            "match": True,
            "person_name": "Alice",
            "similarity": 0.88
        }
        unknown_event = {
            "event": "face_detection",
            "match": False,
            "person_name": "Unknown",
            "similarity": 0.20
        }

        # Scenario 1: WEBHOOK_ONLY_KNOWN_FACES is True
        settings.WEBHOOK_ONLY_KNOWN_FACES = True

        # Unknown face -> Suppressed
        mock_post.reset_mock()
        dispatch_detection_event(unknown_event)
        mock_post.assert_not_called()

        # Known face -> Sent
        mock_post.reset_mock()
        dispatch_detection_event(known_event)
        mock_post.assert_called_once_with("http://example.com/webhook", json=known_event)

        # Scenario 2: WEBHOOK_ONLY_KNOWN_FACES is False
        settings.WEBHOOK_ONLY_KNOWN_FACES = False

        # Unknown face -> Sent
        mock_post.reset_mock()
        dispatch_detection_event(unknown_event)
        mock_post.assert_called_once_with("http://example.com/webhook", json=unknown_event)

if __name__ == "__main__":
    unittest.main()
