import unittest
import tempfile
import os
import shutil
from pathlib import Path
try:
    from fastapi.testclient import TestClient
    from app.main import app
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    TestClient = None
    app = None

from typing import Any
from app.config import settings
from app.db.database import (
    init_db,
    record_event_log,
    get_event_logs,
    clear_event_logs,
    get_event_log_summary
)

# ==============================================================================
# Rules for TestEventLogs:
# 1. Variables and test fixtures must be placed at the top of the class.
# 2. Uses an isolated temporary test database to avoid mutating production data.
# 3. Tests recording, filtering, pagination, summary calculations, and REST endpoints.
# ==============================================================================
class TestEventLogs(unittest.TestCase):
    temp_dir: str
    client: Any = None

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="test_events_")
        settings.DATA_DIR = Path(cls.temp_dir)
        init_db()
        cls.client = TestClient(app) if HAS_FASTAPI else None

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def setUp(self):
        clear_event_logs()

    def test_record_and_retrieve_event_logs(self):
        """Test recording events across categories and retrieving them."""
        # 1. Record motion event
        id1 = record_event_log(
            level="info",
            category="motion",
            event_type="motion_active",
            message="Camera 'Front Porch' detected motion (exited idle mode)",
            details={"camera": "Front Porch", "ratio": 0.045}
        )
        self.assertTrue(id1.startswith("evt_"))

        # 2. Record idle transition event
        id2 = record_event_log(
            level="info",
            category="motion",
            event_type="motion_idle",
            message="Camera 'Front Porch' entered idle mode (motionless)",
            details={"camera": "Front Porch", "hangover": 2.5}
        )
        self.assertTrue(id2.startswith("evt_"))

        # 3. Record detection event
        id3 = record_event_log(
            level="success",
            category="detection",
            event_type="detection_matched",
            message="Face Recognized: 'Alice' (Household, 92.5%) on Front Porch",
            details={"person_name": "Alice", "similarity": 0.925}
        )
        self.assertTrue(id3.startswith("evt_"))

        # 4. Record error event
        id4 = record_event_log(
            level="error",
            category="error",
            event_type="rtsp_error",
            message="RTSP stream disconnected unexpectedly",
            details={"error": "Connection reset by peer"}
        )
        self.assertTrue(id4.startswith("evt_"))

        # 5. Fetch all logs
        res = get_event_logs(limit=10)
        self.assertEqual(res["total"], 4)
        self.assertEqual(len(res["logs"]), 4)

        # 6. Filter by category
        motion_logs = get_event_logs(category="motion")
        self.assertEqual(motion_logs["total"], 2)
        for log in motion_logs["logs"]:
            self.assertEqual(log["category"], "motion")

        # 7. Filter by level
        error_logs = get_event_logs(level="error")
        self.assertEqual(error_logs["total"], 1)
        self.assertEqual(error_logs["logs"][0]["event_type"], "rtsp_error")

        # 8. Keyword search
        search_res = get_event_logs(search="Alice")
        self.assertEqual(search_res["total"], 1)
        self.assertIn("Alice", search_res["logs"][0]["message"])

    def test_event_summary_statistics(self):
        """Test calculation of operational summary telemetry."""
        record_event_log("info", "motion", "motion_active", "Motion active")
        record_event_log("info", "motion", "motion_idle", "Motion idle")
        record_event_log("success", "detection", "detection_matched", "Matched Alice")
        record_event_log("info", "webhook", "webhook_broadcast", "Broadcast sent")
        record_event_log("error", "error", "test_error", "Error occurred")

        summary = get_event_log_summary()
        self.assertEqual(summary["total_events"], 5)
        self.assertEqual(summary["error_count_24h"], 1)
        self.assertEqual(summary["motion_transitions_today"], 2)
        self.assertEqual(summary["detections_today"], 1)
        self.assertEqual(summary["broadcasts_today"], 1)

    def test_api_endpoints(self):
        """Test REST API endpoints for event log listing, summary, and clearing."""
        if not HAS_FASTAPI or self.client is None:
            self.skipTest("FastAPI not installed on test host")

        # Log in to get session cookie
        login_res = self.client.post("/api/v1/auth/login", data={"username": "admin", "password": "admin123"})
        self.assertEqual(login_res.status_code, 200)

        record_event_log("info", "motion", "motion_idle", "Camera Front Door entered idle mode")
        record_event_log("success", "detection", "detection_matched", "Face recognized: Bob")

        # GET /api/v1/events/logs
        res = self.client.get("/api/v1/events/logs?limit=50")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("logs", data)
        self.assertGreaterEqual(data["total"], 2)

        # GET /api/v1/events/summary
        sum_res = self.client.get("/api/v1/events/summary")
        self.assertEqual(sum_res.status_code, 200)
        sum_data = sum_res.json()
        self.assertIn("total_events", sum_data)
        self.assertIn("motion_transitions_today", sum_data)

        # GET /api/v1/events/export
        exp_res = self.client.get("/api/v1/events/export")
        self.assertEqual(exp_res.status_code, 200)
        self.assertEqual(exp_res.headers["content-type"], "application/json")

        # DELETE /api/v1/events/logs
        del_res = self.client.delete("/api/v1/events/logs")
        self.assertEqual(del_res.status_code, 200)
        del_data = del_res.json()
        self.assertEqual(del_data["status"], "success")

        # After clearing, only the "logs_cleared" system log remains
        after_res = self.client.get("/api/v1/events/logs")
        self.assertEqual(after_res.status_code, 200)
        self.assertEqual(after_res.json()["total"], 1)
        self.assertEqual(after_res.json()["logs"][0]["event_type"], "logs_cleared")

if __name__ == "__main__":
    unittest.main()
