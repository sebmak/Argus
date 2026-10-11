package com.facedetection.app.data.models

/**
 * Rules for User:
 * - Represents authenticated user session identity.
 * - Variables must be declared at the top of the data class.
 * - Flags isDefaultPassword to warn when administrative credentials are unhardened.
 */
data class User(
    val id: String,
    val username: String,
    val isDefaultPassword: Boolean = false
)

/**
 * Rules for LoginResponse:
 * - Encapsulates JWT authentication token payload returned by /api/v1/auth/login.
 * - Variables must be declared at the top of the data class.
 * - Propagates isDefaultPassword from authentication endpoint.
 */
data class LoginResponse(
    val accessToken: String,
    val tokenType: String,
    val expiresIn: Long,
    val username: String,
    val isDefaultPassword: Boolean = false
)

/**
 * Rules for ServerHealth:
 * - Encapsulates public health probe and engine readiness telemetry.
 * - Variables must be declared at the top of the data class.
 */
data class ServerHealth(
    val status: String,
    val app: String,
    val version: String,
    val model: String,
    val engineReady: Boolean
)

/**
 * Rules for RecentActivity:
 * - Represents an individual facial detection event in the telemetry feed.
 * - Variables must be declared at the top of the data class.
 */
data class RecentActivity(
    val id: String,
    val timestamp: Double,
    val matchedName: String?,
    val similarity: Float?,
    val isHousehold: Boolean?,
    val status: String,
    val thumbnailPath: String?,
    val thumbnailUrl: String?,
    val cameraId: String?
) {
    val isRecognized: Boolean
        get() = !matchedName.isNullOrBlank() && (similarity ?: 0f) > 0.40f
}

/**
 * Rules for SystemStats:
 * - Encapsulates overview metrics and system diagnostics from /api/v1/stats.
 * - Variables must be declared at the top of the data class.
 */
data class SystemStats(
    val totalPersons: Int,
    val householdCount: Int,
    val visitorCount: Int,
    val totalSamples: Int,
    val unrecognizedCount: Int,
    val accuracyRate: Float,
    val faceDetectorType: String,
    val detSize: Int,
    val ortNumThreads: Int,
    val recentActivity: List<RecentActivity>
)

/**
 * Rules for Person:
 * - Represents a registered household member or visitor.
 * - Variables must be declared at the top of the data class.
 */
data class Person(
    val id: Int,
    val name: String,
    val isHousehold: Boolean,
    val sampleCount: Int,
    val thumbnailUrl: String?,
    val createdAt: String? = null
)

/**
 * Rules for FaceSample:
 * - Represents an enrolled reference facial crop with embedding.
 * - Variables must be declared at the top of the data class.
 */
data class FaceSample(
    val id: Int,
    val thumbnailUrl: String?,
    val createdAt: String?,
    val cameraName: String?
)

/**
 * Rules for PersonDetail:
 * - Detailed person record with all enrolled reference face samples.
 * - Variables must be declared at the top of the data class.
 */
data class PersonDetail(
    val id: Int,
    val name: String,
    val isHousehold: Boolean,
    val sampleCount: Int,
    val samples: List<FaceSample>
)

/**
 * Rules for UnrecognizedDetection:
 * - Represents an unknown arrival face crop pending review and assignment.
 * - Variables must be declared at the top of the data class.
 */
data class UnrecognizedDetection(
    val id: Int,
    val timestamp: Double,
    val cameraId: String?,
    val thumbnailUrl: String?,
    val confidence: Float
)

/**
 * Rules for DetectedFace:
 * - Represents an individual detected face box and match in an inference frame.
 * - Variables must be declared at the top of the data class.
 */
data class DetectedFace(
    val bbox: List<Int>, // [x1, y1, x2, y2]
    val confidence: Float,
    val matchedName: String?,
    val similarity: Float?,
    val isHousehold: Boolean?,
    val isVisitor: Boolean?
) {
    val isRecognized: Boolean
        get() = !matchedName.isNullOrBlank() && (similarity ?: 0f) > 0.40f
}

/**
 * Rules for RecognizeResult:
 * - Result payload from interactive test sandbox face recognition.
 * - Variables must be declared at the top of the data class.
 */
data class RecognizeResult(
    val success: Boolean,
    val facesDetected: Int,
    val faces: List<DetectedFace>
)

/**
 * Rules for RtspStatus:
 * - Status and throughput telemetry of the continuous RTSP surveillance worker.
 * - Variables must be declared at the top of the data class.
 * - Supports is_running and is_connected state flags from FastAPI backend.
 */
data class RtspStatus(
    val running: Boolean,
    val isConnected: Boolean = false,
    val url: String?,
    val cameraName: String?,
    val fps: Float,
    val framesProcessed: Long = 0L,
    val motionGated: Boolean = true,
    val motionDetected: Boolean = false,
    val idleMode: Boolean = false,
    val cooldownSeconds: Int = 30
) {
    val isRunning: Boolean
        get() = running
}

/**
 * Rules for EventLog:
 * - Operational event log item from /api/v1/events/logs.
 * - Variables must be declared at the top of the data class.
 * - Preserves category, level, and parsed payload metadata.
 */
data class EventLog(
    val id: Long,
    val timestamp: String,
    val category: String,
    val level: String,
    val eventType: String = "",
    val message: String,
    val details: String = ""
) {
    val severity: String
        get() = level
}

/**
 * Rules for AppSettings:
 * - Global engine hyperparameter configuration and integration flags.
 * - Variables must be declared at the top of the data class.
 */
data class AppSettings(
    val faceDetectorType: String = "yolov8_face",
    val detSize: Int = 320,
    val ortNumThreads: Int = 8,
    val detectionConfidence: Float = 0.70f,
    val similarityThreshold: Float = 0.60f,
    val notificationThreshold: Float = 0.65f,
    val notifyOnUnknown: Boolean = true,
    val unknownMinConfidence: Float = 0.50f,
    val rtspUrl: String = "",
    val rtspEnabled: Boolean = false,
    val rtspCameraName: String = "Default Camera",
    val rtspFps: Float = 3.0f,
    val rtspCooldownSeconds: Int = 30,
    val rtspMotionGatingEnabled: Boolean = true,
    val rtspMotionThreshold: Float = 0.05f,
    val rtspWebhookUrl: String = "",
    val webhookOnlyKnownFaces: Boolean = false,
    val mqttEnabled: Boolean = false,
    val mqttHost: String = "localhost",
    val mqttPort: Int = 1883,
    val mqttTopic: String = "facedetection/events",
    val mqttOnlyKnownFaces: Boolean = false
)
