import os
import sys
import shutil
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Graceful mocks for host environment when binary packages run in Docker
for mod in ["cv2", "httpx", "paho", "paho.mqtt", "paho.mqtt.client", "fastapi", "fastapi.security", "jose"]:
    if mod not in sys.modules:
        try:
            __import__(mod)
        except ImportError:
            sys.modules[mod] = MagicMock()

try:
    import numpy as np
except ImportError:
    from app.db.database import np

# Isolate test configuration before loading app modules
os.environ["DATA_DIR"] = "./data_test_integration"
os.environ["CONFIG_DIR"] = "./data_test_integration"
os.environ["FACE_ENGINE_MOCK"] = "true"
os.environ["WEBHOOK_ONLY_KNOWN_FACES"] = "true"
os.environ["MQTT_ONLY_KNOWN_FACES"] = "true"
os.environ["NOTIFY_ON_UNKNOWN"] = "false"

from app.config import settings
from app.db.database import (
    init_db,
    get_db,
    create_person,
    get_all_persons,
    get_person_by_id,
    delete_person,
    add_face_sample,
    get_all_active_embeddings,
    record_detection,
    get_unrecognized_detections,
    assign_detection_to_person,
    dismiss_detection,
    get_system_stats,
    verify_user_credentials,
    get_all_settings,
    update_setting,
    sync_settings_to_runtime,
    deduplicate_unrecognized_detections,
    update_detection_best_shot
)
from app.core.face_engine import FaceEngine
from app.core.webhook_parser import parse_protect_webhook, WebhookPayload
from app.core.events import dispatch_detection_event
from app.core.rtsp_worker import RtspStreamWorker
from app.db.migrations import (
    run_migrations,
    rollback_migrations,
    get_migration_status
)


# ==============================================================================
# Rules for TestEndToEndSystemIntegration:
# 1. Tests complete lifecycle: migrations, authentication, enrollment, matching,
#    notification suppression for unknown detections, inbox triage, deduplication, runtime settings,
#    and rollback safety.
# 2. Member variables must be declared at the top of the class.
# 3. Uses isolated temporary test directory and cleans up upon completion.
# ==============================================================================
class TestEndToEndSystemIntegration(unittest.TestCase):
    test_dir: Path
    engine: FaceEngine
    worker: RtspStreamWorker

    @classmethod
    def setUpClass(cls):
        cls.test_dir = Path("./data_test_integration")
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir, ignore_errors=True)
        cls.test_dir.mkdir(parents=True, exist_ok=True)
        settings.CONFIG_DIR = "./data_test_integration"
        settings.DATA_DIR = "./data_test_integration"
        init_db()

    @classmethod
    def tearDownClass(cls):
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir, ignore_errors=True)
        os.environ.pop("DATA_DIR", None)
        os.environ.pop("CONFIG_DIR", None)

    def setUp(self):
        self.engine = FaceEngine()
        self.engine.mock_mode = True
        self.engine.initialized = True
        self.worker = RtspStreamWorker()

    def test_01_database_and_admin_auth(self):
        """Verify DB migrations initialized all tables and seeded default admin."""
        status = get_migration_status()
        self.assertEqual(status["database_version"], "1.1.0")

        # Admin user authentication
        admin = verify_user_credentials("admin", "admin123")
        self.assertIsNotNone(admin)
        self.assertEqual(admin["username"], "admin")

        # Wrong password rejection
        bad_auth = verify_user_credentials("admin", "wrong_password")
        self.assertIsNone(bad_auth)

    def test_02_member_enrollment_and_centroid_computation(self):
        """Test household member creation, multi-sample enrollment, and centroid calculation."""
        person = create_person("Alice Resident", "Primary family member")
        person_id = person["id"]
        self.assertTrue(person_id.startswith("p_"))

        # Enroll 3 face samples
        base_vec = np.random.randn(512).astype(np.float32)
        base_vec = base_vec / np.linalg.norm(base_vec)

        for i in range(3):
            # Slight perturbation to simulate different angles
            noise = np.random.randn(512).astype(np.float32) * 0.05
            sample_vec = base_vec + noise
            sample_vec = sample_vec / np.linalg.norm(sample_vec)
            sample_id = add_face_sample(
                person_id=person_id,
                embedding=sample_vec,
                thumbnail_path=f"alice_thumb_{i}.jpg",
                source="protect_webhook"
            )
            self.assertTrue(sample_id.startswith("s_"))

        # Verify person stats
        details = get_person_by_id(person_id)
        self.assertEqual(details["sample_count"], 3)

        # Verify active embeddings and centroid
        active = get_all_active_embeddings()
        self.assertIn(person_id, active)
        self.assertEqual(len(active[person_id]["embeddings"]), 3)
        centroid = active[person_id]["centroid"]
        self.assertIsNotNone(centroid)
        self.assertAlmostEqual(float(np.linalg.norm(centroid)), 1.0, places=3)

    def test_03_face_recognition_engine_matching(self):
        """Test recognition engine accurately matches known member and rejects unknown face."""
        active = get_all_active_embeddings()

        # 1. Matching known person
        alice_data = [p for p in active.values() if p["name"] == "Alice Resident"][0]
        known_query = alice_data["centroid"]

        match_known = self.engine.match_face(known_query, active, similarity_threshold=0.45)
        self.assertTrue(match_known["match"])
        self.assertEqual(match_known["name"], "Alice Resident")
        self.assertGreaterEqual(match_known["similarity"], 0.85)

        # 2. Unknown face query (orthogonal vector)
        unknown_vec = np.zeros(512, dtype=np.float32)
        unknown_vec[0] = 1.0
        match_unknown = self.engine.match_face(unknown_vec, active, similarity_threshold=0.45)
        self.assertFalse(match_unknown["match"])
        self.assertEqual(match_unknown["name"], "Unknown")
        self.assertIsNone(match_unknown["person_id"])

    @patch("app.core.events.get_mqtt_client")
    @patch("app.core.events.httpx.Client")
    def test_04_notification_filtering_for_unknown_faces(self, mock_httpx_cls, mock_get_mqtt):
        """Ensure external Webhook and MQTT are strictly SUPPRESSED for unknown faces by default."""
        mock_http_client = MagicMock()
        mock_httpx_cls.return_value.__enter__.return_value = mock_http_client

        mock_mqtt_client = MagicMock()
        mock_get_mqtt.return_value = mock_mqtt_client

        # Ensure suppression flags are active
        settings.WEBHOOK_ONLY_KNOWN_FACES = True
        settings.MQTT_ONLY_KNOWN_FACES = True
        settings.NOTIFY_ON_UNKNOWN = False
        settings.RTSP_WEBHOOK_URL = "http://homeassistant.local:8123/api/webhook/face_event"
        settings.MQTT_ENABLED = True

        # CASE A: Unknown detection -> MUST NOT send Webhook or MQTT
        unknown_payload = {
            "event": "face_detection",
            "camera": "Driveway",
            "person_name": "Unknown",
            "match": False,
            "confidence": 0.88,
            "similarity": 0.20,
            "thumbnail_url": "/api/detections/unknown_1.jpg",
            "matched_person_id": None
        }
        dispatch_detection_event(unknown_payload)

        # Verify NO outgoing calls were made
        mock_http_client.post.assert_not_called()
        mock_mqtt_client.publish.assert_not_called()

        # CASE B: Known detection -> MUST dispatch Webhook and MQTT
        known_payload = {
            "event": "face_detection",
            "camera": "Front Door",
            "person_name": "Alice Resident",
            "match": True,
            "confidence": 0.95,
            "similarity": 0.89,
            "thumbnail_url": "/api/detections/alice_thumb.jpg",
            "matched_person_id": "p_alice"
        }
        dispatch_detection_event(known_payload)

        mock_http_client.post.assert_called_once()
        self.assertTrue(mock_mqtt_client.publish.called)

    @patch("app.core.rtsp_worker.dispatch_detection_event")
    @patch("app.core.rtsp_worker.face_engine")
    def test_05_rtsp_worker_unknown_suppression_and_inbox_logging(self, mock_engine, mock_dispatch):
        """Verify RTSP worker records unknown detections for triage but does not alert externally."""
        # Ensure only known faces trigger alerts
        settings.WEBHOOK_ONLY_KNOWN_FACES = True
        settings.MQTT_ONLY_KNOWN_FACES = True
        settings.NOTIFY_ON_UNKNOWN = False
        self.worker.cooldowns.clear()

        # Mock detection from frame
        mock_det = MagicMock()
        mock_det.bbox = [10, 10, 100, 100]
        mock_det.confidence = 0.82
        mock_det.embedding = np.zeros(512, dtype=np.float32)
        mock_det.thumbnail_filename = "crop_unknown_1.jpg"
        mock_engine.detect_and_embed.return_value = [mock_det]

        # Unknown match result
        mock_engine.match_face.return_value = {
            "match": False,
            "name": "Unknown",
            "person_id": None,
            "similarity": 0.12,
            "distance": 0.88
        }

        # Process frame
        self.worker._process_frame(MagicMock())

        # External event dispatcher must NOT be called for unknown face
        mock_dispatch.assert_not_called()

        # But it MUST be recorded in DB unrecognized triage inbox with accurate confidence!
        inbox = get_unrecognized_detections(limit=10)
        self.assertGreaterEqual(len(inbox), 1)
        latest = inbox[0]
        self.assertEqual(latest["status"], "unrecognized")
        self.assertAlmostEqual(latest["confidence"], 0.82, places=2)

        # CASE 2: Low-confidence unknown face (0.45 < UNKNOWN_MIN_CONFIDENCE 0.65)
        # Must be SUPPRESSED from database review inbox to prevent cluttering with non-faces!
        count_before = len(get_unrecognized_detections())
        mock_det.confidence = 0.45
        mock_det.thumbnail_filename = "crop_low_conf_noise.jpg"
        self.worker.cooldowns.clear()
        self.worker._process_frame(MagicMock())
        count_after = len(get_unrecognized_detections())
        self.assertEqual(count_after, count_before)

    def test_06_unrecognized_triage_assignment_and_dismissal(self):
        """Test assigning unknown detection to household member and dismissing false positives."""
        # 1. Record an unrecognized detection
        det_id = record_detection(
            thumbnail_path="porch_unknown.jpg",
            bbox=[10, 10, 100, 100],
            camera_id="Front Porch",
            matched_person_id=None,
            status="unrecognized"
        )
        self.assertTrue(det_id.startswith("det_"))

        # Verify it appears in unreviewed inbox
        inbox_before = get_unrecognized_detections()
        self.assertTrue(any(d["id"] == det_id for d in inbox_before))

        # Find Alice's person ID
        alice = [p for p in get_all_persons() if p["name"] == "Alice Resident"][0]

        # Assign detection to Alice
        assigned = assign_detection_to_person(detection_id=det_id, person_id=alice["id"])
        self.assertTrue(assigned)

        # Verify detection status updated and no longer in unreviewed inbox
        inbox_after = get_unrecognized_detections()
        self.assertFalse(any(d["id"] == det_id for d in inbox_after))

        # 2. Record another unrecognized detection and dismiss it
        det_id_2 = record_detection(
            thumbnail_path="gate_unknown.jpg",
            bbox=[15, 15, 110, 110],
            camera_id="Back Gate",
            matched_person_id=None,
            status="unrecognized"
        )
        self.assertTrue(det_id_2.startswith("det_"))

        dismissed = dismiss_detection(det_id_2)
        self.assertTrue(dismissed)

        # Verify it also no longer appears in unrecognized inbox
        inbox_dismissed = get_unrecognized_detections()
        self.assertFalse(any(d["id"] == det_id_2 for d in inbox_dismissed))

    def test_07_dynamic_settings_synchronization(self):
        """Test dynamic settings updates are reflected immediately in memory without server restart."""
        # 1. Update mqtt_only_known_faces
        update_setting("mqtt_only_known_faces", "false")
        sync_settings_to_runtime()
        self.assertFalse(settings.MQTT_ONLY_KNOWN_FACES)

        # 2. Toggle back to true
        update_setting("mqtt_only_known_faces", "true")
        sync_settings_to_runtime()
        self.assertTrue(settings.MQTT_ONLY_KNOWN_FACES)

        # 3. Update similarity threshold
        update_setting("similarity_threshold", "0.52")
        sync_settings_to_runtime()
        self.assertAlmostEqual(settings.SIMILARITY_THRESHOLD, 0.52, places=2)

    def test_08_schema_rollback_and_recovery(self):
        """Test non-destructive migration rollback to 1.0.0 and subsequent restoration to 1.1.0."""
        # Rollback to 1.0.0
        res_down = rollback_migrations("1.0.0")
        self.assertEqual(res_down["status"], "success")
        self.assertEqual(res_down["current_app_version"], "1.0.0")
        self.assertIn("dynamic_settings_and_telemetry", res_down["rolled_back"])

        # Verify core persons remain safe after rollback
        persons = get_all_persons()
        alice = [p for p in persons if p["name"] == "Alice Resident"]
        self.assertEqual(len(alice), 1)

        # Roll forward back to 1.1.0
        res_up = run_migrations("1.1.0")
        self.assertEqual(res_up["status"], "success")
        self.assertEqual(res_up["current_app_version"], "1.1.0")
        self.assertIn("dynamic_settings_and_telemetry", res_up["applied"])

    def test_09_unrecognized_deduplication_and_best_shot(self):
        """Test deduplicating burst unrecognized frames into highest confidence best-shots."""
        # 1. Insert multiple unknown frames recorded within the same timeframe on Backyard camera
        id1 = record_detection(
            thumbnail_path="unk_shot_1.jpg",
            bbox=[15, 15, 80, 80],
            camera_id="Backyard",
            status="unrecognized",
            confidence=0.69
        )
        id2 = record_detection(
            thumbnail_path="unk_shot_2_best.jpg",
            bbox=[18, 18, 90, 90],
            camera_id="Backyard",
            status="unrecognized",
            confidence=0.97
        )
        id3 = record_detection(
            thumbnail_path="unk_shot_3.jpg",
            bbox=[15, 15, 80, 80],
            camera_id="Backyard",
            status="unrecognized",
            confidence=0.73
        )

        # 2. Run deduplication
        dedup_res = deduplicate_unrecognized_detections(time_window_seconds=20)
        self.assertGreaterEqual(dedup_res["deleted_count"], 2)

        # 3. Verify Backyard has exactly 1 remaining detection with highest confidence (0.97)
        queue = get_unrecognized_detections()
        backyard_queue = [d for d in queue if d["camera_id"] == "Backyard"]
        self.assertEqual(len(backyard_queue), 1)
        self.assertEqual(backyard_queue[0]["id"], id2)
        self.assertEqual(backyard_queue[0]["thumbnail_path"], "unk_shot_2_best.jpg")
        self.assertEqual(backyard_queue[0]["confidence"], 0.97)


if __name__ == "__main__":
    unittest.main()
