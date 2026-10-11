package com.facedetection.app.data

import android.util.Base64
import com.facedetection.app.data.models.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * Rules for FaceEngineApiClient:
 * 1. Variables must be declared at the top of the class.
 * 2. All network requests must use Coroutines with Dispatchers.IO.
 * 3. Class documentation comments must be maintained for all changes.
 * 4. Strictly adheres to specs/API_SPEC.md data contracts, security headers, and error formats.
 * 5. Handles session authentication, password management, and rate-limiting responses gracefully.
 */
class FaceEngineApiClient(private val configManager: ServerConfigManager) {

    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()
    private val httpClient: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(8, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .build()

    fun getBaseUrl(): String {
        return configManager.getBaseUrl() ?: "http://127.0.0.1:8000"
    }

    suspend fun testConnection(baseUrl: String): Boolean = withContext(Dispatchers.IO) {
        configManager.testConnection(baseUrl).isSuccess
    }

    private fun buildRequest(path: String, method: String = "GET", body: RequestBody? = null): Request {
        val baseUrl = configManager.getBaseUrl() ?: throw IllegalStateException("Server URL not configured")
        val url = baseUrl.trimEnd('/') + path
        val builder = Request.Builder().url(url)

        val token = configManager.getAuthToken()
        if (!token.isNullOrBlank()) {
            builder.addHeader("Authorization", "Bearer $token")
            builder.addHeader("Cookie", "session_id=$token")
        }

        when (method.uppercase()) {
            "GET" -> builder.get()
            "POST" -> builder.post(body ?: "".toRequestBody(jsonMediaType))
            "PUT" -> builder.put(body ?: "".toRequestBody(jsonMediaType))
            "DELETE" -> builder.delete(body)
        }

        return builder.build()
    }

    suspend fun login(password: String): Result<LoginResponse> {
        return login("admin", password)
    }

    suspend fun login(username: String, password: String): Result<LoginResponse> = withContext(Dispatchers.IO) {
        try {
            val json = JSONObject().apply {
                put("username", username)
                put("password", password)
            }
            val request = buildRequest("/api/v1/auth/login", "POST", json.toString().toRequestBody(jsonMediaType))
            val response = httpClient.newCall(request).execute()

            if (!response.isSuccessful) {
                val errBody = response.body?.string()
                val detail = try {
                    JSONObject(errBody ?: "").optString("detail")
                } catch (e: Exception) { null }
                val errorMsg = if (!detail.isNullOrBlank()) detail else "Login failed: ${response.code} ${response.message}"
                return@withContext Result.failure(Exception(errorMsg))
            }

            val body = response.body?.string() ?: return@withContext Result.failure(Exception("Empty login response"))
            val resObj = JSONObject(body)
            val token = resObj.getString("access_token")
            configManager.saveAuthToken(token)

            val loginRes = LoginResponse(
                accessToken = token,
                tokenType = resObj.optString("token_type", "bearer"),
                expiresIn = resObj.optLong("expires_in", 86400),
                username = resObj.optString("username", username),
                isDefaultPassword = resObj.optBoolean("is_default_password", false)
            )
            Result.success(loginRes)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getCurrentUser(): Result<User> = withContext(Dispatchers.IO) {
        try {
            val request = buildRequest("/api/v1/auth/me")
            val response = httpClient.newCall(request).execute()
            if (!response.isSuccessful) {
                return@withContext Result.failure(Exception("Failed to verify session (${response.code})"))
            }

            val body = response.body?.string() ?: return@withContext Result.failure(Exception("Empty user profile response"))
            val json = JSONObject(body)
            val user = User(
                id = json.optString("id", "1"),
                username = json.optString("username", "admin"),
                isDefaultPassword = json.optBoolean("is_default_password", false)
            )
            Result.success(user)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun changePassword(currentPassword: String, newPassword: String): Result<Boolean> = withContext(Dispatchers.IO) {
        try {
            val json = JSONObject().apply {
                put("current_password", currentPassword)
                put("new_password", newPassword)
            }
            val request = buildRequest("/api/v1/auth/change-password", "POST", json.toString().toRequestBody(jsonMediaType))
            val response = httpClient.newCall(request).execute()

            if (!response.isSuccessful) {
                val errBody = response.body?.string()
                val detail = try {
                    JSONObject(errBody ?: "").optString("detail")
                } catch (e: Exception) { null }
                val errorMsg = if (!detail.isNullOrBlank()) detail else "Failed to update password (${response.code})"
                return@withContext Result.failure(Exception(errorMsg))
            }

            val body = response.body?.string() ?: ""
            if (body.isNotBlank()) {
                val resObj = JSONObject(body)
                val refreshedToken = resObj.optString("access_token")
                if (refreshedToken.isNotBlank()) {
                    configManager.saveAuthToken(refreshedToken)
                }
            }
            Result.success(true)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getStats(): Result<SystemStats> = withContext(Dispatchers.IO) {
        try {
            val request = buildRequest("/api/v1/stats")
            val response = httpClient.newCall(request).execute()
            if (!response.isSuccessful) {
                return@withContext Result.failure(Exception("Failed to load stats: ${response.code}"))
            }

            val body = response.body?.string() ?: return@withContext Result.failure(Exception("Empty stats response"))
            val json = JSONObject(body)

            val activityList = mutableListOf<RecentActivity>()
            val actArray = json.optJSONArray("recent_activity") ?: JSONArray()
            for (i in 0 until actArray.length()) {
                val item = actArray.getJSONObject(i)
                activityList.add(
                    RecentActivity(
                        id = item.optString("id", "$i"),
                        timestamp = item.optDouble("timestamp", 0.0),
                        matchedName = item.optStringOrNull("matched_name"),
                        similarity = if (item.has("similarity")) item.getDouble("similarity").toFloat() else null,
                        isHousehold = if (item.has("is_household")) item.getBoolean("is_household") else null,
                        status = item.optString("status", "unknown"),
                        thumbnailPath = item.optStringOrNull("thumbnail_path"),
                        thumbnailUrl = item.optStringOrNull("thumbnail_url"),
                        cameraId = item.optStringOrNull("camera_id")
                    )
                )
            }

            val stats = SystemStats(
                totalPersons = json.optInt("total_persons", 0),
                householdCount = json.optInt("household_count", 0),
                visitorCount = json.optInt("visitor_count", 0),
                totalSamples = json.optInt("total_samples", 0),
                unrecognizedCount = json.optInt("unrecognized_count", 0),
                accuracyRate = json.optDouble("accuracy_rate", 0.0).toFloat(),
                faceDetectorType = json.optString("face_detector_type", "yolov8_face"),
                detSize = json.optInt("det_size", 320),
                ortNumThreads = json.optInt("ort_num_threads", 8),
                recentActivity = activityList
            )
            Result.success(stats)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getPersons(): Result<List<Person>> = withContext(Dispatchers.IO) {
        try {
            val request = buildRequest("/api/v1/persons")
            val response = httpClient.newCall(request).execute()
            if (!response.isSuccessful) {
                return@withContext Result.failure(Exception("Failed to load persons: ${response.code}"))
            }

            val body = response.body?.string() ?: return@withContext Result.failure(Exception("Empty persons response"))
            val array = JSONArray(body)
            val list = mutableListOf<Person>()
            for (i in 0 until array.length()) {
                val item = array.getJSONObject(i)
                list.add(
                    Person(
                        id = item.getInt("id"),
                        name = item.getString("name"),
                        isHousehold = item.optBoolean("is_household", true),
                        sampleCount = item.optInt("sample_count", 0),
                        thumbnailUrl = item.optStringOrNull("thumbnail_url"),
                        createdAt = item.optStringOrNull("created_at")
                    )
                )
            }
            Result.success(list)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun addPerson(name: String, isHousehold: Boolean = true): Result<Person> = withContext(Dispatchers.IO) {
        try {
            val json = JSONObject().apply {
                put("name", name)
                put("is_household", isHousehold)
            }
            val request = buildRequest("/api/v1/persons", "POST", json.toString().toRequestBody(jsonMediaType))
            val response = httpClient.newCall(request).execute()
            if (!response.isSuccessful) {
                return@withContext Result.failure(Exception("Failed to add member: ${response.code}"))
            }

            val body = response.body?.string() ?: return@withContext Result.failure(Exception("Empty response"))
            val item = JSONObject(body)
            val person = Person(
                id = item.getInt("id"),
                name = item.getString("name"),
                isHousehold = item.optBoolean("is_household", true),
                sampleCount = item.optInt("sample_count", 0),
                thumbnailUrl = item.optStringOrNull("thumbnail_url")
            )
            Result.success(person)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun deletePerson(personId: Int): Result<Boolean> = withContext(Dispatchers.IO) {
        try {
            val request = buildRequest("/api/v1/persons/$personId", "DELETE")
            val response = httpClient.newCall(request).execute()
            Result.success(response.isSuccessful)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getUnrecognizedDetections(): Result<List<UnrecognizedDetection>> = withContext(Dispatchers.IO) {
        try {
            val request = buildRequest("/api/v1/detections/unrecognized")
            val response = httpClient.newCall(request).execute()
            if (!response.isSuccessful) {
                return@withContext Result.failure(Exception("Failed to load review queue: ${response.code}"))
            }

            val body = response.body?.string() ?: return@withContext Result.failure(Exception("Empty review queue"))
            val array = JSONArray(body)
            val list = mutableListOf<UnrecognizedDetection>()
            for (i in 0 until array.length()) {
                val item = array.getJSONObject(i)
                list.add(
                    UnrecognizedDetection(
                        id = item.getInt("id"),
                        timestamp = item.optDouble("timestamp", 0.0),
                        cameraId = item.optStringOrNull("camera_id"),
                        thumbnailUrl = item.optStringOrNull("thumbnail_url"),
                        confidence = item.optDouble("confidence", 0.0).toFloat()
                    )
                )
            }
            Result.success(list)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun assignDetection(detectionId: Int, personId: Int?, newPersonName: String?): Result<Boolean> = withContext(Dispatchers.IO) {
        try {
            val json = JSONObject().apply {
                if (personId != null) put("person_id", personId)
                if (!newPersonName.isNullOrBlank()) put("new_person_name", newPersonName)
            }
            val request = buildRequest("/api/v1/detections/$detectionId/assign", "POST", json.toString().toRequestBody(jsonMediaType))
            val response = httpClient.newCall(request).execute()
            Result.success(response.isSuccessful)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun dismissDetection(detectionId: Int): Result<Boolean> = withContext(Dispatchers.IO) {
        try {
            val request = buildRequest("/api/v1/detections/$detectionId/dismiss", "DELETE")
            val response = httpClient.newCall(request).execute()
            Result.success(response.isSuccessful)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun recognize(imageBytes: ByteArray, minConfidence: Float = 0.5f, similarityThreshold: Float = 0.45f): Result<RecognizeResult> {
        val base64 = "data:image/jpeg;base64," + Base64.encodeToString(imageBytes, Base64.NO_WRAP)
        return recognize(base64, minConfidence, similarityThreshold)
    }

    suspend fun recognize(base64Image: String, minConfidence: Float = 0.5f, similarityThreshold: Float = 0.45f): Result<RecognizeResult> = withContext(Dispatchers.IO) {
        try {
            val json = JSONObject().apply {
                put("image", base64Image)
                put("min_confidence", minConfidence.toDouble())
                put("similarity_threshold", similarityThreshold.toDouble())
            }
            val request = buildRequest("/api/v1/recognize", "POST", json.toString().toRequestBody(jsonMediaType))
            val response = httpClient.newCall(request).execute()
            if (!response.isSuccessful) {
                return@withContext Result.failure(Exception("Recognition failed: ${response.code}"))
            }

            val body = response.body?.string() ?: return@withContext Result.failure(Exception("Empty recognize response"))
            val resObj = JSONObject(body)
            val faceArray = resObj.optJSONArray("faces") ?: JSONArray()
            val faces = mutableListOf<DetectedFace>()

            for (i in 0 until faceArray.length()) {
                val f = faceArray.getJSONObject(i)
                val bboxArr = f.optJSONArray("bbox") ?: JSONArray()
                val bboxList = mutableListOf<Int>()
                for (b in 0 until bboxArr.length()) {
                    bboxList.add(bboxArr.getInt(b))
                }

                faces.add(
                    DetectedFace(
                        bbox = bboxList,
                        confidence = f.optDouble("confidence", 0.0).toFloat(),
                        matchedName = f.optStringOrNull("matched_name"),
                        similarity = if (f.has("similarity")) f.getDouble("similarity").toFloat() else null,
                        isHousehold = if (f.has("is_household")) f.getBoolean("is_household") else null,
                        isVisitor = if (f.has("is_visitor")) f.getBoolean("is_visitor") else null
                    )
                )
            }

            Result.success(
                RecognizeResult(
                    success = resObj.optBoolean("success", true),
                    facesDetected = resObj.optInt("faces_detected", faces.size),
                    faces = faces
                )
            )
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    fun getAuthToken(): String? = configManager.getAuthToken()

    suspend fun getRtspStatus(): Result<RtspStatus> = withContext(Dispatchers.IO) {
        try {
            val request = buildRequest("/api/v1/rtsp/status")
            val response = httpClient.newCall(request).execute()
            if (!response.isSuccessful) {
                return@withContext Result.failure(Exception("Failed to get RTSP status: ${response.code}"))
            }

            val body = response.body?.string() ?: return@withContext Result.failure(Exception("Empty response"))
            val json = JSONObject(body)

            val isRunning = json.optBoolean("is_running", json.optBoolean("running", false))
            val isConnected = json.optBoolean("is_connected", false)
            val fpsVal = when {
                json.has("actual_fps") -> json.optDouble("actual_fps", 0.0)
                json.has("fps_actual") -> json.optDouble("fps_actual", 0.0)
                json.has("target_fps") -> json.optDouble("target_fps", 3.0)
                else -> json.optDouble("fps", 3.0)
            }.toFloat()

            val motionGated = json.optBoolean("motion_gating_enabled", json.optBoolean("motion_gated", true))
            val motionDetected = json.optBoolean("motion_detected", false)

            val status = RtspStatus(
                running = isRunning,
                isConnected = isConnected,
                url = json.optStringOrNull("url"),
                cameraName = json.optStringOrNull("camera_name"),
                fps = fpsVal,
                framesProcessed = json.optLong("frames_processed", 0L),
                motionGated = motionGated,
                motionDetected = motionDetected,
                idleMode = json.optBoolean("idle_mode", false),
                cooldownSeconds = json.optInt("cooldown_seconds", 30)
            )
            Result.success(status)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun startRtsp(): Result<Boolean> = withContext(Dispatchers.IO) {
        try {
            val request = buildRequest("/api/v1/rtsp/start", "POST")
            val response = httpClient.newCall(request).execute()
            Result.success(response.isSuccessful)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun stopRtsp(): Result<Boolean> = withContext(Dispatchers.IO) {
        try {
            val request = buildRequest("/api/v1/rtsp/stop", "POST")
            val response = httpClient.newCall(request).execute()
            Result.success(response.isSuccessful)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getEvents(category: String? = null, level: String? = null, limit: Int = 50): Result<List<EventLog>> = withContext(Dispatchers.IO) {
        try {
            val path = buildString {
                append("/api/v1/events/logs?limit=").append(limit)
                if (!category.isNullOrBlank() && category.lowercase() != "all") {
                    append("&category=").append(category.lowercase())
                }
                if (!level.isNullOrBlank() && level.lowercase() != "all") {
                    append("&level=").append(level.lowercase())
                }
            }
            val request = buildRequest(path)
            val response = httpClient.newCall(request).execute()
            if (!response.isSuccessful) {
                return@withContext Result.failure(Exception("Failed to get events: ${response.code}"))
            }

            val body = response.body?.string() ?: return@withContext Result.failure(Exception("Empty events response"))
            val json = JSONObject(body)
            val logsArr = json.optJSONArray("logs") ?: json.optJSONArray("events") ?: JSONArray()
            val list = mutableListOf<EventLog>()

            for (i in 0 until logsArr.length()) {
                val item = logsArr.getJSONObject(i)
                val detailsRaw = item.opt("details")
                val detailsStr = when (detailsRaw) {
                    is JSONObject -> detailsRaw.toString(2)
                    is String -> detailsRaw
                    null -> ""
                    else -> detailsRaw.toString()
                }

                list.add(
                    EventLog(
                        id = item.optLong("id", i.toLong()),
                        timestamp = item.optString("timestamp", ""),
                        category = item.optString("category", "system"),
                        level = item.optString("level", item.optString("severity", "info")),
                        eventType = item.optString("event_type", ""),
                        message = item.optString("message", ""),
                        details = detailsStr
                    )
                )
            }
            Result.success(list)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getSettings(): Result<AppSettings> = withContext(Dispatchers.IO) {
        try {
            val request = buildRequest("/api/v1/settings")
            val response = httpClient.newCall(request).execute()
            if (!response.isSuccessful) {
                return@withContext Result.failure(Exception("Failed to load settings: ${response.code}"))
            }

            val body = response.body?.string() ?: return@withContext Result.failure(Exception("Empty settings response"))
            val json = JSONObject(body)
            val settings = AppSettings(
                faceDetectorType = json.optString("face_detector_type", "yolov8_face"),
                detSize = json.optInt("det_size", 320),
                ortNumThreads = json.optInt("ort_num_threads", 8),
                detectionConfidence = json.optDouble("detection_confidence", 0.70).toFloat(),
                similarityThreshold = json.optDouble("similarity_threshold", 0.60).toFloat(),
                notificationThreshold = json.optDouble("notification_threshold", 0.65).toFloat(),
                notifyOnUnknown = json.optBoolean("notify_on_unknown", true),
                unknownMinConfidence = json.optDouble("unknown_min_confidence", 0.50).toFloat(),
                rtspUrl = json.optString("rtsp_url", ""),
                rtspEnabled = json.optBoolean("rtsp_enabled", false),
                rtspCameraName = json.optString("rtsp_camera_name", "Default Camera"),
                rtspFps = json.optDouble("rtsp_fps", 3.0).toFloat(),
                rtspCooldownSeconds = json.optInt("cooldown_seconds", 30),
                rtspMotionGatingEnabled = json.optBoolean("rtsp_motion_gating_enabled", true),
                rtspMotionThreshold = json.optDouble("rtsp_motion_threshold", 0.05).toFloat(),
                rtspWebhookUrl = json.optString("rtsp_webhook_url", ""),
                webhookOnlyKnownFaces = json.optBoolean("webhook_only_known_faces", false),
                mqttEnabled = json.optBoolean("mqtt_enabled", false),
                mqttHost = json.optString("mqtt_host", "localhost"),
                mqttPort = json.optInt("mqtt_port", 1883),
                mqttTopic = json.optString("mqtt_topic", "facedetection/events"),
                mqttOnlyKnownFaces = json.optBoolean("mqtt_only_known_faces", false)
            )
            Result.success(settings)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun updateSettings(settings: AppSettings): Result<AppSettings> = withContext(Dispatchers.IO) {
        try {
            val json = JSONObject().apply {
                put("face_detector_type", settings.faceDetectorType)
                put("det_size", settings.detSize)
                put("ort_num_threads", settings.ortNumThreads)
                put("detection_confidence", settings.detectionConfidence.toDouble())
                put("similarity_threshold", settings.similarityThreshold.toDouble())
                put("notification_threshold", settings.notificationThreshold.toDouble())
                put("notify_on_unknown", settings.notifyOnUnknown)
                put("unknown_min_confidence", settings.unknownMinConfidence.toDouble())
                put("rtsp_url", settings.rtspUrl)
                put("rtsp_enabled", settings.rtspEnabled)
                put("rtsp_camera_name", settings.rtspCameraName)
                put("rtsp_fps", settings.rtspFps.toDouble())
                put("rtsp_cooldown_seconds", settings.rtspCooldownSeconds)
                put("rtsp_motion_gating_enabled", settings.rtspMotionGatingEnabled)
                put("rtsp_motion_threshold", settings.rtspMotionThreshold.toDouble())
                put("rtsp_webhook_url", settings.rtspWebhookUrl)
                put("webhook_only_known_faces", settings.webhookOnlyKnownFaces)
                put("mqtt_enabled", settings.mqttEnabled)
                put("mqtt_host", settings.mqttHost)
                put("mqtt_port", settings.mqttPort)
                put("mqtt_topic", settings.mqttTopic)
                put("mqtt_only_known_faces", settings.mqttOnlyKnownFaces)
            }
            val request = buildRequest("/api/v1/settings", "PUT", json.toString().toRequestBody(jsonMediaType))
            val response = httpClient.newCall(request).execute()
            if (!response.isSuccessful) {
                return@withContext Result.failure(Exception("Failed to update settings: ${response.code}"))
            }

            Result.success(settings)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    private fun JSONObject.optStringOrNull(name: String): String? {
        return if (has(name) && !isNull(name)) getString(name) else null
    }
}

