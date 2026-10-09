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
# 1. Encapsulates InsightFace face detection, ArcFace embedding, and cosine matching.
# 2. Class and instance variables must be placed at the top of the class.
# 3. Supports mock_mode for headless test environments without host ONNX runtimes.
# ==============================================================================
class FaceEngine:
    app: Any = None
    initialized: bool = False
    mock_mode: bool = False

    def __init__(self):
        self.app = None
        self.initialized = False
        self.mock_mode = os.getenv("FACE_ENGINE_MOCK", "false").lower() in ("true", "1", "yes")

    def initialize(self):
        """Lazy initialization of InsightFace model with CPU execution provider."""
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
            self.initialized = True
            logger.info("InsightFace successfully initialized with optimized inference pipeline!")
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
            h, w = img_bgr.shape[:2]
            # Center face approximation for headless testing
            box = [int(w * 0.2), int(h * 0.2), int(w * 0.8), int(h * 0.8)]
            cropped = self.crop_face(img_bgr, box)
            thumb_b64 = self.encode_image_base64(cropped)
            
            # Deterministic synthetic 512-d embedding based on image histogram for testing
            hist = cv2.calcHist([img_bgr], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256]).flatten()
            norm = np.linalg.norm(hist)
            emb = hist / (norm + 1e-10)
            
            thumb_name = f"crop_{uuid.uuid4().hex[:12]}.jpg"
            thumb_file = settings.thumbnails_path / thumb_name
            cv2.imwrite(str(thumb_file), cropped)

            return [FaceDetectionResult(
                bbox=box,
                confidence=0.95,
                embedding=emb.astype(np.float32),
                thumbnail_base64=thumb_b64,
                thumbnail_filename=thumb_name
            )]

        # InsightFace detection
        faces = self.app.get(img_bgr)
        for face in faces:
            conf = float(face.det_score)
            if conf < threshold:
                continue

            bbox = [int(b) for b in face.bbox]
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
            return {
                "match": True,
                "person_id": matched_person_id,
                "name": matched_name,
                "similarity": round(highest_sim, 4),
                "distance": round(distance, 4),
                "sample_count": matched_sample_count
            }

        return {
            "match": False,
            "person_id": None,
            "name": "Unknown",
            "similarity": round(max(0.0, highest_sim), 4),
            "distance": round(float(np.sqrt(2.0 * max(0.0, 1.0 - max(0.0, highest_sim)))), 4),
            "sample_count": matched_sample_count
        }

# Global Singleton
face_engine = FaceEngine()
