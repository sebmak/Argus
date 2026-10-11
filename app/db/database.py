import sqlite3
import os
import uuid
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
try:
    import numpy as np
except ImportError:
    import struct
    import math

    # Rules for _DummyArray class:
    # 1. Variables and element representation must be declared at the top of the class.
    # 2. Implements lightweight vector arithmetic and byte serialization fallbacks when numpy is unavailable.
    class _DummyArray(list):
        def astype(self, dtype):
            return self

        def tobytes(self):
            return struct.pack(f"{len(self)}f", *self)

        def __truediv__(self, scalar):
            return _DummyArray([x / scalar for x in self])

        def __mul__(self, scalar):
            return _DummyArray([x * scalar for x in self])

        def __neg__(self):
            return _DummyArray([-x for x in self])

        def __add__(self, other):
            return _DummyArray([x + y for x, y in zip(self, other)])

    # Rules for _DummyLinalg class:
    # 1. Variables and math configuration must be declared at the top of the class.
    # 2. Provides pure-python Euclidean norm calculation fallback.
    class _DummyLinalg:
        @staticmethod
        def norm(vec):
            return math.sqrt(sum(x * x for x in vec)) or 1e-10

    # Rules for _DummyNumpy class:
    # 1. Variables and mock type attributes must be defined at the top of the class.
    # 2. Provides lightweight fallback math methods and array conversions when numpy is not installed on host.
    class _DummyNumpy:
        ndarray = Any
        float32 = "float32"
        linalg = _DummyLinalg()

        @staticmethod
        def frombuffer(buf, dtype=None):
            num = len(buf) // 4
            if num == 0:
                return _DummyArray([])
            return _DummyArray(struct.unpack(f"{num}f", buf[:num * 4]))

        @staticmethod
        def stack(arrays):
            return list(arrays)

        @staticmethod
        def mean(arrays, axis=0):
            if not arrays:
                return _DummyArray([])
            length = len(arrays[0])
            sums = [0.0] * length
            for arr in arrays:
                for i in range(length):
                    sums[i] += arr[i]
            count = len(arrays)
            return _DummyArray([s / count for s in sums])

        @staticmethod
        def zeros(n, dtype=None):
            return _DummyArray([0.0] * n)

        @staticmethod
        def dot(a, b):
            return sum(x * y for x, y in zip(a, b))

        @staticmethod
        def sqrt(x):
            return math.sqrt(max(0.0, float(x)))

        # Rules for random class:
        # 1. Variables and pseudo-random generators must be defined at the top of the class.
        # 2. Generates Gaussian normal distribution vectors as numpy fallback.
        class random:
            @staticmethod
            def randn(n):
                import random
                return _DummyArray([random.gauss(0, 1) for _ in range(n)])

    np = _DummyNumpy()

try:
    import bcrypt
except ImportError:
    bcrypt = None

from ..config import settings

logger = logging.getLogger(__name__)

def hash_password(password: str) -> str:
    """Hashes a password using bcrypt directly, safely truncating to 72 bytes."""
    if bcrypt is not None:
        pwd_bytes = password.encode("utf-8")[:72]
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")
    import hashlib
    return f"sha256_{hashlib.sha256(password.encode()).hexdigest()}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a stored bcrypt hash."""
    if bcrypt is not None:
        try:
            pwd_bytes = plain_password.encode("utf-8")[:72]
            return bcrypt.checkpw(pwd_bytes, hashed_password.encode("utf-8"))
        except Exception:
            return False
    import hashlib
    return hashed_password == f"sha256_{hashlib.sha256(plain_password.encode()).hexdigest()}"


def get_db():
    """Returns a SQLite connection with row factory enabled."""
    db_file = Path(settings.db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_file), timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def init_db(target_version: Optional[str] = None) -> Dict[str, Any]:
    """Initializes directories and executes versioned migrations to reconcile schema."""
    from .migrations import run_migrations
    settings.config_path.mkdir(parents=True, exist_ok=True)
    settings.thumbnails_path.mkdir(parents=True, exist_ok=True)
    settings.snapshots_path.mkdir(parents=True, exist_ok=True)

    result = run_migrations(target_version=target_version, db_path=settings.db_path)
    logger.info(
        "Database migrations reconciled to version %s (target: %s, applied: %s, rolled_back: %s)",
        result.get("current_app_version"),
        result.get("target_app_version"),
        result.get("applied"),
        result.get("rolled_back")
    )
    return result

# --- Person Helpers ---

def get_all_persons() -> List[Dict[str, Any]]:
    """Retrieve all persons with their sample count, primary thumbnail, and household status."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                p.id, p.name, p.notes, p.is_household, p.created_at, p.updated_at,
                COUNT(s.id) AS sample_count,
                (SELECT thumbnail_path FROM face_samples WHERE person_id = p.id ORDER BY created_at DESC LIMIT 1) AS primary_thumbnail,
                (SELECT timestamp FROM detections WHERE matched_person_id = p.id ORDER BY timestamp DESC LIMIT 1) AS last_seen
            FROM persons p
            LEFT JOIN face_samples s ON p.id = s.person_id
            GROUP BY p.id
            ORDER BY p.name ASC
        """)
        rows = cursor.fetchall()
        persons = []
        for row in rows:
            p = dict(row)
            p["is_household"] = bool(p["is_household"]) if p.get("is_household") is not None else True
            persons.append(p)
        return persons

def get_person_by_id(person_id: str) -> Optional[Dict[str, Any]]:
    """Get a single person by ID with sample details and household status."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM persons WHERE id = ?", (person_id,))
        row = cursor.fetchone()
        if not row:
            return None
        person = dict(row)
        person["is_household"] = bool(person["is_household"]) if person.get("is_household") is not None else True
        
        # Get samples
        cursor.execute("SELECT id, thumbnail_path, source, camera_id, created_at FROM face_samples WHERE person_id = ? ORDER BY created_at DESC", (person_id,))
        person["samples"] = [dict(s) for s in cursor.fetchall()]
        person["sample_count"] = len(person["samples"])
        return person

def get_person_by_name(name: str) -> Optional[Dict[str, Any]]:
    """Find a person by exact name (case-insensitive) with household status."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM persons WHERE LOWER(name) = LOWER(?)", (name.strip(),))
        row = cursor.fetchone()
        if not row:
            return None
        person = dict(row)
        person["is_household"] = bool(person["is_household"]) if person.get("is_household") is not None else True
        return person

def create_person(name: str, notes: str = "", is_household: bool = True) -> Dict[str, Any]:
    """Create a new person entry with household classification."""
    name_clean = name.strip()
    person_id = f"p_{uuid.uuid4().hex[:12]}"
    hh_val = 1 if is_household else 0
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO persons (id, name, notes, is_household, created_at, updated_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
            (person_id, name_clean, notes, hh_val)
        )
        conn.commit()
    return {"id": person_id, "name": name_clean, "notes": notes, "is_household": is_household, "sample_count": 0}

def update_person(
    person_id: str,
    name: Optional[str] = None,
    notes: Optional[str] = None,
    is_household: Optional[bool] = None
) -> Optional[Dict[str, Any]]:
    """Updates a person's name, notes, or household status."""
    person = get_person_by_id(person_id)
    if not person:
        return None

    updates = []
    params = []
    if name is not None and name.strip():
        updates.append("name = ?")
        params.append(name.strip())
    if notes is not None:
        updates.append("notes = ?")
        params.append(notes.strip())
    if is_household is not None:
        updates.append("is_household = ?")
        params.append(1 if is_household else 0)

    if updates:
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(person_id)
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE persons SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()

    return get_person_by_id(person_id)

def delete_person(person_id: str) -> bool:
    """Delete a person and all their associated face samples."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM persons WHERE id = ?", (person_id,))
        conn.commit()
        return cursor.rowcount > 0

# --- Face Sample & Embedding Helpers ---

def add_face_sample(
    person_id: str,
    embedding: np.ndarray,
    thumbnail_path: str,
    source: str = "manual",
    camera_id: str = "",
    event_id: str = ""
) -> str:
    """Stores a 512-d face embedding vector and thumbnail for a person."""
    sample_id = f"s_{uuid.uuid4().hex[:12]}"
    embedding_blob = embedding.astype(np.float32).tobytes()
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Check max sample limit to prevent unbounded growth from auto-training
        cursor.execute("SELECT COUNT(*) FROM face_samples WHERE person_id = ?", (person_id,))
        count = cursor.fetchone()[0]
        if count >= settings.MAX_SAMPLES_PER_PERSON:
            # Delete the oldest sample
            cursor.execute("""
                DELETE FROM face_samples 
                WHERE id = (SELECT id FROM face_samples WHERE person_id = ? ORDER BY created_at ASC LIMIT 1)
            """, (person_id,))

        cursor.execute("""
            INSERT INTO face_samples (id, person_id, embedding, thumbnail_path, source, camera_id, event_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (sample_id, person_id, embedding_blob, thumbnail_path, source, camera_id, event_id))
        
        # Touch person's updated_at
        cursor.execute("UPDATE persons SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (person_id,))
        conn.commit()
        
    return sample_id

def get_person_samples(person_id: str) -> List[Dict[str, Any]]:
    """Retrieve all sample records and numpy embeddings for a person."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, person_id, embedding, thumbnail_path, source, created_at FROM face_samples WHERE person_id = ?", (person_id,))
        samples = []
        for row in cursor.fetchall():
            sample = dict(row)
            sample["vector"] = np.frombuffer(sample.pop("embedding"), dtype=np.float32)
            samples.append(sample)
        return samples

def get_all_active_embeddings() -> Dict[str, Dict[str, Any]]:
    """
    Returns all persons with their stored embedding vectors, computed centroid, and household classification.
    Format:
    {
       person_id: {
           "id": person_id,
           "name": "Sebastian",
           "is_household": True,
           "embeddings": [np.ndarray, ...],
           "centroid": np.ndarray
       }
    }
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.id, p.name, p.is_household, s.embedding 
            FROM persons p
            JOIN face_samples s ON p.id = s.person_id
        """)
        rows = cursor.fetchall()
        
        result: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            p_id = row["id"]
            if p_id not in result:
                is_hh = bool(row["is_household"]) if "is_household" in row.keys() and row["is_household"] is not None else True
                result[p_id] = {
                    "id": p_id,
                    "name": row["name"],
                    "is_household": is_hh,
                    "embeddings": []
                }
            vector = np.frombuffer(row["embedding"], dtype=np.float32)
            result[p_id]["embeddings"].append(vector)
            
        # Compute normalized centroid vector for each person
        for p_id, data in result.items():
            if data["embeddings"]:
                stacked = np.stack(data["embeddings"])
                mean_vec = np.mean(stacked, axis=0)
                norm = np.linalg.norm(mean_vec)
                data["centroid"] = mean_vec / (norm + 1e-10) if norm > 0 else mean_vec
            else:
                data["centroid"] = None
                
        return result

def delete_face_sample(sample_id: str) -> bool:
    """Delete a specific face sample."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM face_samples WHERE id = ?", (sample_id,))
        conn.commit()
        return cursor.rowcount > 0

# --- Detections History & Review Queue ---

def record_detection(
    thumbnail_path: str,
    bbox: List[int],
    camera_id: str = "",
    matched_person_id: Optional[str] = None,
    matched_name: Optional[str] = None,
    similarity: float = 0.0,
    status: str = "matched",
    confidence: float = 1.0,
    is_household: Optional[bool] = None
) -> str:
    """Record a face detection event with detection confidence and household classification."""
    detection_id = f"det_{uuid.uuid4().hex[:12]}"
    hh_val = None
    if is_household is not None:
        hh_val = 1 if is_household else 0
    elif matched_person_id is not None:
        person = get_person_by_id(matched_person_id)
        if person:
            hh_val = 1 if person.get("is_household", True) else 0

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO detections (
                id, timestamp, camera_id, thumbnail_path, bbox, 
                matched_person_id, matched_name, similarity, status, confidence, is_household, created_at
            )
            VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            detection_id, camera_id, thumbnail_path, json.dumps(bbox),
            matched_person_id, matched_name, similarity, status, float(confidence), hh_val
        ))
        conn.commit()
    return detection_id

def get_unrecognized_detections(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """Retrieve unrecognized detections waiting for manual classification."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, timestamp, camera_id, thumbnail_path, bbox, status, created_at, confidence
            FROM detections
            WHERE status = 'unrecognized'
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
        rows = cursor.fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["bbox"] = json.loads(item["bbox"]) if item["bbox"] else []
            raw_conf = item.get("confidence")
            item["confidence"] = float(raw_conf) if raw_conf is not None else 1.0
            result.append(item)
        return result

def purge_low_confidence_detections(min_confidence: float = 0.65) -> Dict[str, Any]:
    """
    Purges unreviewed/unrecognized detections with confidence below threshold,
    and removes their orphaned thumbnail images from disk.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, thumbnail_path, confidence 
            FROM detections 
            WHERE status = 'unrecognized' 
              AND (confidence IS NULL OR confidence < ?)
        """, (min_confidence,))
        rows = cursor.fetchall()

        deleted_count = 0
        deleted_files = 0
        for row in rows:
            det_id = row["id"]
            thumb = row["thumbnail_path"]
            if thumb:
                thumb_file = settings.thumbnails_path / thumb
                try:
                    if thumb_file.exists():
                        thumb_file.unlink()
                        deleted_files += 1
                except Exception as e:
                    logger.debug("Could not remove thumbnail %s: %s", thumb, e)
            cursor.execute("DELETE FROM detections WHERE id = ?", (det_id,))
            deleted_count += 1
        conn.commit()

    return {
        "deleted_count": deleted_count,
        "deleted_files": deleted_files,
        "threshold": min_confidence
    }

def update_detection_best_shot(
    detection_id: str,
    thumbnail_path: str,
    bbox: List[int],
    confidence: float
) -> bool:
    """Updates an existing detection with a higher-confidence best-shot thumbnail and bbox."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE detections
            SET thumbnail_path = ?, bbox = ?, confidence = ?, timestamp = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (thumbnail_path, json.dumps(bbox), float(confidence), detection_id))
        conn.commit()
        return cursor.rowcount > 0

def deduplicate_unrecognized_detections(time_window_seconds: int = 20) -> Dict[str, Any]:
    """
    Combines consecutive unrecognized detections within time_window_seconds per camera,
    keeping only the single highest-confidence best-shot and deleting redundant duplicate frames
    and their orphaned thumbnails.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, camera_id, timestamp, thumbnail_path, confidence, created_at
            FROM detections
            WHERE status = 'unrecognized'
            ORDER BY camera_id ASC, timestamp ASC, id ASC
        """)
        rows = [dict(r) for r in cursor.fetchall()]

        if not rows:
            return {"deleted_count": 0, "kept_count": 0, "deleted_files": 0, "window_seconds": time_window_seconds}

        def parse_ts(ts_str: str) -> float:
            try:
                dt = datetime.strptime(ts_str[:19], "%Y-%m-%d %H:%M:%S")
                return dt.timestamp()
            except Exception:
                return 0.0

        clusters = []
        current_cluster = []

        for row in rows:
            row["ts_float"] = parse_ts(row["timestamp"])
            row["conf_float"] = float(row["confidence"]) if row.get("confidence") is not None else 0.0

            if not current_cluster:
                current_cluster.append(row)
                continue

            prev = current_cluster[-1]
            same_cam = (row["camera_id"] == prev["camera_id"])
            time_diff = abs(row["ts_float"] - prev["ts_float"])

            if same_cam and time_diff <= time_window_seconds:
                current_cluster.append(row)
            else:
                clusters.append(current_cluster)
                current_cluster = [row]

        if current_cluster:
            clusters.append(current_cluster)

        deleted_ids = []
        deleted_files = 0
        kept_count = 0

        for cluster in clusters:
            if len(cluster) == 1:
                kept_count += 1
                continue

            # Pick the detection with the highest confidence
            best = max(cluster, key=lambda d: d["conf_float"])
            kept_count += 1

            for item in cluster:
                if item["id"] != best["id"]:
                    deleted_ids.append(item["id"])
                    thumb = item.get("thumbnail_path")
                    if thumb and thumb != best.get("thumbnail_path"):
                        thumb_file = settings.thumbnails_path / thumb
                        try:
                            if thumb_file.exists():
                                thumb_file.unlink()
                                deleted_files += 1
                        except Exception as e:
                            logger.debug("Could not remove duplicate thumbnail %s: %s", thumb, e)

        if deleted_ids:
            chunk_size = 500
            for i in range(0, len(deleted_ids), chunk_size):
                chunk = deleted_ids[i:i + chunk_size]
                placeholders = ",".join("?" for _ in chunk)
                cursor.execute(f"DELETE FROM detections WHERE id IN ({placeholders})", chunk)
            conn.commit()

        return {
            "deleted_count": len(deleted_ids),
            "kept_count": kept_count,
            "deleted_files": deleted_files,
            "window_seconds": time_window_seconds
        }

def assign_detection_to_person(detection_id: str, person_id: str) -> bool:
    """Mark an unrecognized detection as assigned to a person, adopting their household status."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, is_household FROM persons WHERE id = ?", (person_id,))
        person_row = cursor.fetchone()
        if not person_row:
            return False
            
        is_hh = bool(person_row["is_household"]) if "is_household" in person_row.keys() and person_row["is_household"] is not None else True
        cursor.execute("""
            UPDATE detections 
            SET status = 'assigned', matched_person_id = ?, matched_name = ?, is_household = ?
            WHERE id = ?
        """, (person_id, person_row["name"], 1 if is_hh else 0, detection_id))
        conn.commit()
        return cursor.rowcount > 0

def dismiss_detection(detection_id: str) -> bool:
    """Dismiss/ignore an unrecognized detection."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE detections SET status = 'dismissed' WHERE id = ?", (detection_id,))
        conn.commit()
        return cursor.rowcount > 0

# --- Dashboard Stats & Auth Helpers ---

def get_system_stats() -> Dict[str, Any]:
    """Retrieve summary counts for the dashboard overview."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM persons")
        total_persons = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM persons WHERE is_household = 1 OR is_household IS NULL")
        household_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM persons WHERE is_household = 0")
        visitor_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM face_samples")
        total_samples = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM detections WHERE status = 'unrecognized'")
        unrecognized_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM detections WHERE DATE(timestamp) = DATE('now')")
        detections_today = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM detections WHERE DATE(timestamp) = DATE('now') AND status IN ('matched', 'assigned')")
        recognized_today = cursor.fetchone()[0]

        accuracy_rate = round((recognized_today / detections_today * 100), 1) if detections_today > 0 else 100.0

        # Recent 10 activity records
        cursor.execute("""
            SELECT id, timestamp, camera_id, thumbnail_path, matched_name, similarity, status, is_household
            FROM detections
            ORDER BY timestamp DESC
            LIMIT 10
        """)
        recent_activity = []
        for row in cursor.fetchall():
            rec = dict(row)
            rec["is_household"] = bool(rec["is_household"]) if rec.get("is_household") is not None else None
            recent_activity.append(rec)

        return {
            "total_persons": total_persons,
            "household_count": household_count,
            "visitor_count": visitor_count,
            "total_samples": total_samples,
            "unrecognized_count": unrecognized_count,
            "detections_today": detections_today,
            "recognized_today": recognized_today,
            "accuracy_rate": accuracy_rate,
            "recent_activity": recent_activity,
            "det_size": settings.DET_SIZE,
            "ort_num_threads": settings.ORT_NUM_THREADS,
            "face_detector_type": settings.FACE_DETECTOR_TYPE,
            "face_model_name": settings.FACE_MODEL_NAME
        }

def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(?)", (username.strip(),))
        row = cursor.fetchone()
        return dict(row) if row else None

def create_user(username: str, password_plain: str) -> str:
    user_id = f"u_{uuid.uuid4().hex[:12]}"
    hashed_pw = hash_password(password_plain)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (id, username, password_hash) VALUES (?, ?, ?)",
            (user_id, username.strip(), hashed_pw)
        )
        conn.commit()
    return user_id

def verify_user_credentials(username: str, password_plain: str) -> Optional[Dict[str, Any]]:
    user = get_user_by_username(username)
    if not user:
        return None
    if not verify_password(password_plain, user["password_hash"]):
        return None
    return user

# --- Dynamic Settings Storage Helpers ---

DEFAULT_SETTINGS_MAP = {
    "detection_confidence": lambda: str(settings.DETECTION_CONFIDENCE),
    "face_detector_type": lambda: settings.FACE_DETECTOR_TYPE,
    "similarity_threshold": lambda: str(settings.SIMILARITY_THRESHOLD),
    "notification_threshold": lambda: str(settings.NOTIFICATION_THRESHOLD),
    "notify_on_unknown": lambda: "true" if settings.NOTIFY_ON_UNKNOWN else "false",
    "unknown_min_confidence": lambda: str(settings.UNKNOWN_MIN_CONFIDENCE),
    "det_size": lambda: str(settings.DET_SIZE),
    "ort_num_threads": lambda: str(settings.ORT_NUM_THREADS),
    "max_samples_per_person": lambda: str(settings.MAX_SAMPLES_PER_PERSON),
    "rtsp_enabled": lambda: "true" if settings.RTSP_ENABLED else "false",
    "rtsp_url": lambda: settings.RTSP_URL,
    "rtsp_camera_name": lambda: settings.RTSP_CAMERA_NAME,
    "rtsp_fps": lambda: str(settings.RTSP_FPS),
    "rtsp_cooldown_seconds": lambda: str(settings.RTSP_COOLDOWN_SECONDS),
    "rtsp_motion_gating_enabled": lambda: "true" if settings.RTSP_MOTION_GATING_ENABLED else "false",
    "rtsp_motion_threshold": lambda: str(settings.RTSP_MOTION_THRESHOLD),
    "rtsp_webhook_url": lambda: settings.RTSP_WEBHOOK_URL,
    "unrecognized_track_window_seconds": lambda: str(settings.UNRECOGNIZED_TRACK_WINDOW_SECONDS),
    "webhook_only_known_faces": lambda: "true" if settings.WEBHOOK_ONLY_KNOWN_FACES else "false",
    "mqtt_only_known_faces": lambda: "true" if settings.MQTT_ONLY_KNOWN_FACES else "false",
    "mqtt_enabled": lambda: "true" if settings.MQTT_ENABLED else "false",
    "mqtt_host": lambda: settings.MQTT_HOST,
    "mqtt_port": lambda: str(settings.MQTT_PORT),
    "mqtt_topic": lambda: settings.MQTT_TOPIC,
    "mqtt_user": lambda: settings.MQTT_USER,
    "mqtt_password": lambda: settings.MQTT_PASSWORD
}

def seed_default_settings():
    """Seeds SQLite settings table with defaults from environment config if missing, then syncs to memory."""
    with get_db() as conn:
        cursor = conn.cursor()
        # Defensive check: ensure settings table exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        # If a rollback backup existed from a previous downgrade, restore it!
        cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name = 'settings_v1_1_backup'")
        if cursor.fetchone():
            logger.info("Restoring previous settings from rollback backup table in seed_default_settings...")
            cursor.execute("""
                INSERT OR REPLACE INTO settings (key, value)
                SELECT key, value FROM settings_v1_1_backup
            """)
            cursor.execute("DROP TABLE IF EXISTS settings_v1_1_backup;")
            conn.commit()

        for key, val_fn in DEFAULT_SETTINGS_MAP.items():
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            if not cursor.fetchone():
                cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(val_fn())))

        # Synchronize container environment variables if explicitly defined in runtime environment
        env_explicit_sync_bool = {
            "notify_on_unknown": "NOTIFY_ON_UNKNOWN",
            "webhook_only_known_faces": "WEBHOOK_ONLY_KNOWN_FACES",
            "mqtt_only_known_faces": "MQTT_ONLY_KNOWN_FACES",
            "mqtt_enabled": "MQTT_ENABLED",
            "rtsp_enabled": "RTSP_ENABLED",
            "rtsp_motion_gating_enabled": "RTSP_MOTION_GATING_ENABLED"
        }
        for s_key, env_name in env_explicit_sync_bool.items():
            if env_name in os.environ and os.environ[env_name].strip() != "":
                env_val = os.environ[env_name].strip().lower()
                bool_str = "true" if env_val in ("true", "1", "yes") else "false"
                cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (s_key, bool_str))

        env_explicit_sync_str = {
            "face_detector_type": "FACE_DETECTOR_TYPE",
            "det_size": "DET_SIZE",
            "ort_num_threads": "ORT_NUM_THREADS",
            "detection_confidence": "DETECTION_CONFIDENCE",
            "similarity_threshold": "SIMILARITY_THRESHOLD",
            "notification_threshold": "NOTIFICATION_THRESHOLD",
            "unknown_min_confidence": "UNKNOWN_MIN_CONFIDENCE",
            "max_samples_per_person": "MAX_SAMPLES_PER_PERSON",
            "rtsp_url": "RTSP_URL",
            "rtsp_camera_name": "RTSP_CAMERA_NAME",
            "rtsp_fps": "RTSP_FPS",
            "rtsp_cooldown_seconds": "RTSP_COOLDOWN_SECONDS",
            "rtsp_motion_threshold": "RTSP_MOTION_THRESHOLD",
            "rtsp_webhook_url": "RTSP_WEBHOOK_URL",
            "mqtt_host": "MQTT_HOST",
            "mqtt_port": "MQTT_PORT",
            "mqtt_topic": "MQTT_TOPIC"
        }
        for s_key, env_name in env_explicit_sync_str.items():
            if env_name in os.environ and os.environ[env_name].strip() != "":
                cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (s_key, os.environ[env_name].strip()))
        conn.commit()
    sync_settings_to_runtime()

def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Retrieve single setting value from SQLite."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        if row:
            return row["value"]
    return default

def get_all_settings() -> Dict[str, Any]:
    """Retrieve all configurable settings formatted with appropriate types."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM settings")
        rows = cursor.fetchall()
        raw = {row["key"]: row["value"] for row in rows}

    return {
        "face_detector_type": raw.get("face_detector_type", settings.FACE_DETECTOR_TYPE),
        "detection_confidence": float(raw.get("detection_confidence", settings.DETECTION_CONFIDENCE)),
        "similarity_threshold": float(raw.get("similarity_threshold", settings.SIMILARITY_THRESHOLD)),
        "notification_threshold": float(raw.get("notification_threshold", settings.NOTIFICATION_THRESHOLD)),
        "notify_on_unknown": raw.get("notify_on_unknown", "true").lower() in ("true", "1", "yes"),
        "unknown_min_confidence": float(raw.get("unknown_min_confidence", settings.UNKNOWN_MIN_CONFIDENCE)),
        "det_size": int(raw.get("det_size", settings.DET_SIZE)),
        "ort_num_threads": int(raw.get("ort_num_threads", settings.ORT_NUM_THREADS)),
        "max_samples_per_person": int(raw.get("max_samples_per_person", settings.MAX_SAMPLES_PER_PERSON)),
        "rtsp_enabled": raw.get("rtsp_enabled", "false").lower() in ("true", "1", "yes"),
        "rtsp_url": raw.get("rtsp_url", settings.RTSP_URL),
        "rtsp_camera_name": raw.get("rtsp_camera_name", settings.RTSP_CAMERA_NAME),
        "rtsp_fps": float(raw.get("rtsp_fps", settings.RTSP_FPS)),
        "rtsp_cooldown_seconds": int(raw.get("rtsp_cooldown_seconds", settings.RTSP_COOLDOWN_SECONDS)),
        "rtsp_motion_gating_enabled": raw.get("rtsp_motion_gating_enabled", "true" if settings.RTSP_MOTION_GATING_ENABLED else "false").lower() in ("true", "1", "yes"),
        "rtsp_motion_threshold": float(raw.get("rtsp_motion_threshold", settings.RTSP_MOTION_THRESHOLD)),
        "rtsp_webhook_url": raw.get("rtsp_webhook_url", settings.RTSP_WEBHOOK_URL),
        "unrecognized_track_window_seconds": int(raw.get("unrecognized_track_window_seconds", settings.UNRECOGNIZED_TRACK_WINDOW_SECONDS)),
        "webhook_only_known_faces": raw.get("webhook_only_known_faces", "true" if settings.WEBHOOK_ONLY_KNOWN_FACES else "false").lower() in ("true", "1", "yes"),
        "mqtt_only_known_faces": raw.get("mqtt_only_known_faces", "true" if settings.MQTT_ONLY_KNOWN_FACES else "false").lower() in ("true", "1", "yes"),
        "mqtt_enabled": raw.get("mqtt_enabled", "false").lower() in ("true", "1", "yes"),
        "mqtt_host": raw.get("mqtt_host", settings.MQTT_HOST),
        "mqtt_port": int(raw.get("mqtt_port", settings.MQTT_PORT)),
        "mqtt_topic": raw.get("mqtt_topic", settings.MQTT_TOPIC),
        "mqtt_user": raw.get("mqtt_user", settings.MQTT_USER),
        "mqtt_password": raw.get("mqtt_password", settings.MQTT_PASSWORD)
    }

def save_settings_bulk(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Saves multiple settings to SQLite and immediately syncs runtime memory."""
    with get_db() as conn:
        cursor = conn.cursor()
        for key, val in updates.items():
            if val is not None:
                str_val = "true" if val is True else ("false" if val is False else str(val).strip())
                cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str_val))
        conn.commit()
    sync_settings_to_runtime()
    return get_all_settings()

def update_setting(key: str, val: Any) -> Optional[str]:
    """Updates a single setting in SQLite and immediately syncs runtime memory."""
    save_settings_bulk({key: val})
    return get_setting(key)

def sync_settings_to_runtime():
    """Applies database settings immediately to the active in-memory configuration and workers."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM settings")
        raw = {row["key"]: row["value"] for row in cursor.fetchall()}

    try:
        if "face_detector_type" in raw:
            settings.FACE_DETECTOR_TYPE = raw["face_detector_type"]
            try:
                from ..core.face_engine import face_engine
                face_engine.set_detector_type(settings.FACE_DETECTOR_TYPE)
            except Exception:
                pass
        if "detection_confidence" in raw:
            settings.DETECTION_CONFIDENCE = float(raw["detection_confidence"])
        if "similarity_threshold" in raw:
            settings.SIMILARITY_THRESHOLD = float(raw["similarity_threshold"])
        if "notification_threshold" in raw:
            settings.NOTIFICATION_THRESHOLD = float(raw["notification_threshold"])
        if "notify_on_unknown" in raw:
            settings.NOTIFY_ON_UNKNOWN = raw["notify_on_unknown"].lower() in ("true", "1", "yes")
        if "unknown_min_confidence" in raw:
            settings.UNKNOWN_MIN_CONFIDENCE = float(raw["unknown_min_confidence"])
        if "det_size" in raw:
            settings.DET_SIZE = int(raw["det_size"])
            try:
                from ..core.face_engine import face_engine
                face_engine.update_det_size(settings.DET_SIZE)
            except Exception:
                pass
        if "ort_num_threads" in raw:
            settings.ORT_NUM_THREADS = int(raw["ort_num_threads"])
            os.environ["OMP_NUM_THREADS"] = str(settings.ORT_NUM_THREADS)
            os.environ["OPENBLAS_NUM_THREADS"] = str(settings.ORT_NUM_THREADS)
            os.environ["MKL_NUM_THREADS"] = str(settings.ORT_NUM_THREADS)
            os.environ["VECLIB_MAXIMUM_THREADS"] = str(settings.ORT_NUM_THREADS)
            os.environ["NUMEXPR_NUM_THREADS"] = str(settings.ORT_NUM_THREADS)
        if "max_samples_per_person" in raw:
            settings.MAX_SAMPLES_PER_PERSON = int(raw["max_samples_per_person"])
        if "rtsp_enabled" in raw:
            settings.RTSP_ENABLED = raw["rtsp_enabled"].lower() in ("true", "1", "yes")
        if "rtsp_url" in raw:
            settings.RTSP_URL = raw["rtsp_url"]
        if "rtsp_camera_name" in raw:
            settings.RTSP_CAMERA_NAME = raw["rtsp_camera_name"]
        if "rtsp_fps" in raw:
            settings.RTSP_FPS = float(raw["rtsp_fps"])
        if "rtsp_cooldown_seconds" in raw:
            settings.RTSP_COOLDOWN_SECONDS = int(raw["rtsp_cooldown_seconds"])
        if "rtsp_motion_gating_enabled" in raw:
            settings.RTSP_MOTION_GATING_ENABLED = raw["rtsp_motion_gating_enabled"].lower() in ("true", "1", "yes")
        if "rtsp_motion_threshold" in raw:
            settings.RTSP_MOTION_THRESHOLD = float(raw["rtsp_motion_threshold"])
        if "rtsp_webhook_url" in raw:
            settings.RTSP_WEBHOOK_URL = raw["rtsp_webhook_url"]
        if "unrecognized_track_window_seconds" in raw:
            settings.UNRECOGNIZED_TRACK_WINDOW_SECONDS = int(raw["unrecognized_track_window_seconds"])
        if "webhook_only_known_faces" in raw:
            settings.WEBHOOK_ONLY_KNOWN_FACES = raw["webhook_only_known_faces"].lower() in ("true", "1", "yes")
        if "mqtt_only_known_faces" in raw:
            settings.MQTT_ONLY_KNOWN_FACES = raw["mqtt_only_known_faces"].lower() in ("true", "1", "yes")
        if "mqtt_enabled" in raw:
            settings.MQTT_ENABLED = raw["mqtt_enabled"].lower() in ("true", "1", "yes")
        if "mqtt_host" in raw:
            settings.MQTT_HOST = raw["mqtt_host"]
        if "mqtt_port" in raw:
            settings.MQTT_PORT = int(raw["mqtt_port"])
        if "mqtt_topic" in raw:
            settings.MQTT_TOPIC = raw["mqtt_topic"]
        if "mqtt_user" in raw:
            settings.MQTT_USER = raw["mqtt_user"]
        if "mqtt_password" in raw:
            settings.MQTT_PASSWORD = raw["mqtt_password"]

        from ..core.events import reset_mqtt_client
        reset_mqtt_client()

        from ..core.rtsp_worker import rtsp_worker
        rtsp_worker.configure(
            url=settings.RTSP_URL,
            camera_name=settings.RTSP_CAMERA_NAME,
            fps=settings.RTSP_FPS,
            cooldown_seconds=settings.RTSP_COOLDOWN_SECONDS,
            motion_gating_enabled=settings.RTSP_MOTION_GATING_ENABLED,
            motion_threshold=settings.RTSP_MOTION_THRESHOLD
        )
    except Exception as e:
        logger.warning("Error syncing settings to runtime: %s", e)


# --- Event Log Helpers ---

def record_event_log(
    level: str,
    category: str,
    event_type: str,
    message: str,
    details: Optional[Dict[str, Any]] = None
) -> str:
    """
    Records an operational system event log.
    Automatically maintains rolling capacity by pruning logs beyond 10,000 entries.
    """
    log_id = f"evt_{uuid.uuid4().hex[:16]}"
    details_json = json.dumps(details or {})
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO event_logs (id, level, category, event_type, message, details)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (log_id, level, category, event_type, message, details_json))
            
            # Keep table size bounded: delete oldest entries beyond 10,000 rows
            cursor.execute("""
                DELETE FROM event_logs
                WHERE id IN (
                    SELECT id FROM event_logs
                    ORDER BY timestamp DESC
                    LIMIT -1 OFFSET 10000
                )
            """)
            conn.commit()
    except Exception as e:
        logger.debug("Failed to record event log in database: %s", e)
    return log_id


def get_event_logs(
    limit: int = 100,
    offset: int = 0,
    category: Optional[str] = None,
    level: Optional[str] = None,
    search: Optional[str] = None
) -> Dict[str, Any]:
    """Retrieve filtered event logs with total count."""
    with get_db() as conn:
        cursor = conn.cursor()
        query = "SELECT id, timestamp, level, category, event_type, message, details, created_at FROM event_logs WHERE 1=1"
        count_query = "SELECT COUNT(*) FROM event_logs WHERE 1=1"
        params: List[Any] = []

        if category and category.lower() != "all":
            query += " AND category = ?"
            count_query += " AND category = ?"
            params.append(category.lower())

        if level and level.lower() != "all":
            query += " AND level = ?"
            count_query += " AND level = ?"
            params.append(level.lower())

        if search:
            query += " AND (message LIKE ? OR details LIKE ? OR event_type LIKE ?)"
            count_query += " AND (message LIKE ? OR details LIKE ? OR event_type LIKE ?)"
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])

        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        cursor.execute(query, params + [limit, offset])
        rows = cursor.fetchall()

        logs = []
        for r in rows:
            item = dict(r)
            try:
                item["details"] = json.loads(item.get("details") or "{}")
            except Exception:
                item["details"] = {}
            logs.append(item)

        return {
            "total": total,
            "logs": logs
        }


def clear_event_logs(category: Optional[str] = None, before_date: Optional[str] = None) -> int:
    """Clears matching or all event logs from the database."""
    with get_db() as conn:
        cursor = conn.cursor()
        query = "DELETE FROM event_logs WHERE 1=1"
        params: List[Any] = []

        if category and category.lower() != "all":
            query += " AND category = ?"
            params.append(category.lower())

        if before_date:
            query += " AND timestamp < ?"
            params.append(before_date)

        cursor.execute(query, params)
        deleted_count = cursor.rowcount
        conn.commit()
        return deleted_count


def get_event_log_summary() -> Dict[str, Any]:
    """Calculates operational summary statistics for the Event Log dashboard."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM event_logs")
        total_events = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM event_logs WHERE level = 'error' AND datetime(timestamp) >= datetime('now', '-24 hours')")
        error_count_24h = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM event_logs WHERE category = 'motion' AND DATE(timestamp) = DATE('now')")
        motion_transitions_today = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM event_logs WHERE category = 'detection' AND DATE(timestamp) = DATE('now')")
        detections_today = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM event_logs WHERE category IN ('webhook', 'mqtt') AND DATE(timestamp) = DATE('now')")
        broadcasts_today = cursor.fetchone()[0]

        return {
            "total_events": total_events,
            "error_count_24h": error_count_24h,
            "motion_transitions_today": motion_transitions_today,
            "detections_today": detections_today,
            "broadcasts_today": broadcasts_today
        }
