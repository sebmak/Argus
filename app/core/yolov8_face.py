import os
import logging
import urllib.request
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import numpy as np
except ImportError:
    from ..db.database import np

try:
    import onnxruntime
except ImportError:
    onnxruntime = None

logger = logging.getLogger(__name__)

# Primary and fallback URLs for the pre-trained YOLOv8-Face ONNX model
YOLO_FACE_MODEL_URLS = [
    "https://github.com/yakhyo/yolov8-face-onnx-inference/releases/download/weights/yolov8n-face.onnx",
    "https://huggingface.co/deepghs/yolo-face/resolve/main/yolov8n-face/model.onnx",
    "https://github.com/lindevs/yolov8-face/releases/download/v0.0.1/yolov8n-face.onnx"
]

def ensure_yolo_face_model(destination_path: Path) -> bool:
    """
    Ensures that the YOLOv8-Face ONNX model file exists on disk.
    If missing, attempts to download it automatically into the models directory.
    Returns True if model file is present or downloaded successfully, False otherwise.
    """
    if destination_path.exists() and destination_path.stat().st_size > 500000:
        return True

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination_path.with_suffix(".tmp")

    for url in YOLO_FACE_MODEL_URLS:
        try:
            logger.info("Attempting to download YOLOv8-Face model from %s...", url)
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 Household-FaceDetection/1.0"}
            )
            with urllib.request.urlopen(req, timeout=30) as response, open(temp_path, "wb") as out_file:
                shutil.copyfileobj(response, out_file)

            if temp_path.exists() and temp_path.stat().st_size > 500000:
                os.replace(temp_path, destination_path)
                logger.info(
                    "YOLOv8-Face model downloaded successfully to %s (size: %d bytes)",
                    destination_path, destination_path.stat().st_size
                )
                return True
            else:
                if temp_path.exists():
                    temp_path.unlink()
        except Exception as e:
            logger.warning("Download from %s failed: %s", url, e)
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass

    logger.warning(
        "Could not automatically download YOLOv8-Face model. If operating offline or firewalled, "
        "please place 'yolov8n-face.onnx' in '%s'.", destination_path
    )
    return False

# ==============================================================================
# Rules for YOLOv8FaceDetector:
# 1. Encapsulates YOLOv8-Face ONNX inference for face bounding box detection and 5 facial landmarks.
# 2. Member variables and session handles must be declared at the top of the class.
# 3. Uses pure OpenCV DNN NMS and NumPy post-processing without PyTorch dependency.
# 4. Supports dynamic image resolutions via letterbox preprocessing and coordinate un-scaling.
# 5. Supports both multi-head unconcatenated DFL outputs (3 feature maps) and single concatenated detection tensors.
# ==============================================================================
class YOLOv8FaceDetector:
    model_path: Optional[str] = None
    session: Any = None
    input_name: str = ""
    output_names: List[str] = []
    input_height: int = 640
    input_width: int = 640
    conf_threshold: float = 0.50
    iou_threshold: float = 0.45
    initialized: bool = False
    providers: List[str] = ["CPUExecutionProvider"]

    def __init__(
        self,
        model_path: Optional[str] = None,
        conf_threshold: float = 0.50,
        iou_threshold: float = 0.45,
        providers: Optional[List[str]] = None
    ):
        self.model_path = model_path
        self.session = None
        self.input_name = ""
        self.output_names = []
        self.input_height = 640
        self.input_width = 640
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.initialized = False
        self.providers = providers or ["CPUExecutionProvider"]

        if model_path:
            self.load_model(model_path)

    def load_model(self, model_path: str) -> bool:
        """Loads ONNX inference session and checks tensor dimensions."""
        if onnxruntime is None:
            logger.warning("onnxruntime is not installed; YOLOv8FaceDetector cannot load.")
            return False

        if not os.path.exists(model_path):
            logger.warning("YOLOv8-Face model file does not exist at %s", model_path)
            return False

        try:
            self.model_path = model_path
            self.session = onnxruntime.InferenceSession(model_path, providers=self.providers)
            
            inputs = self.session.get_inputs()
            self.input_name = inputs[0].name
            
            # Inspect input shape if statically defined
            if len(inputs[0].shape) >= 4:
                h, w = inputs[0].shape[2], inputs[0].shape[3]
                if isinstance(h, int) and h > 0:
                    self.input_height = h
                if isinstance(w, int) and w > 0:
                    self.input_width = w

            outputs = self.session.get_outputs()
            self.output_names = [out.name for out in outputs]
            self.initialized = True
            logger.info(
                "YOLOv8FaceDetector initialized from %s (input: %s %dx%d, outputs: %s)",
                model_path, self.input_name, self.input_width, self.input_height, self.output_names
            )
            return True
        except Exception as e:
            logger.error("Failed to load YOLOv8-Face ONNX model (%s): %s", model_path, e)
            self.initialized = False
            return False

    def preprocess(
        self,
        image_bgr: np.ndarray,
        target_shape: Optional[Tuple[int, int]] = None
    ) -> Tuple[np.ndarray, float, Tuple[float, float]]:
        """
        Resizes and letterboxes image to target shape maintaining aspect ratio.
        Returns: (blob_tensor, scale_ratio, (pad_w, pad_h))
        """
        h, w = image_bgr.shape[:2]
        target_h, target_w = target_shape or (self.input_height, self.input_width)

        scale = min(target_w / float(w), target_h / float(h))
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))

        if cv2 is not None:
            resized = cv2.resize(image_bgr, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            dw = (target_w - new_w) / 2.0
            dh = (target_h - new_h) / 2.0

            top = int(round(dh - 0.1))
            bottom = int(round(dh + 0.1))
            left = int(round(dw - 0.1))
            right = int(round(dw + 0.1))

            padded = cv2.copyMakeBorder(
                resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114, 114, 114)
            )
            rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
            blob = rgb.transpose((2, 0, 1)).astype(np.float32) / 255.0
            blob = np.expand_dims(blob, axis=0)
            return blob, scale, (dw, dh)
        else:
            return np.zeros((1, 3, target_h, target_w), dtype=np.float32), 1.0, (0.0, 0.0)

    @staticmethod
    def softmax(x: np.ndarray, axis: int = -1) -> np.ndarray:
        """Compute softmax values for array x along axis."""
        exp_x = np.exp(x - np.max(x, axis=axis, keepdims=True))
        return exp_x / np.sum(exp_x, axis=axis, keepdims=True)

    def _decode_dfl_feature_maps(
        self,
        feature_maps: List[np.ndarray],
        orig_shape: Tuple[int, int],
        scale: float,
        pad: Tuple[float, float],
        conf_threshold: Optional[float] = None,
        iou_threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Decodes multi-scale YOLOv8-Face Pose/DFL feature maps (e.g. from yakhyo/yolov8-face-onnx-inference).
        Outputs have shape (1, 80, H, W) across strides [8, 16, 32] where 80 = 64 (bbox DFL) + 1 (conf) + 15 (keypoints).
        """
        conf_th = conf_threshold if conf_threshold is not None else self.conf_threshold
        iou_th = iou_threshold if iou_threshold is not None else self.iou_threshold

        boxes_list = []
        scores_list = []
        landmarks_list = []
        strides = [8, 16, 32]

        for pred, stride in zip(feature_maps, strides):
            if not hasattr(pred, "shape") or len(pred.shape) != 4:
                continue
            batch_size, channels, height, width = pred.shape
            if channels < 80:
                continue

            # Reshape: (1, 80, H, W) -> (H*W, 80)
            p = pred.reshape(batch_size, channels, -1).transpose(0, 2, 1)[0]

            # Grid generation with 0.5 center offset matching PyTorch's make_anchors
            grid_y, grid_x = np.meshgrid(np.arange(height) + 0.5, np.arange(width) + 0.5, indexing="ij")
            grid_x = grid_x.flatten()
            grid_y = grid_y.flatten()

            bbox_pred = p[:, :64]
            cls_conf = p[:, 64]
            kpt_pred = p[:, 65:]

            # Softmax across DFL 16 bins and project to distance
            bbox_pred = bbox_pred.reshape(-1, 4, 16)
            dfl_weights = np.arange(16, dtype=np.float32)
            bbox_dist = self.softmax(bbox_pred, axis=-1) @ dfl_weights

            x1 = (grid_x - bbox_dist[:, 0]) * stride
            y1 = (grid_y - bbox_dist[:, 1]) * stride
            x2 = (grid_x + bbox_dist[:, 2]) * stride
            y2 = (grid_y + bbox_dist[:, 3]) * stride
            boxes = np.stack([x1, y1, x2, y2], axis=-1)

            # Keypoints decoding: kpt = (kpt * 2.0 + grid) * stride
            kpt_grid_y, kpt_grid_x = np.meshgrid(np.arange(height), np.arange(width), indexing="ij")
            kpt_grid_x = kpt_grid_x.flatten()
            kpt_grid_y = kpt_grid_y.flatten()

            kpt_pred = kpt_pred.reshape(-1, 5, 3)
            kpt_x = (kpt_pred[:, :, 0] * 2.0 + kpt_grid_x[:, None]) * stride
            kpt_y = (kpt_pred[:, :, 1] * 2.0 + kpt_grid_y[:, None]) * stride
            landmarks = np.stack([kpt_x, kpt_y], axis=-1).reshape(-1, 10)

            # Sigmoid for class confidence
            scores = 1.0 / (1.0 + np.exp(-np.clip(cls_conf, -50.0, 50.0)))

            boxes_list.append(boxes)
            scores_list.append(scores)
            landmarks_list.append(landmarks)

        if not boxes_list:
            return []

        all_boxes = np.concatenate(boxes_list, axis=0)
        all_scores = np.concatenate(scores_list, axis=0)
        all_landmarks = np.concatenate(landmarks_list, axis=0)

        mask = all_scores >= conf_th
        if not np.any(mask):
            return []

        kept_boxes = all_boxes[mask]
        kept_scores = all_scores[mask]
        kept_landmarks = all_landmarks[mask]

        # Convert xyxy to xywh for OpenCV NMS
        w = np.maximum(0.0, kept_boxes[:, 2] - kept_boxes[:, 0])
        h = np.maximum(0.0, kept_boxes[:, 3] - kept_boxes[:, 1])
        boxes_for_nms = []
        for i in range(len(kept_boxes)):
            boxes_for_nms.append([float(kept_boxes[i, 0]), float(kept_boxes[i, 1]), float(w[i]), float(h[i])])

        scores_list_nms = [float(s) for s in kept_scores]

        indices = []
        if cv2 is not None:
            indices = cv2.dnn.NMSBoxes(
                bboxes=boxes_for_nms,
                scores=scores_list_nms,
                score_threshold=float(conf_th),
                nms_threshold=float(iou_th)
            )

        if len(indices) == 0:
            return []

        if hasattr(indices, "flatten"):
            indices = indices.flatten()
        elif isinstance(indices, list):
            indices = [idx[0] if isinstance(idx, (list, tuple, np.ndarray)) else idx for idx in indices]

        orig_h, orig_w = orig_shape
        dw, dh = pad
        results: List[Dict[str, Any]] = []

        for idx in indices:
            idx = int(idx)
            bx1, by1, bx2, by2 = kept_boxes[idx]

            # Un-pad and un-scale
            ubx1 = (bx1 - dw) / scale
            uby1 = (by1 - dh) / scale
            ubx2 = (bx2 - dw) / scale
            uby2 = (by2 - dh) / scale

            clip_x1 = max(0, min(orig_w - 1, int(round(ubx1))))
            clip_y1 = max(0, min(orig_h - 1, int(round(uby1))))
            clip_x2 = max(0, min(orig_w, int(round(ubx2))))
            clip_y2 = max(0, min(orig_h, int(round(uby2))))

            raw_kps = kept_landmarks[idx].reshape(5, 2)
            kps: List[List[float]] = []
            for kx, ky in raw_kps:
                ukx = (kx - dw) / scale
                uky = (ky - dh) / scale
                kps.append([round(float(ukx), 2), round(float(uky), 2)])

            results.append({
                "bbox": [clip_x1, clip_y1, clip_x2, clip_y2],
                "score": round(float(kept_scores[idx]), 3),
                "kps": kps
            })

        return results

    def postprocess(
        self,
        raw_preds: Any,
        orig_shape: Tuple[int, int],
        scale: float,
        pad: Tuple[float, float],
        conf_threshold: Optional[float] = None,
        iou_threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Parses raw model outputs (both DFL multi-head and concatenated single-tensor),
        runs OpenCV NMS, and un-scales coordinates back to original image.
        Returns list of detections with 'bbox', 'score', and 'kps'.
        """
        if raw_preds is None or len(raw_preds) == 0:
            return []

        # Case 1: Multiple feature map outputs (e.g. YOLOv8 Pose DFL 3 strides)
        if isinstance(raw_preds, (list, tuple)):
            if len(raw_preds) >= 3 and any(len(getattr(p, "shape", ())) == 4 and p.shape[1] >= 80 for p in raw_preds):
                return self._decode_dfl_feature_maps(
                    raw_preds, orig_shape, scale, pad, conf_threshold, iou_threshold
                )
            elif len(raw_preds) == 1:
                preds = raw_preds[0]
            else:
                preds = raw_preds[0]
        else:
            preds = raw_preds

        # Check if single 4D tensor with >= 80 channels was passed
        if hasattr(preds, "shape") and len(preds.shape) == 4 and preds.shape[1] >= 80:
            return self._decode_dfl_feature_maps(
                [preds], orig_shape, scale, pad, conf_threshold, iou_threshold
            )

        # Case 2: Concatenated single tensor output
        if hasattr(preds, "shape"):
            if len(preds.shape) == 3:
                # If shape is (1, C, Anchors) e.g. (1, 15, 8400), transpose to (Anchors, C)
                if preds.shape[1] < preds.shape[2]:
                    preds = np.transpose(preds[0], (1, 0))
                else:
                    preds = preds[0]
            elif len(preds.shape) == 2 and preds.shape[0] < preds.shape[1]:
                preds = np.transpose(preds, (1, 0))
            elif len(preds.shape) > 2:
                preds = np.squeeze(preds)
                if len(preds.shape) == 2 and preds.shape[0] < preds.shape[1]:
                    preds = np.transpose(preds, (1, 0))

        if not hasattr(preds, "shape") or len(preds.shape) != 2:
            return []

        conf_th = conf_threshold if conf_threshold is not None else self.conf_threshold
        iou_th = iou_threshold if iou_threshold is not None else self.iou_threshold

        scores = preds[:, 4]
        mask = scores >= conf_th
        if not np.any(mask):
            return []

        filtered = preds[mask]
        filtered_scores = scores[mask]

        cx = filtered[:, 0]
        cy = filtered[:, 1]
        w = filtered[:, 2]
        h = filtered[:, 3]

        x1 = cx - w / 2.0
        y1 = cy - h / 2.0

        boxes_for_nms = []
        for i in range(len(filtered)):
            boxes_for_nms.append([float(x1[i]), float(y1[i]), float(w[i]), float(h[i])])

        scores_list = [float(s) for s in filtered_scores]

        indices = []
        if cv2 is not None:
            indices = cv2.dnn.NMSBoxes(
                bboxes=boxes_for_nms,
                scores=scores_list,
                score_threshold=float(conf_th),
                nms_threshold=float(iou_th)
            )

        if len(indices) == 0:
            return []

        if hasattr(indices, "flatten"):
            indices = indices.flatten()
        elif isinstance(indices, list):
            indices = [idx[0] if isinstance(idx, (list, tuple, np.ndarray)) else idx for idx in indices]

        orig_h, orig_w = orig_shape
        dw, dh = pad
        results: List[Dict[str, Any]] = []

        C = filtered.shape[1]

        for idx in indices:
            idx = int(idx)
            # Un-pad and un-scale bounding box
            bx1 = (x1[idx] - dw) / scale
            by1 = (y1[idx] - dh) / scale
            bx2 = (x1[idx] + w[idx] - dw) / scale
            by2 = (y1[idx] + h[idx] - dh) / scale

            # Clip box to image boundaries
            clip_x1 = max(0, min(orig_w - 1, int(round(bx1))))
            clip_y1 = max(0, min(orig_h - 1, int(round(by1))))
            clip_x2 = max(0, min(orig_w, int(round(bx2))))
            clip_y2 = max(0, min(orig_h, int(round(by2))))

            # Extract 5 facial keypoints: [left_eye, right_eye, nose, left_mouth, right_mouth]
            pred_row = filtered[idx]
            if C == 15:
                # 5 landmarks (x, y)
                raw_kps = pred_row[5:15].reshape(5, 2)
            elif C >= 20:
                # 5 landmarks (x, y, conf/vis)
                raw_kps = pred_row[5:20].reshape(5, 3)[:, :2]
            elif C == 16:
                raw_kps = pred_row[6:16].reshape(5, 2)
            else:
                raw_kps = pred_row[5:15].reshape(5, 2)

            kps: List[List[float]] = []
            for kx, ky in raw_kps:
                unpad_kx = (kx - dw) / scale
                unpad_ky = (ky - dh) / scale
                kps.append([round(float(unpad_kx), 2), round(float(unpad_ky), 2)])

            results.append({
                "bbox": [clip_x1, clip_y1, clip_x2, clip_y2],
                "score": round(float(filtered_scores[idx]), 3),
                "kps": kps
            })

        return results

    def detect(
        self,
        image_bgr: np.ndarray,
        conf_threshold: Optional[float] = None,
        iou_threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Runs full YOLOv8-Face detection pipeline on an input BGR image.
        Returns list of detection dictionaries with 'bbox', 'score', and 'kps'.
        """
        if not self.initialized or self.session is None or cv2 is None:
            return []

        orig_shape = image_bgr.shape[:2]
        blob, scale, (dw, dh) = self.preprocess(image_bgr)

        try:
            outputs = self.session.run(self.output_names, {self.input_name: blob})
            return self.postprocess(
                outputs,
                orig_shape=orig_shape,
                scale=scale,
                pad=(dw, dh),
                conf_threshold=conf_threshold,
                iou_threshold=iou_threshold
            )
        except Exception as e:
            logger.error("YOLOv8-Face inference error: %s", e)
            return []
