import unittest
import sys
import tempfile
import os
from pathlib import Path
from unittest.mock import MagicMock

# Graceful mocks for host environment
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
        def dict(self, **kwargs):
            return self.__dict__
    pyd_mock = MagicMock()
    pyd_mock.BaseModel = DummyBaseModel
    pyd_mock.BaseSettings = DummyBaseModel
    pyd_mock.Field = lambda *args, **kwargs: None
    sys.modules["pydantic"] = pyd_mock
    sys.modules["pydantic_settings"] = pyd_mock

from app.config import settings
from app.db.database import (
    init_db,
    seed_default_settings,
    get_setting,
    get_all_settings,
    save_settings_bulk,
    sync_settings_to_runtime,
    get_system_stats
)

# Rules for TestSettingsManagement class:
# 1. Variables and class attributes must be declared at the top of the class.
# 2. Test lifecycle methods set up isolated temporary sqlite database in setUpClass and clean up in tearDownClass.
# 3. Validates database persistence, type conversion, and live runtime memory synchronization.
class TestSettingsManagement(unittest.TestCase):
    test_dir: Path = Path("data/test_settings_data")

    @classmethod
    def setUpClass(cls):
        cls.test_dir.mkdir(parents=True, exist_ok=True)
        settings.CONFIG_DIR = str(cls.test_dir)
        settings.DATA_DIR = str(cls.test_dir)
        init_db()

    @classmethod
    def tearDownClass(cls):
        import shutil
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_seed_and_get_all_settings(self):
        seed_default_settings()
        all_settings = get_all_settings()

        self.assertIn("detection_confidence", all_settings)
        self.assertIn("similarity_threshold", all_settings)
        self.assertIn("notification_threshold", all_settings)
        self.assertIn("notify_on_unknown", all_settings)
        self.assertIn("unknown_min_confidence", all_settings)
        self.assertIn("rtsp_url", all_settings)
        self.assertIn("rtsp_motion_gating_enabled", all_settings)
        self.assertIn("rtsp_motion_threshold", all_settings)
        self.assertIn("webhook_only_known_faces", all_settings)
        self.assertIn("mqtt_enabled", all_settings)

        self.assertIsInstance(all_settings["notification_threshold"], float)
        self.assertIsInstance(all_settings["notify_on_unknown"], bool)
        self.assertIsInstance(all_settings["unknown_min_confidence"], float)
        self.assertIsInstance(all_settings["rtsp_motion_gating_enabled"], bool)
        self.assertIsInstance(all_settings["rtsp_motion_threshold"], float)
        self.assertIsInstance(all_settings["webhook_only_known_faces"], bool)
        self.assertIsInstance(all_settings["mqtt_only_known_faces"], bool)

    def test_save_settings_bulk_and_runtime_sync(self):
        updates = {
            "detection_confidence": 0.65,
            "similarity_threshold": 0.52,
            "notification_threshold": 0.70,
            "notify_on_unknown": False,
            "unknown_min_confidence": 0.80,
            "rtsp_camera_name": "Backyard Gate",
            "rtsp_fps": 4.5,
            "rtsp_cooldown_seconds": 60,
            "rtsp_motion_gating_enabled": False,
            "rtsp_motion_threshold": 0.025,
            "rtsp_webhook_url": "http://192.168.1.100:8123/webhook/gate",
            "webhook_only_known_faces": True,
            "mqtt_enabled": True,
            "mqtt_host": "192.168.1.200",
            "mqtt_port": 1883,
            "mqtt_topic": "home/cameras/gate",
            "mqtt_only_known_faces": True
        }

        result = save_settings_bulk(updates)

        # Verify returned dictionary
        self.assertEqual(result["detection_confidence"], 0.65)
        self.assertEqual(result["similarity_threshold"], 0.52)
        self.assertEqual(result["notification_threshold"], 0.70)
        self.assertFalse(result["notify_on_unknown"])
        self.assertEqual(result["unknown_min_confidence"], 0.80)
        self.assertEqual(result["rtsp_camera_name"], "Backyard Gate")
        self.assertEqual(result["rtsp_fps"], 4.5)
        self.assertEqual(result["rtsp_cooldown_seconds"], 60)
        self.assertFalse(result["rtsp_motion_gating_enabled"])
        self.assertEqual(result["rtsp_motion_threshold"], 0.025)
        self.assertEqual(result["rtsp_webhook_url"], "http://192.168.1.100:8123/webhook/gate")
        self.assertTrue(result["webhook_only_known_faces"])
        self.assertTrue(result["mqtt_enabled"])
        self.assertEqual(result["mqtt_host"], "192.168.1.200")
        self.assertEqual(result["mqtt_topic"], "home/cameras/gate")
        self.assertTrue(result["mqtt_only_known_faces"])

        # Verify active runtime settings singleton was immediately updated
        self.assertEqual(settings.DETECTION_CONFIDENCE, 0.65)
        self.assertEqual(settings.SIMILARITY_THRESHOLD, 0.52)
        self.assertEqual(settings.NOTIFICATION_THRESHOLD, 0.70)
        self.assertFalse(settings.NOTIFY_ON_UNKNOWN)
        self.assertEqual(settings.UNKNOWN_MIN_CONFIDENCE, 0.80)
        self.assertEqual(settings.RTSP_CAMERA_NAME, "Backyard Gate")
        self.assertEqual(settings.RTSP_FPS, 4.5)
        self.assertEqual(settings.RTSP_COOLDOWN_SECONDS, 60)
        self.assertFalse(settings.RTSP_MOTION_GATING_ENABLED)
        self.assertEqual(settings.RTSP_MOTION_THRESHOLD, 0.025)
        self.assertEqual(settings.RTSP_WEBHOOK_URL, "http://192.168.1.100:8123/webhook/gate")
        self.assertTrue(settings.WEBHOOK_ONLY_KNOWN_FACES)
        self.assertTrue(settings.MQTT_ENABLED)
        self.assertEqual(settings.MQTT_HOST, "192.168.1.200")
        self.assertEqual(settings.MQTT_TOPIC, "home/cameras/gate")
        self.assertTrue(settings.MQTT_ONLY_KNOWN_FACES)

    def test_env_var_override_sync_on_boot(self):
        os.environ["NOTIFY_ON_UNKNOWN"] = "false"
        os.environ["WEBHOOK_ONLY_KNOWN_FACES"] = "true"
        os.environ["MQTT_ONLY_KNOWN_FACES"] = "true"
        os.environ["FACE_DETECTOR_TYPE"] = "scrfd"
        os.environ["DET_SIZE"] = "640"
        os.environ["ORT_NUM_THREADS"] = "4"

        seed_default_settings()

        self.assertFalse(settings.NOTIFY_ON_UNKNOWN)
        self.assertTrue(settings.WEBHOOK_ONLY_KNOWN_FACES)
        self.assertTrue(settings.MQTT_ONLY_KNOWN_FACES)
        self.assertEqual(settings.FACE_DETECTOR_TYPE, "scrfd")
        self.assertEqual(settings.DET_SIZE, 640)
        self.assertEqual(settings.ORT_NUM_THREADS, 4)

        self.assertEqual(get_setting("notify_on_unknown"), "false")
        self.assertEqual(get_setting("webhook_only_known_faces"), "true")
        self.assertEqual(get_setting("mqtt_only_known_faces"), "true")
        self.assertEqual(get_setting("face_detector_type"), "scrfd")
        self.assertEqual(get_setting("det_size"), "640")
        self.assertEqual(get_setting("ort_num_threads"), "4")

        # Clean up
        del os.environ["FACE_DETECTOR_TYPE"]
        del os.environ["DET_SIZE"]
        del os.environ["ORT_NUM_THREADS"]
        save_settings_bulk({
            "face_detector_type": "yolov8_face",
            "det_size": 320,
            "ort_num_threads": 8
        })

    def test_det_size_and_threads_runtime_sync_and_stats(self):
        # Update resolution and thread count
        save_settings_bulk({
            "det_size": 480,
            "ort_num_threads": 16,
            "face_detector_type": "yolov8_face"
        })

        # Verify active runtime settings singleton immediately updated
        self.assertEqual(settings.DET_SIZE, 480)
        self.assertEqual(settings.ORT_NUM_THREADS, 16)
        self.assertEqual(settings.FACE_DETECTOR_TYPE, "yolov8_face")

        # Verify get_system_stats returns the updated values
        stats = get_system_stats()
        self.assertEqual(stats["det_size"], 480)
        self.assertEqual(stats["ort_num_threads"], 16)
        self.assertEqual(stats["face_detector_type"], "yolov8_face")

if __name__ == "__main__":
    unittest.main()
