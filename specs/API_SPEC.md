# FaceEngine Shared API Specification & Client Data Contracts

This specification defines the complete REST API contract and WebSocket/Polling schemas for **FaceEngine**. It serves as the single source of truth ensuring feature parity and contract synchronization between the **Web Application (`frontend/`)** and the **Native Android Compose Application (`android/`)**.

---

## 1. Authentication & Session Management

All management endpoints require authentication. Clients may authenticate via:
* **Cookie**: `session_id=<token>` (HTTP-only session cookie)
* **Bearer Token**: `Authorization: Bearer <token>` in HTTP headers

### `POST /api/v1/auth/login`
Authenticates user credentials and initiates a session.
* **Request Body** (`application/json`):
  ```json
  {
    "username": "admin",
    "password": "yourpassword"
  }
  ```
* **Response** (`200 OK`):
  ```json
  {
    "access_token": "eyJhbGciOi...",
    "token_type": "bearer",
    "expires_in": 86400,
    "username": "admin"
  }
  ```
* **Cookie**: Sets `session_id` with `SameSite=lax; HttpOnly`.

### `GET /api/v1/auth/me`
Retrieves current session identity.
* **Response** (`200 OK`):
  ```json
  {
    "id": "admin",
    "username": "admin"
  }
  ```
* **Errors**: `401 Unauthorized` if invalid or expired.

### `POST /api/v1/auth/logout`
Terminates the session and expires the session cookie.
* **Response** (`200 OK`):
  ```json
  {
    "message": "Logged out successfully"
  }
  ```

---

## 2. System Health & Telemetry

### `GET /health` (Public)
Public readiness probe for Docker, Unraid, and client ping tests.
* **Response** (`200 OK`):
  ```json
  {
    "status": "healthy",
    "app": "Household Face Detection",
    "version": "0.0.15",
    "model": "buffalo_l",
    "engine_ready": true
  }
  ```

### `GET /api/v1/stats`
Telemetry metrics for dashboard cards and review badge counts.
* **Response** (`200 OK`):
  ```json
  {
    "total_persons": 4,
    "household_count": 3,
    "visitor_count": 1,
    "total_samples": 28,
    "unrecognized_count": 2,
    "accuracy_rate": 96.5,
    "face_detector_type": "yolov8_face",
    "det_size": 320,
    "ort_num_threads": 8,
    "recent_activity": [
      {
        "id": "det_1829102",
        "timestamp": 1728591230.12,
        "matched_name": "Sebastian",
        "similarity": 0.82,
        "is_household": true,
        "status": "matched",
        "thumbnail_path": "det_1829102.jpg",
        "thumbnail_url": "/api/v1/thumbnails/det_1829102.jpg",
        "camera_id": "Front Door RTSP"
      }
    ]
  }
  ```

---

## 3. Household Persons Directory

### `GET /api/v1/persons`
List all registered members and visitors.
* **Response** (`200 OK`):
  ```json
  [
    {
      "id": 1,
      "name": "Sebastian",
      "is_household": true,
      "sample_count": 12,
      "thumbnail_url": "/api/v1/thumbnails/p1_sample1.jpg",
      "created_at": "2026-10-01T12:00:00Z"
    }
  ]
  ```

### `POST /api/v1/persons`
Create a new household member or visitor.
* **Request Body** (`application/json`):
  ```json
  {
    "name": "Alice",
    "is_household": true,
    "notes": "Primary resident"
  }
  ```
* **Response** (`201 Created`): Returns created `Person`.

### `GET /api/v1/persons/{id}`
Retrieve person details including all learned photo embeddings.
* **Response** (`200 OK`):
  ```json
  {
    "id": 1,
    "name": "Sebastian",
    "is_household": true,
    "sample_count": 2,
    "samples": [
      {
        "id": 101,
        "thumbnail_url": "/api/v1/thumbnails/sample_101.jpg",
        "created_at": "2026-10-05T14:30:00Z",
        "camera_name": "UniFi Front Porch"
      }
    ]
  }
  ```

### `DELETE /api/v1/persons/{id}`
Deletes member and all associated face embeddings.
* **Response** (`200 OK`): `{ "deleted": true }`

### `POST /api/v1/persons/{id}/photos`
Upload and extract embeddings from a new reference photo.
* **Request**: `multipart/form-data` with `file` (image JPEG/PNG).
* **Response** (`200 OK`):
  ```json
  {
    "success": true,
    "faces_extracted": 1,
    "sample_id": 102
  }
  ```

---

## 4. Review Queue (Unrecognized Faces)

### `GET /api/v1/detections/unrecognized`
Retrieves unknown arrivals waiting for human review.
* **Response** (`200 OK`):
  ```json
  [
    {
      "id": 42,
      "timestamp": 1728591830.4,
      "camera_id": "Front Door",
      "thumbnail_url": "/api/v1/thumbnails/unknown_42.jpg",
      "confidence": 0.89
    }
  ]
  ```

### `POST /api/v1/detections/{id}/assign`
Assign an unrecognized detection crop to an existing or new person.
* **Request Body** (`application/json`):
  ```json
  {
    "person_id": 1,
    "new_person_name": null
  }
  ```
* **Response** (`200 OK`):
  ```json
  {
    "assigned": true,
    "person_id": 1,
    "person_name": "Sebastian"
  }
  ```

### `DELETE /api/v1/detections/{id}`
Rejects/dismisses an unrecognized face.
* **Response** (`200 OK`): `{ "dismissed": true }`

---

## 5. Live RTSP & Motion Ingestion

### `GET /api/v1/rtsp/status`
Telemetry for the continuous RTSP camera ingestion worker.
* **Response** (`200 OK`):
  ```json
  {
    "running": true,
    "url": "rtsp://192.168.1.1:554/s0",
    "camera_name": "Front Door RTSP",
    "fps": 3.0,
    "frames_processed": 14209,
    "motion_gated": true,
    "idle_mode": false,
    "cooldown_seconds": 30
  }
  ```

### `POST /api/v1/rtsp/start`
Starts background frame sampling and face inference.
* **Response** (`200 OK`): `{ "status": "started" }`

### `POST /api/v1/rtsp/stop`
Pauses background camera ingestion.
* **Response** (`200 OK`): `{ "status": "stopped" }`

### `GET /api/v1/rtsp/snapshot`
Returns the latest raw camera frame.
* **Response** (`200 OK`): `image/jpeg` binary stream.

---

## 6. Test Sandbox Recognition

### `POST /api/v1/recognize`
Runs full pipeline (YOLOv8-Face/SCRFD + ArcFace Buffalo_L) on a frame.
* **Request Body** (`application/json`):
  ```json
  {
    "image": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
    "camera_name": "Sandbox Test",
    "min_confidence": 0.50,
    "similarity_threshold": 0.45
  }
  ```
* **Response** (`200 OK`):
  ```json
  {
    "success": true,
    "faces_detected": 1,
    "faces": [
      {
        "bbox": [120, 85, 290, 310],
        "confidence": 0.94,
        "matched_name": "Sebastian",
        "similarity": 0.78,
        "is_household": true,
        "is_visitor": false
      }
    ]
  }
  ```

---

## 7. Operational Event Log & Telemetry

### `GET /api/v1/events`
Query operational events with category, severity, and pagination filters.
* **Query Parameters**:
  * `category` (optional): `detection`, `motion`, `webhook`, `mqtt`, `system`
  * `severity` (optional): `info`, `warning`, `error`
  * `limit` (default: 50)
  * `offset` (default: 0)
* **Response** (`200 OK`):
  ```json
  {
    "total": 128,
    "limit": 50,
    "offset": 0,
    "events": [
      {
        "id": 128,
        "timestamp": "2026-10-10T21:00:00Z",
        "category": "detection",
        "severity": "info",
        "message": "Recognized Sebastian (78% match) on Front Door",
        "details": { "similarity": 0.78, "camera": "Front Door" }
      }
    ]
  }
  ```

---

## 8. Settings & Configuration

### `GET /api/v1/settings`
Returns current engine, camera, and notification configuration.
* **Response** (`200 OK`): Full settings object.

### `PUT /api/v1/settings`
Updates server configuration in SQLite (`faces.db`).
* **Request Body** (`application/json`): Partial or full settings update.
* **Response** (`200 OK`): Updated settings.
