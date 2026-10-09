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
    record_detection,
    update_detection_best_shot
)

logger = logging.getLogger(__name__)

# Rules for RtspStreamWorker class:
# 1. Variables and worker state must be declared and initialized at the top of the class.
# 2. Worker loop must run on a dedicated background daemon thread without blocking the FastAPI event loop.
# 3. get_status must return comprehensive telemetry including target_fps, actual_fps, and fps_actual for frontend compatibility.
# 4. Stream frame acquisitions and inference must respect configured sampling rates and entity cooldowns.
# 5. Filters out low-confidence faces and tiny non-face bounding boxes before inbox recording and alerts.
# 6. Aggregates unknown face detections across a sliding timeframe window to record only the highest-confidence best shot.
class RtspStreamWorker:
    thread: Optional[threading.Thread] = None
    stop_event: threading.Event = threading.Event()
    is_running: bool = False
    is_connected: bool = False
    url: str = ""
    camera_name: str = ""
    fps: float = 2.0
    cooldown_seconds: int = 30
    last_frame: Optional[Any] = None
    last_detection: Optional[Dict[str, Any]] = None
    last_error: str = ""
    fps_actual: float = 0.0
    cooldowns: Dict[str, float] = {}
    unknown_tracks: List[Dict[str, Any]] = []

    def __init__(self):
        self.thread = None
        self.stop_event = threading.Event()
        self.is_running = False
        self.is_connected = False
        self.url = settings.RTSP_URL
        self.camera_name = settings.RTSP_CAMERA_NAME
        self.fps = settings.RTSP_FPS
        self.cooldown_seconds = settings.RTSP_COOLDOWN_SECONDS
        
        self.last_frame = None
        self.last_detection = None
        self.last_error = ""
        self.fps_actual = 0.0
        
        # Cooldown map: entity_name -> timestamp of last event emission
        self.cooldowns = {}
        # Sliding aggregation window for unknown faces in view: keeps single best-shot
        self.unknown_tracks = []

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
            track_window = float(settings.UNRECOGNIZED_TRACK_WINDOW_SECONDS)

            # Purge expired unrecognized face tracks (expired if unseen for > track_window or active for > 60s)
            self.unknown_tracks = [
                t for t in self.unknown_tracks
                if (now - t["last_seen"] <= track_window) and (now - t.get("first_seen", now) <= max(track_window * 4, 60.0))
            ]

            for det in detections:
                box = getattr(det, "bbox", [])
                if len(box) >= 4:
                    box_w = abs(box[2] - box[0])
                    box_h = abs(box[3] - box[1])
                    if box_w < 35 or box_h < 35:
                        logger.debug("Suppressing tiny RTSP detection: %dx%d (min 35x35)", box_w, box_h)
                        if getattr(det, "thumbnail_filename", None):
                            thumb_p = settings.thumbnails_path / det.thumbnail_filename
                            if thumb_p.exists():
                                try:
                                    thumb_p.unlink()
                                except Exception:
                                    pass
                        continue

                det_confidence = float(getattr(det, "confidence", 1.0))
                if det_confidence < settings.DETECTION_CONFIDENCE:
                    logger.debug("Suppressing low-confidence face detection: %.2f < %.2f", det_confidence, settings.DETECTION_CONFIDENCE)
                    if getattr(det, "thumbnail_filename", None):
                        thumb_p = settings.thumbnails_path / det.thumbnail_filename
                        if thumb_p.exists():
                            try:
                                thumb_p.unlink()
                            except Exception:
                                pass
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
                    if getattr(det, "thumbnail_filename", None):
                        thumb_p = settings.thumbnails_path / det.thumbnail_filename
                        if thumb_p.exists():
                            try:
                                thumb_p.unlink()
                            except Exception:
                                pass
                    continue

                # -------------------------------------------------------------
                # Handle UNKNOWN face detection aggregation
                # -------------------------------------------------------------
                if not match_info["match"]:
                    matched_track = None
                    for t in self.unknown_tracks:
                        if t.get("camera_name") == self.camera_name:
                            if getattr(det, "embedding", None) is not None and t.get("embedding") is not None:
                                try:
                                    sim = float(face_engine.cosine_similarity(det.embedding, t["embedding"]))
                                except Exception:
                                    sim = 0.0
                                if sim >= settings.SIMILARITY_THRESHOLD:
                                    matched_track = t
                                    break

                    if matched_track is not None:
                        # Existing unknown face still in view during the track window
                        matched_track["last_seen"] = now
                        matched_track["frame_count"] = matched_track.get("frame_count", 1) + 1

                        if det_confidence > matched_track["best_confidence"]:
                            old_thumb = matched_track.get("thumbnail_filename")
                            if old_thumb and old_thumb != det.thumbnail_filename:
                                old_path = settings.thumbnails_path / old_thumb
                                if old_path.exists():
                                    try:
                                        old_path.unlink()
                                    except Exception:
                                        pass

                            update_detection_best_shot(
                                detection_id=matched_track["detection_id"],
                                thumbnail_path=det.thumbnail_filename,
                                bbox=det.bbox,
                                confidence=det_confidence
                            )
                            logger.info(
                                "Promoted higher confidence unknown face best-shot on %s: %.2f -> %.2f (id: %s)",
                                self.camera_name, matched_track["best_confidence"], det_confidence, matched_track["detection_id"]
                            )
                            matched_track["best_confidence"] = det_confidence
                            matched_track["thumbnail_filename"] = det.thumbnail_filename
                            matched_track["embedding"] = det.embedding

                            # Update live telemetry last_detection with improved thumbnail
                            if self.last_detection and self.last_detection.get("detection_id") == matched_track["detection_id"]:
                                self.last_detection["confidence"] = det_confidence
                                self.last_detection["thumbnail_url"] = f"/api/v1/thumbnails/{det.thumbnail_filename}"
                                self.last_detection["thumbnail_base64"] = det.thumbnail_base64
                                self.last_detection["bbox"] = det.bbox
                        else:
                            # Lower confidence frame of same unknown face: delete duplicate crop
                            if getattr(det, "thumbnail_filename", None):
                                thumb_p = settings.thumbnails_path / det.thumbnail_filename
                                if thumb_p.exists():
                                    try:
                                        thumb_p.unlink()
                                    except Exception:
                                        pass

                        # Aggregated into existing track; suppress creating another DB row or duplicate alert
                        continue

                    # New unknown face track! Record in database
                    det_id = record_detection(
                        thumbnail_path=det.thumbnail_filename,
                        bbox=det.bbox,
                        camera_id=self.camera_name,
                        matched_person_id=None,
                        matched_name=None,
                        similarity=match_info["similarity"],
                        status="unrecognized",
                        confidence=det_confidence
                    )

                    self.unknown_tracks.append({
                        "detection_id": det_id,
                        "camera_name": self.camera_name,
                        "embedding": det.embedding,
                        "best_confidence": det_confidence,
                        "thumbnail_filename": det.thumbnail_filename,
                        "first_seen": now,
                        "last_seen": now,
                        "frame_count": 1
                    })

                    allow_unknown_external = (
                        (settings.RTSP_WEBHOOK_URL and not settings.WEBHOOK_ONLY_KNOWN_FACES) or
                        (settings.MQTT_ENABLED and not settings.MQTT_ONLY_KNOWN_FACES and not settings.WEBHOOK_ONLY_KNOWN_FACES)
                    )
                    should_notify = (
                        settings.NOTIFY_ON_UNKNOWN and
                        allow_unknown_external and
                        det_confidence >= settings.UNKNOWN_MIN_CONFIDENCE and
                        (now - self.cooldowns.get("unknown", 0.0) >= self.cooldown_seconds)
                    )

                # -------------------------------------------------------------
                # Handle KNOWN face detection
                # -------------------------------------------------------------
                else:
                    last_alert_time = self.cooldowns.get(cooldown_key, 0.0)
                    if now - last_alert_time < self.cooldown_seconds:
                        logger.debug("Suppressing event for '%s' due to active cooldown (%.1fs remaining)",
                                     person_name, self.cooldown_seconds - (now - last_alert_time))
                        if getattr(det, "thumbnail_filename", None):
                            thumb_p = settings.thumbnails_path / det.thumbnail_filename
                            if thumb_p.exists():
                                try:
                                    thumb_p.unlink()
                                except Exception:
                                    pass
                        continue

                    det_id = record_detection(
                        thumbnail_path=det.thumbnail_filename,
                        bbox=det.bbox,
                        camera_id=self.camera_name,
                        matched_person_id=match_info["person_id"],
                        matched_name=match_info["name"],
                        similarity=match_info["similarity"],
                        status="matched",
                        confidence=det_confidence
                    )
                    should_notify = (match_info["similarity"] >= settings.NOTIFICATION_THRESHOLD)

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

                # Dispatch to Webhook and MQTT
                dispatch_detection_event(event_payload)

        except Exception as e:
            logger.error("Error during RTSP frame inference: %s", e)

# Global Worker Singleton
rtsp_worker = RtspStreamWorker()
