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
# 2. Tests verify streaming status reporting, cooldown suppression, inference rate limiting, webhook event dispatching, and unknown track best-shot aggregation.
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
        settings.NOTIFY_ON_UNKNOWN = True
        settings.RTSP_WEBHOOK_URL = "http://example.com/webhook"
        settings.WEBHOOK_ONLY_KNOWN_FACES = False
        settings.MQTT_ONLY_KNOWN_FACES = False
        mock_det.confidence = 0.75
        self.worker.cooldowns.clear()
        self.worker.unknown_tracks.clear()

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
        settings.NOTIFY_ON_UNKNOWN = True

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

    @patch("app.core.events.get_mqtt_client")
    def test_mqtt_only_known_faces_filtering(self, mock_get_client):
        from app.config import settings
        from app.core.events import dispatch_detection_event

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_publish = mock_client.publish

        settings.MQTT_ENABLED = True
        settings.MQTT_TOPIC = "facedetection/events"
        settings.RTSP_WEBHOOK_URL = ""
        settings.NOTIFY_ON_UNKNOWN = True

        known_event = {
            "event": "face_detection",
            "match": True,
            "person_name": "Bob",
            "similarity": 0.90
        }
        unknown_event = {
            "event": "face_detection",
            "match": False,
            "person_name": "Unknown",
            "similarity": 0.15
        }

        # Scenario 1: MQTT_ONLY_KNOWN_FACES is True
        settings.MQTT_ONLY_KNOWN_FACES = True
        settings.WEBHOOK_ONLY_KNOWN_FACES = True

        # Unknown face -> Suppressed on MQTT
        mock_publish.reset_mock()
        dispatch_detection_event(unknown_event)
        mock_publish.assert_not_called()

        # Known face -> Published on MQTT
        mock_publish.reset_mock()
        dispatch_detection_event(known_event)
        self.assertEqual(mock_publish.call_count, 2)  # main topic + person subtopic

        # Scenario 2: MQTT_ONLY_KNOWN_FACES is False, WEBHOOK_ONLY_KNOWN_FACES is False, NOTIFY_ON_UNKNOWN is True
        settings.MQTT_ONLY_KNOWN_FACES = False
        settings.WEBHOOK_ONLY_KNOWN_FACES = False
        settings.NOTIFY_ON_UNKNOWN = True

        # Unknown face -> Published
        mock_publish.reset_mock()
        dispatch_detection_event(unknown_event)
        mock_publish.assert_called_once()

    @patch("app.core.rtsp_worker.update_detection_best_shot")
    @patch("app.core.rtsp_worker.record_detection")
    @patch("app.core.rtsp_worker.get_all_active_embeddings")
    @patch("app.core.rtsp_worker.face_engine")
    def test_sliding_window_unknown_face_aggregation(self, mock_engine, mock_get_emb, mock_record, mock_update):
        from app.config import settings

        mock_get_emb.return_value = {}
        mock_record.return_value = "det_initial_1"
        self.worker.unknown_tracks.clear()
        self.worker.cooldowns.clear()

        # Face engine returns cosine_similarity of 0.85 (same unknown person in scene)
        mock_engine.cosine_similarity.return_value = 0.85
        mock_engine.match_face.return_value = {
            "match": False,
            "person_id": None,
            "name": "Unknown",
            "similarity": 0.20,
            "distance": 0.80
        }

        # Frame 1: First appearance of unknown face at 0.70 confidence
        det1 = MagicMock()
        det1.embedding = [0.1] * 512
        det1.confidence = 0.70
        det1.bbox = [10, 10, 100, 100]
        det1.thumbnail_filename = "frame1.jpg"
        det1.thumbnail_base64 = "base64_1"
        mock_engine.detect_and_embed.return_value = [det1]

        self.worker._process_frame(MagicMock())
        self.assertEqual(mock_record.call_count, 1)
        self.assertEqual(len(self.worker.unknown_tracks), 1)
        self.assertEqual(self.worker.unknown_tracks[0]["best_confidence"], 0.70)
        self.assertEqual(self.worker.unknown_tracks[0]["thumbnail_filename"], "frame1.jpg")

        # Frame 2: Same face stays in view, but now higher confidence 0.95 (clear shot)
        det2 = MagicMock()
        det2.embedding = [0.1] * 512
        det2.confidence = 0.95
        det2.bbox = [12, 12, 105, 105]
        det2.thumbnail_filename = "frame2_best.jpg"
        det2.thumbnail_base64 = "base64_2"
        mock_engine.detect_and_embed.return_value = [det2]

        self.worker._process_frame(MagicMock())
        # record_detection should NOT be called again (no duplicate queue item!)
        self.assertEqual(mock_record.call_count, 1)
        # update_detection_best_shot should be called to update the single item in-place
        mock_update.assert_called_once_with(
            detection_id="det_initial_1",
            thumbnail_path="frame2_best.jpg",
            bbox=[12, 12, 105, 105],
            confidence=0.95
        )
        self.assertEqual(self.worker.unknown_tracks[0]["best_confidence"], 0.95)
        self.assertEqual(self.worker.unknown_tracks[0]["thumbnail_filename"], "frame2_best.jpg")

        # Frame 3: Same face stays in view, but lower confidence 0.72 (blurry shot)
        det3 = MagicMock()
        det3.embedding = [0.1] * 512
        det3.confidence = 0.72
        det3.bbox = [10, 10, 100, 100]
        det3.thumbnail_filename = "frame3.jpg"
        det3.thumbnail_base64 = "base64_3"
        mock_engine.detect_and_embed.return_value = [det3]

        self.worker._process_frame(MagicMock())
        # Neither record_detection nor update_detection_best_shot should be called
        self.assertEqual(mock_record.call_count, 1)
        self.assertEqual(mock_update.call_count, 1)
        # Track still retains the highest confidence 0.95 shot
        self.assertEqual(self.worker.unknown_tracks[0]["best_confidence"], 0.95)

if __name__ == "__main__":
    unittest.main()
