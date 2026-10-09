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
    get_system_stats,
    verify_user_credentials
)

# ==============================================================================
# Rules for TestDatabaseAndAPIIntegration:
# 1. Tests SQLite data layer, household member CRUD, embedding centroids, and detection inbox.
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

if __name__ == "__main__":
    unittest.main()
