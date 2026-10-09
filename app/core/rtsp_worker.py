import os
import time
import logging
import threading
from typing import Dict, Any, Optional, List
try:
    import cv2
except ImportError:
    cv2 = None
try:
    import numpy as np
except ImportError:
    from ..db.database import np
from ..config import settings
from .face_engine import face_engine
from .events import dispatch_detection_event
from ..db.database import (
    get_all_active_embeddings,
    record_detection
)

logger = logging.getLogger(__name__)

# Rules for RtspStreamWorker class:
# 1. Variables and worker state must be declared and initialized at the top of the class.
# 2. Worker loop must run on a dedicated background daemon thread without blocking the FastAPI event loop.
# 3. get_status must return comprehensive telemetry including target_fps, actual_fps, and fps_actual for frontend compatibility.
# 4. Stream frame acquisitions and inference must respect configured sampling rates and entity cooldowns.
# 5. Filters out low-confidence faces and tiny non-face bounding boxes before inbox recording and alerts.
class RtspStreamWorker:
    """
    Dedicated background worker thread for real-time RTSP stream processing,
    face detection, identity classification, and event notification dispatching.
    """
    def __init__(self):
        self.thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.is_running = False
        self.is_connected = False
        self.url = settings.RTSP_URL
        self.camera_name = settings.RTSP_CAMERA_NAME
        self.fps = settings.RTSP_FPS
        self.cooldown_seconds = settings.RTSP_COOLDOWN_SECONDS
        
        self.last_frame: Optional[np.ndarray] = None
        self.last_detection: Optional[Dict[str, Any]] = None
        self.last_error = ""
        self.fps_actual = 0.0
        
        # Cooldown map: entity_name -> timestamp of last event emission
        self.cooldowns: Dict[str, float] = {}

    def configure(
        self,
        url: Optional[str] = None,
        camera_name: Optional[str] = None,
        fps: Optional[float] = None,
        cooldown_seconds: Optional[int] = None
    ):
        """Update stream settings at runtime."""
        if url is not None:
            self.url = url
        if camera_name is not None:
            self.camera_name = camera_name
        if fps is not None:
            self.fps = max(0.5, fps)
        if cooldown_seconds is not None:
            self.cooldown_seconds = max(1, cooldown_seconds)

    def start(self):
        """Starts the background RTSP processing thread."""
        if self.is_running:
            logger.info("RTSP worker is already running.")
            return

        if not self.url:
            logger.warning("Cannot start RTSP worker: No RTSP_URL configured.")
            self.last_error = "No RTSP URL configured"
            return

        self.stop_event.clear()
        self.is_running = True
        self.thread = threading.Thread(target=self._run_loop, name="rtsp-worker-thread", daemon=True)
        self.thread.start()
        logger.info("RTSP worker thread started for camera '%s' at %s", self.camera_name, self.url)

    def stop(self):
        """Stops the RTSP worker thread gracefully."""
        if not self.is_running:
            return

        logger.info("Stopping RTSP worker thread...")
        self.stop_event.set()
        self.is_running = False
        self.is_connected = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3.0)
        self.thread = None
        logger.info("RTSP worker thread stopped.")

    def get_status(self) -> Dict[str, Any]:
        """Returns runtime status and diagnostic telemetry."""
        return {
            "is_running": self.is_running,
            "is_connected": self.is_connected,
            "url": self.url,
            "camera_name": self.camera_name,
            "target_fps": self.fps,
            "actual_fps": round(self.fps_actual, 1),
            "fps_actual": round(self.fps_actual, 1),
            "cooldown_seconds": self.cooldown_seconds,
            "last_detection": self.last_detection,
            "last_error": self.last_error,
            "active_cooldowns": {
                k: round(time.time() - v, 1) for k, v in self.cooldowns.items()
            }
        }

    def get_latest_jpeg(self) -> Optional[bytes]:
        """Encodes the latest stream frame to JPEG for live dashboard preview."""
        if self.last_frame is None:
            return None
        success, buffer = cv2.imencode(".jpg", self.last_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        return buffer.tobytes() if success else None

    def _run_loop(self):
        """Main loop: connects to RTSP stream, buffers frames, and triggers inference."""
        reconnect_delay = 5.0

        while not self.stop_event.is_set():
            logger.info("Connecting to RTSP stream: %s", self.url)
            cap = None
            try:
                # Open RTSP stream with FFMPEG backend and minimal buffer to reduce frame lag
                os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
                cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                if not cap.isOpened():
                    raise ConnectionError(f"Failed to open video stream at {self.url}")

                self.is_connected = True
                self.last_error = ""
                logger.info("Successfully connected to RTSP stream '%s'", self.camera_name)

                last_inference_time = 0.0
                frame_count = 0
                fps_timer = time.time()
                min_interval = 1.0 / max(0.5, self.fps)

                while not self.stop_event.is_set():
                    ret, frame = cap.read()
                    if not ret or frame is None:
                        logger.warning("RTSP stream disconnected or end of stream reached.")
                        self.is_connected = False
                        self.last_error = "Stream disconnected"
                        break

                    self.last_frame = frame
                    frame_count += 1

                    # Compute actual FPS every 2 seconds
                    now = time.time()
                    if now - fps_timer >= 2.0:
                        self.fps_actual = frame_count / (now - fps_timer)
                        frame_count = 0
                        fps_timer = now

                    # Process inference at target FPS frequency
                    if now - last_inference_time >= min_interval:
                        last_inference_time = now
                        self._process_frame(frame)

            except Exception as e:
                self.is_connected = False
                self.last_error = str(e)
                logger.warning("RTSP connection error: %s. Reconnecting in %ds...", e, reconnect_delay)
            finally:
                if cap is not None:
                    cap.release()

            if not self.stop_event.is_set():
                time.sleep(reconnect_delay)

        self.is_connected = False

    def _process_frame(self, frame_bgr: np.ndarray):
        """Runs face detection and emits events with cooldowns."""
        try:
            detections = face_engine.detect_and_embed(frame_bgr)
            if not detections:
                return

            known_persons = get_all_active_embeddings()
            now = time.time()

            for det in detections:
                box = getattr(det, "bbox", [])
                if len(box) >= 4:
                    box_w = abs(box[2] - box[0])
                    box_h = abs(box[3] - box[1])
                    if box_w < 35 or box_h < 35:
                        logger.debug("Suppressing tiny RTSP detection: %dx%d (min 35x35)", box_w, box_h)
                        continue

                det_confidence = float(getattr(det, "confidence", 1.0))
                if det_confidence < settings.DETECTION_CONFIDENCE:
                    logger.debug("Suppressing low-confidence face detection: %.2f < %.2f", det_confidence, settings.DETECTION_CONFIDENCE)
                    continue

                match_info = face_engine.match_face(
                    query_embedding=det.embedding,
                    known_persons=known_persons
                )

                person_name = match_info["name"] if match_info["match"] else "Unknown"
                cooldown_key = person_name.lower()

                # For unknown detections: do not clutter database review queue if below UNKNOWN_MIN_CONFIDENCE
                if not match_info["match"] and det_confidence < settings.UNKNOWN_MIN_CONFIDENCE:
                    logger.debug(
                        "Suppressing review inbox logging for low-confidence unknown face: %.2f < %.2f",
                        det_confidence, settings.UNKNOWN_MIN_CONFIDENCE
                    )
                    continue

                # Check cooldown: only fire event if last alert was > cooldown_seconds ago
                last_alert_time = self.cooldowns.get(cooldown_key, 0.0)
                if now - last_alert_time < self.cooldown_seconds:
                    logger.debug("Suppressing event for '%s' due to active cooldown (%.1fs remaining)",
                                 person_name, self.cooldown_seconds - (now - last_alert_time))
                    continue

                # 1. Record detection in SQLite database (for history & dashboard review queue)
                det_status = "matched" if match_info["match"] else "unrecognized"
                det_id = record_detection(
                    thumbnail_path=det.thumbnail_filename,
                    bbox=det.bbox,
                    camera_id=self.camera_name,
                    matched_person_id=match_info["person_id"],
                    matched_name=match_info["name"] if match_info["match"] else None,
                    similarity=match_info["similarity"],
                    status=det_status,
                    confidence=det_confidence
                )

                # 2. Check configured notification threshold before firing alerts
                should_notify = False

                if match_info["match"]:
                    # Known person: similarity must reach or exceed notification threshold
                    if match_info["similarity"] >= settings.NOTIFICATION_THRESHOLD:
                        should_notify = True
                    else:
                        logger.debug(
                            "Suppressing notification for '%s': similarity %.2f < threshold %.2f",
                            person_name, match_info["similarity"], settings.NOTIFICATION_THRESHOLD
                        )
                else:
                    # Unknown person: check notify toggle, external channel acceptance, and minimum confidence
                    allow_unknown_external = (
                        (settings.RTSP_WEBHOOK_URL and not settings.WEBHOOK_ONLY_KNOWN_FACES) or
                        (settings.MQTT_ENABLED and not settings.MQTT_ONLY_KNOWN_FACES and not settings.WEBHOOK_ONLY_KNOWN_FACES)
                    )
                    if settings.NOTIFY_ON_UNKNOWN and allow_unknown_external and det_confidence >= settings.UNKNOWN_MIN_CONFIDENCE:
                        should_notify = True
                    else:
                        logger.debug(
                            "Suppressing notification for Unknown face: notify_on_unknown=%s, allow_unknown_external=%s, confidence=%.2f (min=%.2f)",
                            settings.NOTIFY_ON_UNKNOWN, allow_unknown_external, det_confidence, settings.UNKNOWN_MIN_CONFIDENCE
                        )

                if not should_notify:
                    continue

                # Update cooldown when notification is confirmed
                self.cooldowns[cooldown_key] = now

                event_payload = {
                    "event": "face_detection",
                    "camera": self.camera_name,
                    "person_name": person_name,
                    "match": match_info["match"],
                    "person_id": match_info["person_id"],
                    "similarity": match_info["similarity"],
                    "confidence": det_confidence,
                    "distance": match_info["distance"],
                    "timestamp": now,
                    "detection_id": det_id,
                    "bbox": det.bbox,
                    "thumbnail_url": f"/api/v1/thumbnails/{det.thumbnail_filename}",
                    "thumbnail_base64": det.thumbnail_base64
                }

                self.last_detection = event_payload
                logger.info("Real-time RTSP detection alert: '%s' (similarity: %.2f) on %s",
                            person_name, match_info["similarity"], self.camera_name)

                # 3. Dispatch to Webhook and MQTT
                dispatch_detection_event(event_payload)

        except Exception as e:
            logger.error("Error during RTSP frame inference: %s", e)

# Global Worker Singleton
rtsp_worker = RtspStreamWorker()
