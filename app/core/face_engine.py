import os
import base64
import logging
import uuid
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
try:
    import cv2
except ImportError:
    cv2 = None

try:
    import numpy as np
except ImportError:
    from ..db.database import np

from ..config import settings
from .yolov8_face import YOLOv8FaceDetector, ensure_yolo_face_model

logger = logging.getLogger(__name__)

# ==============================================================================
# Rules for FaceDetectionResult:
# 1. Represents an individual detected face box, embedding, confidence, and crop.
# 2. Member variables must be declared at the top of the class.
# ==============================================================================
class FaceDetectionResult:
    bbox: List[int]
    confidence: float
    embedding: np.ndarray
    landmarks: List[List[float]]
    thumbnail_base64: str
    thumbnail_filename: str

    def __init__(
        self,
        bbox: List[int],
        confidence: float,
        embedding: np.ndarray,
        landmarks: Optional[List[List[float]]] = None,
        thumbnail_base64: str = "",
        thumbnail_filename: str = ""
    ):
        self.bbox = bbox  # [x1, y1, x2, y2]
        self.confidence = confidence
        self.embedding = embedding
        self.landmarks = landmarks or []
        self.thumbnail_base64 = thumbnail_base64
        self.thumbnail_filename = thumbnail_filename

# ==============================================================================
# Rules for FaceEngine:
# 1. Encapsulates dual-stage face detection (YOLOv8-Face or SCRFD), ArcFace embedding, and cosine matching.
# 2. Class and instance variables must be placed at the top of the class.
# 3. Supports mock_mode for headless test environments without host ONNX runtimes.
# 4. Supports dynamic switching between YOLOv8-Face and SCRFD with seamless ArcFace embedding extraction.
# ==============================================================================
class FaceEngine:
    app: Any = None
    yolo_detector: Optional[YOLOv8FaceDetector] = None
    detector_type: str = "yolov8_face"
    initialized: bool = False
    mock_mode: bool = False

    def __init__(self):
        self.app = None
        self.yolo_detector = None
        self.detector_type = settings.FACE_DETECTOR_TYPE
        self.initialized = False
        self.mock_mode = os.getenv("FACE_ENGINE_MOCK", "false").lower() in ("true", "1", "yes")

    def _init_yolo_detector(self):
        """Initializes YOLOv8-Face detector if enabled and model file is available."""
        if self.mock_mode:
            return

        try:
            model_file = settings.models_path / settings.YOLO_FACE_MODEL_NAME
            if not model_file.exists():
                ensure_yolo_face_model(model_file)

            if model_file.exists():
                detector = YOLOv8FaceDetector(
                    conf_threshold=settings.DETECTION_CONFIDENCE,
                    iou_threshold=0.45
                )
                detector.input_height = settings.DET_SIZE if settings.DET_SIZE >= 320 else 640
                detector.input_width = settings.DET_SIZE if settings.DET_SIZE >= 320 else 640
                if detector.load_model(str(model_file)):
                    self.yolo_detector = detector
                    logger.info("YOLOv8-Face detector successfully loaded and active!")
                else:
                    logger.warning("Could not load YOLOv8-Face session; will use SCRFD fallback.")
            else:
                logger.info(
                    "YOLOv8-Face model '%s' not found. System will use SCRFD until model is placed in %s.",
                    settings.YOLO_FACE_MODEL_NAME, settings.models_path
                )
        except Exception as e:
            logger.warning("Failed to initialize YOLOv8-Face detector (%s); will use SCRFD.", e)

    def set_detector_type(self, detector_type: str):
        """Switches between 'yolov8_face' and 'scrfd' at runtime."""
        self.detector_type = detector_type
        if detector_type == "yolov8_face" and (self.yolo_detector is None or not self.yolo_detector.initialized):
            self._init_yolo_detector()

    def update_det_size(self, new_size: int):
        """Updates runtime detector resolution for both InsightFace and YOLOv8-Face."""
        if self.app is not None and hasattr(self.app, "prepare"):
            try:
                self.app.prepare(ctx_id=-1, det_size=(new_size, new_size))
            except Exception as e:
                logger.warning("Could not re-prepare InsightFace det_size: %s", e)
        if self.yolo_detector is not None:
            self.yolo_detector.input_height = new_size
            self.yolo_detector.input_width = new_size

    def initialize(self):
        """Lazy initialization of InsightFace and YOLOv8-Face models with CPU execution provider."""
        if self.initialized:
            return

        if self.mock_mode:
            logger.info("FaceEngine initialized in MOCK mode (FACE_ENGINE_MOCK=true)")
            self.initialized = True
            return

        try:
            # Set thread environment variables before importing onnxruntime/insightface
            # This prevents 98 cores from thrashing and context switching on small CNN batches
            os.environ["OMP_NUM_THREADS"] = str(settings.ORT_NUM_THREADS)
            os.environ["OPENBLAS_NUM_THREADS"] = str(settings.ORT_NUM_THREADS)
            os.environ["MKL_NUM_THREADS"] = str(settings.ORT_NUM_THREADS)
            os.environ["VECLIB_MAXIMUM_THREADS"] = str(settings.ORT_NUM_THREADS)
            os.environ["NUMEXPR_NUM_THREADS"] = str(settings.ORT_NUM_THREADS)

            import insightface
            from insightface.app import FaceAnalysis

            models_root = str(settings.models_path)
            logger.info(
                "Initializing InsightFace (model='%s', det_size=%dx%d, threads=%d) at %s...",
                settings.FACE_MODEL_NAME, settings.DET_SIZE, settings.DET_SIZE, settings.ORT_NUM_THREADS, models_root
            )
            
            # Optimization: Load ONLY detection and recognition models!
            # Skips genderage, landmark_2d_106, and landmark_3d_68 (saves ~45% CPU cycles per frame)
            self.app = FaceAnalysis(
                name=settings.FACE_MODEL_NAME,
                root=models_root,
                allowed_modules=["detection", "recognition"],
                providers=["CPUExecutionProvider"]
            )
            # Use optimized detection resolution (e.g. 320x320 or 480x480 instead of heavy 640x640)
            self.app.prepare(ctx_id=-1, det_size=(settings.DET_SIZE, settings.DET_SIZE))
            
            # If YOLOv8-Face detector is configured, initialize it
            if self.detector_type == "yolov8_face":
                self._init_yolo_detector()

            self.initialized = True
            logger.info("Face engine successfully initialized with active detector: %s", self.detector_type)
        except Exception as e:
            logger.warning("Failed to initialize InsightFace (%s). Falling back to OpenCV / Mock engine.", e)
            self.mock_mode = True
            self.initialized = True

    def decode_image(self, image_data: str) -> np.ndarray:
        """
        Decodes base64 string or data URI into OpenCV BGR numpy array,
        and downscales oversized 4K/2K images to avoid memory and pyramid bloat.
        """
        if not image_data:
            raise ValueError("Empty image string provided")

        # Strip Data URI prefix if present
        clean_base64 = image_data
        if "," in clean_base64:
            clean_base64 = clean_base64.split(",", 1)[1]

        # Clean any whitespace or newlines
        clean_base64 = clean_base64.strip()

        try:
            img_bytes = base64.b64decode(clean_base64)
        except Exception as e:
            raise ValueError(f"Invalid base64 encoding: {e}")

        np_arr = np.frombuffer(img_bytes, np.uint8)
        img_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if img_bgr is None:
            raise ValueError("Could not decode image bytes into valid picture (format unsupported or corrupted)")

        # Downscale oversized camera snapshots (e.g. 4K/2K down to 1280px max dimension)
        if settings.MAX_IMAGE_SIZE > 0:
            h, w = img_bgr.shape[:2]
            max_dim = max(h, w)
            if max_dim > settings.MAX_IMAGE_SIZE:
                scale = settings.MAX_IMAGE_SIZE / float(max_dim)
                new_w = max(1, int(w * scale))
                new_h = max(1, int(h * scale))
                img_bgr = cv2.resize(img_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)

        return img_bgr

    def encode_image_base64(self, img_bgr: np.ndarray, ext: str = ".jpg") -> str:
        """Encodes an OpenCV image to base64 data URI string."""
        success, buffer = cv2.imencode(ext, img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
        if not success:
            return ""
        b64 = base64.b64encode(buffer).decode("utf-8")
        return f"data:image/jpeg;base64,{b64}"

    def crop_face(self, img_bgr: np.ndarray, bbox: List[int], margin_ratio: float = 0.25) -> np.ndarray:
        """
        Crops a face from image with padding margin, preserving aspect ratio.
        """
        h, w = img_bgr.shape[:2]
        x1, y1, x2, y2 = bbox

        box_w = x2 - x1
        box_h = y2 - y1

        # Calculate padded box
        pad_x = int(box_w * margin_ratio)
        pad_y = int(box_h * margin_ratio)

        new_x1 = max(0, x1 - pad_x)
        new_y1 = max(0, y1 - pad_y)
        new_x2 = min(w, x2 + pad_x)
        new_y2 = min(h, y2 + pad_y)

        cropped = img_bgr[new_y1:new_y2, new_x1:new_x2]
        if cropped.size == 0:
            return img_bgr[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]

        return cropped

    def detect_and_embed(
        self,
        img_bgr: np.ndarray,
        min_confidence: Optional[float] = None
    ) -> List[FaceDetectionResult]:
        """
        Runs face detection and ArcFace feature extraction.
        Returns list of FaceDetectionResult.
        """
        self.initialize()
        threshold = min_confidence if min_confidence is not None else settings.DETECTION_CONFIDENCE
        results: List[FaceDetectionResult] = []

        if self.mock_mode or self.app is None:
            # Fallback simulated detection: center crop or Haar Cascade if available
            shape = getattr(img_bgr, "shape", None)
            if shape and len(shape) >= 2:
                try:
                    h, w = int(shape[0]), int(shape[1])
                except (ValueError, TypeError):
                    h, w = 480, 640
            else:
                h, w = 480, 640

            # Center face approximation for headless testing
            box = [int(w * 0.2), int(h * 0.2), int(w * 0.8), int(h * 0.8)]
            cropped = None
            thumb_b64 = "data:image/jpeg;base64,mockthumb"
            thumb_name = f"crop_{uuid.uuid4().hex[:12]}.jpg"

            if cv2 is not None and hasattr(cv2, "imencode") and shape and len(shape) >= 2:
                try:
                    cropped = self.crop_face(img_bgr, box)
                    thumb_b64 = self.encode_image_base64(cropped)
                    thumb_file = settings.thumbnails_path / thumb_name
                    cv2.imwrite(str(thumb_file), cropped)
                except Exception:
                    pass

            # Deterministic synthetic 512-d embedding
            emb = None
            if cv2 is not None and hasattr(cv2, "calcHist") and cropped is not None:
                try:
                    hist = cv2.calcHist([img_bgr], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256]).flatten()
                    norm = np.linalg.norm(hist)
                    emb = hist / (norm + 1e-10)
                except Exception:
                    pass

            if emb is None:
                emb = np.zeros(512, dtype=np.float32)
                if hasattr(emb, "__setitem__"):
                    emb[0] = 1.0

            return [FaceDetectionResult(
                bbox=box,
                confidence=0.95,
                embedding=emb if hasattr(emb, "astype") else np.zeros(512, dtype=np.float32),
                thumbnail_base64=thumb_b64,
                thumbnail_filename=thumb_name
            )]

        # Check if YOLOv8-Face detector is active and ready
        use_yolo = (
            self.detector_type == "yolov8_face"
            and self.yolo_detector is not None
            and self.yolo_detector.initialized
        )

        if use_yolo:
            yolo_faces = self.yolo_detector.detect(img_bgr, conf_threshold=threshold)
            rec_model = self.app.models.get("recognition") if (hasattr(self.app, "models") and self.app.models) else None

            for face_det in yolo_faces:
                conf = float(face_det["score"])
                if conf < threshold:
                    continue

                bbox = [int(b) for b in face_det["bbox"]]
                box_w = abs(bbox[2] - bbox[0])
                box_h = abs(bbox[3] - bbox[1])
                if box_w < 30 or box_h < 30:
                    continue

                kps = face_det.get("kps", [])

                # ArcFace feature extraction using the 5 aligned landmarks
                emb = None
                if rec_model is not None and len(kps) == 5:
                    try:
                        try:
                            from insightface.app.common import Face
                        except ImportError:
                            class Face(dict):
                                def __init__(self, **kwargs):
                                    super().__init__(**kwargs)
                                    self.__dict__.update(kwargs)
                        face_obj = Face(
                            bbox=np.array(bbox, dtype=np.float32),
                            kps=np.array(kps, dtype=np.float32),
                            det_score=conf
                        )
                        rec_model.get(img_bgr, face_obj)
                        emb = getattr(face_obj, "normed_embedding", None)
                        if emb is None or len(emb) == 0:
                            emb = getattr(face_obj, "embedding", None)
                    except Exception as ex:
                        logger.debug("ArcFace feature extraction on YOLO crop exception: %s", ex)

                if emb is None or len(emb) == 0:
                    # Fallback deterministic histogram embedding
                    cropped_temp = self.crop_face(img_bgr, bbox)
                    hist = cv2.calcHist([cropped_temp], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256]).flatten()
                    norm_hist = np.linalg.norm(hist)
                    emb = hist / (norm_hist + 1e-10)

                norm = np.linalg.norm(emb)
                emb = emb / (norm + 1e-10)

                # Crop thumbnail
                cropped = self.crop_face(img_bgr, bbox)
                thumb_b64 = self.encode_image_base64(cropped)
                thumb_name = f"crop_{uuid.uuid4().hex[:12]}.jpg"
                thumb_file = settings.thumbnails_path / thumb_name
                cv2.imwrite(str(thumb_file), cropped)

                results.append(FaceDetectionResult(
                    bbox=bbox,
                    confidence=round(conf, 3),
                    embedding=emb.astype(np.float32),
                    landmarks=kps,
                    thumbnail_base64=thumb_b64,
                    thumbnail_filename=thumb_name
                ))

            return results

        # InsightFace detection (SCRFD fallback)
        faces = self.app.get(img_bgr)
        for face in faces:
            conf = float(face.det_score)
            if conf < threshold:
                continue

            bbox = [int(b) for b in face.bbox]
            box_w = abs(bbox[2] - bbox[0])
            box_h = abs(bbox[3] - bbox[1])
            if box_w < 30 or box_h < 30:
                continue

            # Normalize embedding
            emb = face.normed_embedding
            if emb is None or len(emb) == 0:
                emb = face.embedding
                norm = np.linalg.norm(emb)
                emb = emb / (norm + 1e-10)

            # Crop thumbnail
            cropped = self.crop_face(img_bgr, bbox)
            thumb_b64 = self.encode_image_base64(cropped)
            thumb_name = f"crop_{uuid.uuid4().hex[:12]}.jpg"
            thumb_file = settings.thumbnails_path / thumb_name
            cv2.imwrite(str(thumb_file), cropped)

            landmarks = [[float(p[0]), float(p[1])] for p in face.kps] if face.kps is not None else []

            results.append(FaceDetectionResult(
                bbox=bbox,
                confidence=round(conf, 3),
                embedding=emb.astype(np.float32),
                landmarks=landmarks,
                thumbnail_base64=thumb_b64,
                thumbnail_filename=thumb_name
            ))

        return results

    @staticmethod
    def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        """Computes cosine similarity between two vectors (-1.0 to 1.0)."""
        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))

    def match_face(
        self,
        query_embedding: np.ndarray,
        known_persons: Dict[str, Dict[str, Any]],
        similarity_threshold: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Matches a query embedding against all known persons' centroids and individual samples.
        """
        threshold = similarity_threshold if similarity_threshold is not None else settings.SIMILARITY_THRESHOLD
        
        best_match = {
            "match": False,
            "person_id": None,
            "name": "Unknown",
            "similarity": 0.0,
            "distance": 1.0,
            "sample_count": 0
        }

        if not known_persons:
            return best_match

        highest_sim = -1.0
        matched_person_id = None
        matched_name = None
        matched_sample_count = 0

        for p_id, p_data in known_persons.items():
            name = p_data.get("name", "Unknown")
            embeddings = p_data.get("embeddings", [])
            centroid = p_data.get("centroid")

            if not embeddings:
                continue

            # Compare with centroid
            sim_centroid = self.cosine_similarity(query_embedding, centroid) if centroid is not None else -1.0
            
            # Compare with highest individual sample
            sim_samples = max([self.cosine_similarity(query_embedding, s) for s in embeddings])
            
            # Weighted ensemble: 0.6 sample max, 0.4 centroid
            effective_sim = max(sim_samples, (sim_centroid * 0.7 + sim_samples * 0.3))

            if effective_sim > highest_sim:
                highest_sim = effective_sim
                matched_person_id = p_id
                matched_name = name
                matched_sample_count = len(embeddings)

        if highest_sim >= threshold and matched_person_id is not None:
            distance = float(np.sqrt(2.0 * max(0.0, 1.0 - highest_sim)))
            is_hh = bool(known_persons[matched_person_id].get("is_household", True))
            return {
                "match": True,
                "person_id": matched_person_id,
                "name": matched_name,
                "similarity": round(highest_sim, 4),
                "distance": round(distance, 4),
                "sample_count": matched_sample_count,
                "is_household": is_hh
            }

        return {
            "match": False,
            "person_id": None,
            "name": "Unknown",
            "similarity": round(max(0.0, highest_sim), 4),
            "distance": round(float(np.sqrt(2.0 * max(0.0, 1.0 - max(0.0, highest_sim)))), 4),
            "sample_count": matched_sample_count,
            "is_household": False
        }

# Global Singleton
face_engine = FaceEngine()
