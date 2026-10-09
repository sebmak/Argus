import unittest
import os
import shutil
from pathlib import Path
try:
    import numpy as np
except ImportError:
    from app.db.database import np

# Set test environment paths
os.environ["DATA_DIR"] = "./data_test"
os.environ["FACE_ENGINE_MOCK"] = "true"

from app.config import settings
from app.db.database import (
    init_db,
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
    purge_low_confidence_detections,
    update_detection_best_shot,
    deduplicate_unrecognized_detections,
    get_system_stats,
    verify_user_credentials
)

# ==============================================================================
# Rules for TestDatabaseAndAPIIntegration:
# 1. Tests SQLite data layer, household member CRUD, embedding centroids, detection inbox, and deduplication best-shots.
# 2. Member variables must be declared at the top of the class.
# 3. Uses isolated temporary directories for test databases and cleans up afterwards.
# ==============================================================================
class TestDatabaseAndAPIIntegration(unittest.TestCase):
    test_dir: Path

    @classmethod
    def setUpClass(cls):
        os.environ["DATA_DIR"] = "./data_test"
        os.environ["CONFIG_DIR"] = "./data_test"
        cls.test_dir = Path("./data_test")
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir, ignore_errors=True)
        cls.test_dir.mkdir(parents=True, exist_ok=True)
        init_db()

    @classmethod
    def tearDownClass(cls):
        # Cleanup test data directory
        test_dir = Path("./data_test")
        if test_dir.exists():
            shutil.rmtree(test_dir, ignore_errors=True)
        os.environ.pop("DATA_DIR", None)
        os.environ.pop("CONFIG_DIR", None)

    def test_default_admin_user(self):
        user = verify_user_credentials("admin", "admin123")
        self.assertIsNotNone(user)
        self.assertEqual(user["username"], "admin")

    def test_person_crud_and_samples(self):
        # 1. Create person
        person = create_person("Sebastian Makinson", "Test household member")
        self.assertIsNotNone(person["id"])
        self.assertEqual(person["name"], "Sebastian Makinson")

        # 2. Add sample embedding
        sample_vec = np.random.randn(512).astype(np.float32)
        sample_vec = sample_vec / np.linalg.norm(sample_vec)
        sample_id = add_face_sample(
            person_id=person["id"],
            embedding=sample_vec,
            thumbnail_path="test_thumb.jpg",
            source="test_source"
        )
        self.assertTrue(sample_id.startswith("s_"))

        # 3. Retrieve person details
        details = get_person_by_id(person["id"])
        self.assertEqual(details["sample_count"], 1)

        # 4. Check active embeddings centroid computation
        active = get_all_active_embeddings()
        self.assertIn(person["id"], active)
        self.assertIsNotNone(active[person["id"]]["centroid"])
        self.assertEqual(len(active[person["id"]]["embeddings"]), 1)

        # 5. Delete person
        deleted = delete_person(person["id"])
        self.assertTrue(deleted)
        self.assertIsNone(get_person_by_id(person["id"]))

    def test_detection_queue_and_assignment(self):
        # 1. Create test person
        person = create_person("Sarah", "Resident")

        # 2. Record unrecognized detection
        det_id = record_detection(
            thumbnail_path="unknown_crop.jpg",
            bbox=[50, 50, 150, 150],
            camera_id="porch_cam",
            status="unrecognized"
        )
        self.assertTrue(det_id.startswith("det_"))

        # 3. Retrieve unrecognized list
        queue = get_unrecognized_detections()
        found = any(d["id"] == det_id for d in queue)
        self.assertTrue(found)

        # 4. Assign detection to person
        assigned = assign_detection_to_person(det_id, person["id"])
        self.assertTrue(assigned)

        # 5. Verify it is no longer in unrecognized queue
        queue_after = get_unrecognized_detections()
        found_after = any(d["id"] == det_id for d in queue_after)
        self.assertFalse(found_after)

        # 6. Check system stats
        stats = get_system_stats()
        self.assertGreaterEqual(stats["total_persons"], 1)

    def test_purge_low_confidence_detections(self):
        # Record 1 low-confidence detection (0.42) and 1 high-confidence detection (0.85)
        d_low = record_detection(
            thumbnail_path="low_conf.jpg",
            bbox=[10, 10, 50, 50],
            camera_id="cam1",
            status="unrecognized",
            confidence=0.42
        )
        d_high = record_detection(
            thumbnail_path="high_conf.jpg",
            bbox=[10, 10, 80, 80],
            camera_id="cam1",
            status="unrecognized",
            confidence=0.85
        )

        # Purge detections below 0.65
        res = purge_low_confidence_detections(min_confidence=0.65)
        self.assertGreaterEqual(res["deleted_count"], 1)

        # Verify low-confidence detection is gone, but high-confidence remains
        queue = get_unrecognized_detections()
        self.assertFalse(any(d["id"] == d_low for d in queue))
        self.assertTrue(any(d["id"] == d_high for d in queue))

    def test_update_detection_best_shot(self):
        d_id = record_detection(
            thumbnail_path="shot1.jpg",
            bbox=[10, 10, 50, 50],
            camera_id="cam_porch",
            status="unrecognized",
            confidence=0.68
        )

        success = update_detection_best_shot(
            detection_id=d_id,
            thumbnail_path="shot2_best.jpg",
            bbox=[12, 14, 55, 60],
            confidence=0.96
        )
        self.assertTrue(success)

        queue = get_unrecognized_detections()
        updated = next((d for d in queue if d["id"] == d_id), None)
        self.assertIsNotNone(updated)
        self.assertEqual(updated["thumbnail_path"], "shot2_best.jpg")
        self.assertEqual(updated["confidence"], 0.96)

    def test_deduplicate_unrecognized_detections(self):
        # Insert 3 consecutive unrecognized frames on the same camera
        d1 = record_detection(
            thumbnail_path="burst_1.jpg",
            bbox=[10, 10, 50, 50],
            camera_id="cam_driveway",
            status="unrecognized",
            confidence=0.71
        )
        d2 = record_detection(
            thumbnail_path="burst_2.jpg",
            bbox=[10, 10, 50, 50],
            camera_id="cam_driveway",
            status="unrecognized",
            confidence=0.94
        )
        d3 = record_detection(
            thumbnail_path="burst_3.jpg",
            bbox=[10, 10, 50, 50],
            camera_id="cam_driveway",
            status="unrecognized",
            confidence=0.76
        )

        res = deduplicate_unrecognized_detections(time_window_seconds=30)
        self.assertGreaterEqual(res["deleted_count"], 2)

        # Confirm the single kept detection is the highest-confidence shot (d2 with 0.94)
        queue = get_unrecognized_detections()
        kept_driveway = [d for d in queue if d["camera_id"] == "cam_driveway"]
        self.assertEqual(len(kept_driveway), 1)
        self.assertEqual(kept_driveway[0]["id"], d2)
        self.assertEqual(kept_driveway[0]["confidence"], 0.94)

if __name__ == "__main__":
    unittest.main()
