<p align="center">
  <img src="assets/logo.png" alt="FaceEngine Logo" width="140" height="140" style="border-radius: 28px;" />
</p>

# Household Face Detection API & Web Dashboard

A self-hosted, privacy-first Docker container providing real-time face detection, recognition, and auto-training capabilities for your household, built for seamless integration with **Unraid**, **UniFi Protect**, and **Home Assistant**.

---

## 🚀 Key Features

* **General Face Recognition Endpoint (`POST /api/v1/recognize`)**:
  * Accepts base64 encoded images.
  * Detects all faces in frame using RetinaFace / SCRFD.
  * Extracts 512-dimensional ArcFace embeddings and matches against known household members.
  * Unrecognized faces are automatically logged to the **Review Inbox** in the Web UI.

* **UniFi Protect Auto-Training Webhook (`PUT /api/v1/protect/webhook`)**:
  * Parses alerts and base64 snapshots directly from **Home Assistant** and **UniFi Protect**.
  * When a camera identifies a known member, it automatically extracts their new face embedding and updates their profile centroid, making recognition progressively smarter under diverse lighting and angles.

* **Modern React 19 + TypeScript Glassmorphism Web App**:
  * **Secure Authentication Gate**: Access to the dashboard, camera previews, and admin endpoints is strictly protected by session authentication with secure HttpOnly cookies (`SameSite=lax`). Visitors without an active session cannot view any feeds or data.
  * **Modular React Architecture**: Re-architected from monolithic legacy scripts to clean, typed React 19 components with Vite, custom Lucide iconography, and glassmorphic styling tokens.
  * **Dashboard**: Real-time detection counters, member counts, and live activity stream.
  * **Review Queue**: Visual gallery of unrecognized face detections with 1-click assignment to existing members or new entities.
  * **Household Directory**: Manage household members, inspect 512-d embeddings and multi-angle photo samples, or upload extra reference angles.
  * **Interactive Test Sandbox**: Drag-and-drop playground with live overlaid bounding boxes, identity tags, and similarity scores.
  * **RTSP & MQTT Console**: Real-time camera monitor, worker thread controls, webhook filtering policies, and broker credentials.
  * **Database Migrations Manager**: Live schema roll forward and rollback controls with automatic SQLite snapshots.

* **Real-Time RTSP Stream & MQTT Events**:
  * Continuous background video ingestion on a **dedicated worker thread** (never blocks the REST API).
  * Automated identity recognition with configurable **alert cooldowns** (e.g. 30s) to prevent spamming notifications.
  * **Configurable Notification Threshold**: Set custom confidence/similarity thresholds before outgoing alerts are sent to prevent borderline/marginal matches from triggering home automations.
  * Emits event notifications to outgoing **Webhooks** (Home Assistant) and **MQTT Brokers** (`facedetection/events`).
  * Live monitoring preview and on-the-fly stream control directly in the Web Dashboard.

* **⚙️ Live Admin Console & SQLite Configuration**:
  * Adjust detection confidence, known member similarity thresholds, notification thresholds, RTSP feeds, and MQTT broker settings directly inside the **⚙️ Settings** tab.
  * Changes are persistently saved to SQLite (`faces.db`) and immediately synchronized across running background workers without restarting the Docker container!

* **📱 Native Android Companion App (`android/`)**:
  * Dedicated companion app with custom server IP/domain configurator and local persistent storage.
  * Real-time connectivity tester pinging the server `/health` endpoint before connecting.
  * Full feature parity with the web dashboard, hardware back-navigation for tab history, pull-to-refresh, and image upload picker.

* **Unraid & CPU Optimized**:
  * Native Unraid `/config` path support.
  * Non-root permission management via `PUID=99` / `PGID=100` (`nobody:users`), preventing file permission lockouts on your cache/array.
  * Runs on **ONNX Runtime (CPUExecutionProvider)** across Intel/AMD (`linux/amd64`) and ARM (`linux/arm64`) architectures (Apple Silicon, Raspberry Pi 5, Proxmox, Synology NAS).

---

## 🖥️ Unraid Installation Guide

### Method A: Using the Included Unraid Template (Recommended)
1. Copy [unraid/face-detection.xml](file:///Users/sebastianmakinson/FaceDetection/unraid/face-detection.xml) to your Unraid flash drive:
   ```bash
   /boot/config/plugins/dockerMan/templates-user/my-FaceDetection.xml
   ```
2. In the Unraid WebGUI, navigate to the **Docker** tab and click **Add Container**.
3. Under **Template**, select **FaceDetection**.
4. Review the parameters (defaults are prefilled) and click **Apply**.

### Method B: Manual Unraid Docker Configuration
If adding manually via the Unraid WebGUI:

| Unraid Setting | Recommended Value | Description |
|---|---|---|
| **Name** | `FaceDetection` | Container display name |
| **Repository** | `household-face-detection:latest` *(or your local build)* | Docker image |
| **Network Type** | `bridge` | Standard bridge or custom network |
| **Port 1 (WebUI & API)** | Container: `8000` / Host: `8000` | Port for Web Dashboard & API |
| **Path 1 (Config / SQLite)** | Container: `/config` <br> Host: `/mnt/user/appdata/facedetection` | Stores `faces.db`, models, and face thumbnails |
| **Variable: PUID** | `99` | User ID (`nobody` on Unraid) |
| **Variable: PGID** | `100` | Group ID (`users` on Unraid) |
| **Variable: UMASK** | `002` | Standard file permission mask |
| **Variable: FACE_MODEL_NAME** | `buffalo_l` | `buffalo_l` (high accuracy) or `buffalo_s` (ultra-fast) |
| **Variable: ORT_NUM_THREADS** | `8` | Limit threads to 4-8 (prevents 98-core thread thrashing) |
| **Variable: DET_SIZE** | `320` | Detection size: `320` (~20-50ms), `480` (balanced), `640` (max range) |
| **Variable: MAX_IMAGE_SIZE** | `1280` | Downscale 4K/2K frames to max 1280px before inference |
| **Variable: SIMILARITY_THRESHOLD** | `0.45` | Known member cosine similarity threshold (0.40 - 0.55) |
| **Variable: DETECTION_CONFIDENCE** | `0.50` | Face bounding box detection confidence threshold |
| **Variable: NOTIFICATION_THRESHOLD** | `0.55` | Min similarity score required before firing an outgoing webhook/MQTT alert |
| **Variable: NOTIFY_ON_UNKNOWN** | `true` | Dispatch notifications for unknown visitor faces (`true`/`false`) |
| **Variable: UNKNOWN_MIN_CONFIDENCE** | `0.60` | Min face confidence for unknown alerts (filters false positives) |
| **Variable: DEFAULT_ADMIN_USER** | `admin` | Initial dashboard username |
| **Variable: DEFAULT_ADMIN_PASSWORD**| `admin123` | Initial dashboard password |

> 💡 **Tip**: All detection thresholds, notification rules, RTSP streams, and MQTT broker options can be edited and tested live in the **⚙️ Settings** tab of the Web Dashboard without needing to edit environment variables or restart the container!

### 📂 Where Your Data is Stored on Unraid
All persistent data resides inside your mapped appdata directory (e.g. `/mnt/user/appdata/facedetection`):
* `/mnt/user/appdata/facedetection/faces.db`: SQLite database storing registered persons, face embeddings, and detection history.
* `/mnt/user/appdata/facedetection/thumbnails/`: Cropped thumbnail images of detected and learned faces.
* `/mnt/user/appdata/facedetection/models/`: Cached InsightFace ONNX models.

---

## 📦 Quickstart with Docker Compose (Non-Unraid or Local Dev)

Clone the repository and launch the container:

```bash
docker compose up -d --build
```

The container will start on port `8000` and persist data in `./data` (mapped to `/config` in the container).

### Access the Web Dashboard
Open your browser and navigate to:
```
http://<YOUR_SERVER_IP>:8000
```
* **Default Username**: `admin`
* **Default Password**: `admin123` *(configurable via environment variables)*

---

## 🔌 Home Assistant & UniFi Protect Configuration

### Webhook Automation Example
In Home Assistant, create an automation that forwards detection snapshots to this container:

```yaml
alias: "UniFi Protect - Train Face Recognition"
description: "Pushes UniFi Protect face detection snapshots to the FaceID container"
trigger:
  - platform: webhook
    webhook_id: unifi_protect_face_alert
condition:
  - condition: template
    value_template: "{{ trigger.json.triggers[0].key == 'face_known' }}"
action:
  - service: rest_command.feed_face_container
    data:
      person_name: "{{ trigger.json.triggers[0].value }}"
      snapshot: "{{ trigger.json.thumbnail }}"
      camera_id: "{{ trigger.json.triggers[0].sourceEvent.camera }}"
      event_id: "{{ trigger.json.triggers[0].eventId }}"
```

### Direct REST Command (`configuration.yaml`)
```yaml
rest_command:
  feed_face_container:
    url: "http://<UNRAID_OR_DOCKER_IP>:8000/api/v1/protect/webhook"
    method: "POST"
    headers:
      Content-Type: "application/json"
    payload: >
      {
        "person_name": "{{ person_name }}",
        "snapshot": "{{ snapshot }}",
        "camera_id": "{{ camera_id }}",
        "event_id": "{{ event_id }}"
      }
```

---

## 📡 Real-Time RTSP Stream & MQTT Events

In addition to REST endpoints, the container includes an embedded **RTSP video engine** running in a dedicated background worker thread:

1. **Configure via Web Dashboard**:
   * Navigate to the **📡 RTSP & MQTT** tab.
   * Paste your camera stream URL (e.g. `rtsp://user:pass@192.168.1.10:7447/stream`).
   * Set your sampling rate (e.g. `3.0 FPS`), alert cooldown (e.g. `30s`), and optional MQTT broker details.
   * Click **Start Stream** for live monitoring and real-time detection telemetry.

2. **Event Payload**:
   Whenever a person is detected (or unknown face appears), the container immediately emits an event payload to your configured Webhook URL and MQTT topic (`facedetection/events`):
   ```json
   {
     "event": "face_detection",
     "camera": "Front Door RTSP",
     "person_name": "Sebastian",
     "match": true,
     "similarity": 0.84,
     "distance": 0.16,
     "timestamp": 1728340020.5,
     "thumbnail_url": "/api/v1/thumbnails/crop_5961b6.jpg",
     "thumbnail_base64": "data:image/jpeg;base64,...",
     "bbox": [140, 95, 275, 250]
   }
   ```
   * *Cooldown protection*: A detected person is suppressed from re-triggering notifications for the duration of `RTSP_COOLDOWN_SECONDS`, preventing repeated alert spam while remaining in view.

---

## 📡 API Reference

Interactive OpenAPI documentation is available at `http://<SERVER_IP>:8000/docs`.

### 1. Recognize Faces
```bash
curl -X POST http://<SERVER_IP>:8000/api/v1/recognize \
  -H "Content-Type: application/json" \
  -d '{
    "image": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
    "min_confidence": 0.50,
    "similarity_threshold": 0.45,
    "camera_id": "front_door",
    "save_unrecognized": true
  }'
```

**Response:**
```json
{
  "count": 1,
  "faces": [
    {
      "bbox": { "x1": 120, "y1": 80, "x2": 260, "y2": 240, "width": 140, "height": 160 },
      "detection_confidence": 0.98,
      "match": true,
      "person_id": "p_8f9e12...",
      "name": "Sebastian",
      "similarity": 0.82,
      "distance": 0.18,
      "sample_count": 12,
      "thumbnail_url": "/api/v1/thumbnails/crop_a1b2c3.jpg"
    }
  ],
  "unrecognized_count": 0,
  "latency_ms": 68.4
}
```

### 2. Ingest Protect Webhook (POST or PUT)
```bash
curl -X POST http://<SERVER_IP>:8000/api/v1/protect/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "person_name": "Sebastian",
    "snapshot": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
    "camera_id": "front_door_g4_pro"
  }'
```

---

## ⚙️ Configuration & Environment Variables

| Variable | Default | Description |
|---|---|---|
| `CONFIG_DIR` | `/config` | Path to persistent configuration volume (SQLite, thumbnails, models) |
| `PUID` | `99` | User ID for Unraid file permissions (`nobody`) |
| `PGID` | `100` | Group ID for Unraid file permissions (`users`) |
| `UMASK` | `002` | Permissions mask for created files |
| `FACE_MODEL_NAME` | `buffalo_l` | Model profile: `buffalo_l` (high accuracy) or `buffalo_s` (ultra-fast) |
| `ORT_NUM_THREADS` | `8` | OpenMP/ONNX thread limit (4-8 prevents 98-core thread contention) |
| `DET_SIZE` | `320` | Detection size: `320` (~20-50ms), `480` (balanced), `640` (max range) |
| `MAX_IMAGE_SIZE` | `1280` | Downscale 4K/2K frames to max dimension before inference |
| `SIMILARITY_THRESHOLD` | `0.45` | Cosine similarity match threshold (0.40 - 0.55 recommended) |
| `DETECTION_CONFIDENCE` | `0.50` | Minimum confidence score to register a face |
| `MAX_SAMPLES_PER_PERSON` | `50` | Maximum sample vectors stored per person (auto-prunes oldest) |
| `DEFAULT_ADMIN_USER` | `admin` | Initial administrator username |
| `DEFAULT_ADMIN_PASSWORD` | `admin123`| Initial administrator password |
| `WEBHOOK_SECRET` | *(empty)* | Optional secret key verified via `X-Webhook-Secret` header |
| `RTSP_ENABLED` | `false` | Auto-start real-time RTSP background worker on container boot |
| `RTSP_URL` | *(empty)* | RTSP/RTSPS video feed URL |
| `RTSP_CAMERA_NAME` | `Front Door RTSP` | Display label for camera source |
| `RTSP_FPS` | `3.0` | Inference sampling frequency (2-5 FPS recommended) |
| `RTSP_COOLDOWN_SECONDS` | `30` | Minimum seconds between repeat alerts for the same person |
| `RTSP_WEBHOOK_URL` | *(empty)* | Outgoing webhook endpoint URL (e.g. Home Assistant webhook) |
| `WEBHOOK_ONLY_KNOWN_FACES` | `false` | Restrict outgoing webhooks strictly to recognized household members (suppress for unknown faces) |
| `NOTIFICATION_THRESHOLD` | `0.55` | Minimum similarity score required before firing an outgoing webhook/MQTT event |
| `NOTIFY_ON_UNKNOWN` | `true` | Send outgoing notifications for unrecognized visitor faces |
| `UNKNOWN_MIN_CONFIDENCE` | `0.60` | Minimum face confidence required for unknown alerts |
| `MQTT_ENABLED` | `false` | Publish real-time detection JSON events to an MQTT broker |
| `MQTT_HOST` | *(empty)* | MQTT broker IP or hostname |
| `MQTT_PORT` | `1883` | MQTT broker port |
| `MQTT_TOPIC` | `facedetection/events` | Base topic for MQTT events |

---

## 🗄️ Database Migrations, Roll Forward & Rollback Safety

The container includes a built-in, non-destructive SQLite migration engine:
* **Automatic Roll Forward**: When starting up or upgrading to a newer application version (e.g. `v1.1.0`), all pending migrations are applied in sequential order.
* **Automatic Server Rollback Detection**: If you ever downgrade your container image or server release (e.g. from `v1.1.0` back to `v1.0.0`), the system automatically detects that the database schema is ahead of the container version. It safely executes rollbacks, preserves your household members and face embeddings, backs up configurations into backup tables, and takes an atomic database snapshot before downgrading.
* **Pre-Migration Backups**: Atomic snapshots (`faces.db.pre_migration_*.bak` / `faces.db.pre_rollback_*.bak`) are stored in `/config` with automated rolling retention.
* **Web UI Management**: Check migration history and trigger rollbacks or forward sync directly in the **⚙️ Settings** tab.
* **CLI Migration Tool**:
  ```bash
  # Check migration status
  python -m app.db.migrations --status

  # Roll back to a previous app version (e.g. 1.0.0)
  python -m app.db.migrations --rollback 1.0.0

  # Roll forward to target app version (e.g. 1.1.0)
  python -m app.db.migrations --forward 1.1.0
  ```

