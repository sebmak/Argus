import unittest
try:
    import numpy as np
except ImportError:
    from app.db.database import np

from app.core.face_engine import FaceEngine

# ==============================================================================
# Rules for TestFaceEngineMath:
# 1. Tests vector arithmetic, cosine similarity, known member matching, and unknown thresholds.
# 2. Member variables must be declared at the top of the class.
# 3. Compatible with both native NumPy and pure-Python vector fallback implementations.
# ==============================================================================
class TestFaceEngineMath(unittest.TestCase):
    engine: FaceEngine

    def setUp(self):
        self.engine = FaceEngine()
        self.engine.mock_mode = True
        self.engine.initialized = True

    def test_cosine_similarity_identical(self):
        vec = np.random.randn(512).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        sim = self.engine.cosine_similarity(vec, vec)
        self.assertAlmostEqual(sim, 1.0, places=4)

    def test_cosine_similarity_orthogonal(self):
        vec_a = np.zeros(512, dtype=np.float32)
        vec_b = np.zeros(512, dtype=np.float32)
        vec_a[0] = 1.0
        vec_b[1] = 1.0
        sim = self.engine.cosine_similarity(vec_a, vec_b)
        self.assertAlmostEqual(sim, 0.0, places=4)

    def test_cosine_similarity_opposite(self):
        vec_a = np.random.randn(512).astype(np.float32)
        vec_a = vec_a / np.linalg.norm(vec_a)
        vec_b = -vec_a
        sim = self.engine.cosine_similarity(vec_a, vec_b)
        self.assertAlmostEqual(sim, -1.0, places=4)

    def test_match_face_known_person(self):
        # Generate target embedding
        target_vec = np.random.randn(512).astype(np.float32)
        target_vec = target_vec / np.linalg.norm(target_vec)

        # Create known persons database
        known_persons = {
            "p_001": {
                "name": "Sebastian",
                "embeddings": [target_vec],
                "centroid": target_vec
            },
            "p_002": {
                "name": "Alice",
                "embeddings": [np.random.randn(512).astype(np.float32)],
                "centroid": np.random.randn(512).astype(np.float32)
            }
        }

        match = self.engine.match_face(target_vec, known_persons, similarity_threshold=0.45)
        self.assertTrue(match["match"])
        self.assertEqual(match["name"], "Sebastian")
        self.assertEqual(match["person_id"], "p_001")
        self.assertGreaterEqual(match["similarity"], 0.99)

    def test_match_face_unknown_person(self):
        # Generate orthogonal vector
        query_vec = np.zeros(512, dtype=np.float32)
        query_vec[0] = 1.0

        stored_vec = np.zeros(512, dtype=np.float32)
        stored_vec[1] = 1.0

        known_persons = {
            "p_001": {
                "name": "Sebastian",
                "embeddings": [stored_vec],
                "centroid": stored_vec
            }
        }

        match = self.engine.match_face(query_vec, known_persons, similarity_threshold=0.45)
        self.assertFalse(match["match"])
        self.assertEqual(match["name"], "Unknown")
        self.assertIsNone(match["person_id"])

if __name__ == "__main__":
    unittest.main()
