import unittest
import sys
from typing import List, Dict, Any, Tuple
from unittest.mock import MagicMock

try:
    import numpy as np
except ImportError:
    from app.db.database import np

try:
    import cv2
except ImportError:
    cv2 = None

from app.core.yolov8_face import YOLOv8FaceDetector
from app.core.face_engine import FaceEngine
from app.config import settings

def is_native_environment() -> bool:
    """Returns True only when native binary OpenCV and multi-dimensional NumPy are available."""
    cv2_mod = sys.modules.get("cv2")
    if cv2_mod is None or isinstance(cv2_mod, MagicMock) or hasattr(cv2_mod, "_mock_return_value"):
        return False
    numpy_mod = sys.modules.get("numpy")
    if numpy_mod is None or isinstance(numpy_mod, MagicMock) or not hasattr(numpy_mod, "__version__"):
        return False
    return True

# ==============================================================================
# Rules for TestYOLOv8FacePreprocessing:
# 1. Tests letterbox preprocessing, aspect ratio scaling, padding, and tensor normalization.
# 2. Member variables must be declared at the top of the class.
# 3. Compatible with both native NumPy and mock environments.
# ==============================================================================
class TestYOLOv8FacePreprocessing(unittest.TestCase):
    detector: YOLOv8FaceDetector

    def setUp(self):
        if not is_native_environment():
            self.skipTest("Native cv2 and numpy required for matrix preprocessing (available in Docker)")
        self.detector = YOLOv8FaceDetector()

    def test_letterbox_landscape_shape(self):
        # Landscape image: 720x1280
        img = np.zeros((720, 1280, 3), dtype=np.uint8)
        blob, scale, pad = self.detector.preprocess(img, target_shape=(640, 640))

        self.assertEqual(blob.shape, (1, 3, 640, 640))
        # Scale is 640 / 1280 = 0.5
        self.assertAlmostEqual(scale, 0.5, places=3)
        # Height after scaling: 720 * 0.5 = 360. Pad = (640 - 360) / 2 = 140
        self.assertEqual(pad[0], 0.0)  # dw
        self.assertAlmostEqual(pad[1], 140.0, delta=1.0)  # dh

    def test_letterbox_portrait_shape(self):
        # Portrait image: 1280x720
        img = np.zeros((1280, 720, 3), dtype=np.uint8)
        blob, scale, pad = self.detector.preprocess(img, target_shape=(640, 640))

        self.assertEqual(blob.shape, (1, 3, 640, 640))
        # Scale is 640 / 1280 = 0.5
        self.assertAlmostEqual(scale, 0.5, places=3)
        # Width after scaling: 720 * 0.5 = 360. Pad = (640 - 360) / 2 = 140
        self.assertAlmostEqual(pad[0], 140.0, delta=1.0)  # dw
        self.assertEqual(pad[1], 0.0)  # dh

    def test_tensor_normalization_range(self):
        img = np.ones((480, 640, 3), dtype=np.uint8) * 255
        blob, _, _ = self.detector.preprocess(img, target_shape=(640, 640))

        self.assertAlmostEqual(float(blob.max()), 1.0, places=3)
        self.assertGreaterEqual(float(blob.min()), 0.0)

# ==============================================================================
# Rules for TestYOLOv8FacePostprocessing:
# 1. Tests raw output tensor decoding, confidence filtering, OpenCV NMS, and landmark un-scaling.
# 2. Member variables must be declared at the top of the class.
# 3. Validates both 15-channel and 20-channel YOLO face prediction layouts.
# ==============================================================================
class TestYOLOv8FacePostprocessing(unittest.TestCase):
    detector: YOLOv8FaceDetector

    def setUp(self):
        if not is_native_environment():
            self.skipTest("Native cv2 and numpy required for tensor decoding (available in Docker)")
        self.detector = YOLOv8FaceDetector(conf_threshold=0.50, iou_threshold=0.45)

    def test_postprocess_15_channel_format(self):
        # Shape: (1, 15, 8400)
        raw = np.zeros((1, 15, 8400), dtype=np.float32)

        # Anchor 10: High confidence face at center (cx=320, cy=320, w=100, h=100, score=0.92)
        raw[0, 0, 10] = 320.0  # cx
        raw[0, 1, 10] = 320.0  # cy
        raw[0, 2, 10] = 100.0  # w
        raw[0, 3, 10] = 100.0  # h
        raw[0, 4, 10] = 0.92   # score
        # 5 Landmarks: [left_eye, right_eye, nose, left_mouth, right_mouth]
        raw[0, 5, 10] = 300.0  # le_x
        raw[0, 6, 10] = 300.0  # le_y
        raw[0, 7, 10] = 340.0  # re_x
        raw[0, 8, 10] = 300.0  # re_y
        raw[0, 9, 10] = 320.0  # nose_x
        raw[0, 10, 10] = 320.0 # nose_y
        raw[0, 11, 10] = 305.0 # lm_x
        raw[0, 12, 10] = 340.0 # lm_y
        raw[0, 13, 10] = 335.0 # rm_x
        raw[0, 14, 10] = 340.0 # rm_y

        # Anchor 20: Low confidence detection (should be filtered out by conf_threshold)
        raw[0, 0, 20] = 100.0
        raw[0, 1, 20] = 100.0
        raw[0, 2, 20] = 50.0
        raw[0, 3, 20] = 50.0
        raw[0, 4, 20] = 0.25  # < 0.50

        results = self.detector.postprocess(
            raw,
            orig_shape=(640, 640),
            scale=1.0,
            pad=(0.0, 0.0),
            conf_threshold=0.50
        )

        self.assertEqual(len(results), 1)
        det = results[0]
        self.assertAlmostEqual(det["score"], 0.92, places=2)
        # cx=320, cy=320, w=100, h=100 => x1=270, y1=270, x2=370, y2=370
        self.assertEqual(det["bbox"], [270, 270, 370, 370])
        self.assertEqual(len(det["kps"]), 5)
        # Nose keypoint at [320, 320]
        self.assertEqual(det["kps"][2], [320.0, 320.0])

    def test_postprocess_nms_suppression(self):
        # Two heavily overlapping detections with different scores
        raw = np.zeros((1, 15, 8400), dtype=np.float32)

        # Detection A (score 0.90)
        raw[0, 0, 1] = 200.0
        raw[0, 1, 1] = 200.0
        raw[0, 2, 1] = 80.0
        raw[0, 3, 1] = 80.0
        raw[0, 4, 1] = 0.90

        # Detection B (score 0.70, almost identical box)
        raw[0, 0, 2] = 202.0
        raw[0, 1, 2] = 201.0
        raw[0, 2, 2] = 80.0
        raw[0, 3, 2] = 80.0
        raw[0, 4, 2] = 0.70

        results = self.detector.postprocess(
            raw,
            orig_shape=(640, 640),
            scale=1.0,
            pad=(0.0, 0.0),
            conf_threshold=0.50,
            iou_threshold=0.45
        )

        # NMS should suppress the lower scoring overlapping detection
        self.assertEqual(len(results), 1)
        self.assertAlmostEqual(results[0]["score"], 0.90, places=2)

# ==============================================================================
# Rules for TestFaceEngineDetectorSwitching:
# 1. Tests runtime toggling of detector engine between 'yolov8_face' and 'scrfd'.
# 2. Member variables must be declared at the top of the class.
# 3. Ensures graceful fallback to mock mode or secondary detector when model weights are unmounted.
# ==============================================================================
class TestFaceEngineDetectorSwitching(unittest.TestCase):
    engine: FaceEngine

    def setUp(self):
        self.engine = FaceEngine()
        self.engine.mock_mode = True
        self.engine.initialized = True

    def test_default_detector_type(self):
        self.assertEqual(self.engine.detector_type, "yolov8_face")

    def test_switch_detector_type(self):
        self.engine.set_detector_type("scrfd")
        self.assertEqual(self.engine.detector_type, "scrfd")

        self.engine.set_detector_type("yolov8_face")
        self.assertEqual(self.engine.detector_type, "yolov8_face")

    def test_mock_detect_and_embed_returns_valid_result(self):
        dummy_input = [0.0] * 512
        results = self.engine.detect_and_embed(dummy_input)

        self.assertGreaterEqual(len(results), 1)
        res = results[0]
        self.assertEqual(len(res.bbox), 4)
        self.assertEqual(len(res.embedding), 512)
        self.assertGreaterEqual(res.confidence, 0.5)

if __name__ == "__main__":
    unittest.main()
