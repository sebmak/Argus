# FaceEngine Android Companion App

A native Android companion app for **Household FaceEngine**, allowing you to manage facial recognition, inspect live detection streams, review unknown visitors, and configure server parameters directly from your Android phone or tablet while at home.

---

## 📱 Features

* **Custom Server Discovery & Storage**:
  * Onboarding screen to define and persist your Unraid server LAN IP (e.g. `192.168.1.104`) or reverse-proxy domain.
  * Real-time **Test Connection** button that pings the server `/health` endpoint and displays live engine telemetry, version, and model status.
  * Switch servers anytime from the top app menu.
* **Full Feature Parity with Web App**:
  * **Dashboard**: Household stats, recent detections feed, accuracy metrics.
  * **Review Queue**: Review unknown faces, assign to persons, reject false detections.
  * **Household Directory**: Manage members, upload reference photos, inspect embedding counts.
  * **Interactive Test Sandbox**: Upload and test photos from your Android gallery or camera with bounding box overlays.
  * **RTSP & MQTT Stream Monitor**: Real-time snapshots, worker controls, threshold adjustments.
  * **Operational Event Log**: Idle transitions, detections, webhooks, MQTT broadcasts, error logs.
  * **Settings**: Configure model parameters and database migrations.
* **Native Android Integration**:
  * **Seamless Back Navigation**: Hardware back gesture/button steps backwards through HTML5 page history before exiting.
  * **Pull-to-Refresh**: Swipe down from top to refresh live telemetry and data.
  * **Persistent Authentication**: Native `CookieManager` retains secure session cookies.
  * **Media Uploads**: Native Android file picker integration for image testing and member photo uploads.
  * **Local Network Cleartext Traffic**: Configured with `usesCleartextTraffic="true"` to support LAN HTTP connections (e.g. `http://192.168.1.104:8000`).

---

## 🛠️ Building & Running in Android Studio

1. Open **Android Studio**.
2. Select **Open** and choose the `android/` folder inside this repository:
   ```
   /path/to/FaceDetection/android
   ```
3. Let Gradle sync project dependencies.
4. Connect an Android device (via USB with USB debugging enabled or wireless debugging) or launch an Android Virtual Device (AVD).
5. Click **Run 'app'** (`Shift + F10`) or build the APK via **Build > Build Bundle(s) / APK(s) > Build APK(s)**.

---

## ⚙️ Configuration

* **Min SDK**: API 26 (Android 8.0 Oreo)
* **Target SDK**: API 35 (Android 15)
* **Build System**: Gradle Kotlin DSL (`build.gradle.kts`)
