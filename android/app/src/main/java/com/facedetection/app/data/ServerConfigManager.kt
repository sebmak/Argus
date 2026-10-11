package com.facedetection.app.data

import android.content.Context
import android.content.SharedPreferences
import com.facedetection.app.data.models.ServerHealth
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * Rules for ServerConfigManager:
 * 1. Variables must be declared at the top of the class.
 * 2. Network operations must prefer Coroutines with Dispatchers.IO.
 * 3. Comments above the class must be maintained and updated upon modification.
 * 4. Provides local persistence for server IP/domain, port, protocol, and session token via SharedPreferences.
 */
class ServerConfigManager(context: Context) {

    private val prefs: SharedPreferences = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    private val httpClient: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(5, TimeUnit.SECONDS)
        .build()

    fun hasConfiguredServer(): Boolean {
        val host = getHost()
        return !host.isNullOrBlank()
    }

    fun isConfigured(): Boolean = hasConfiguredServer()

    fun getProtocol(): String = prefs.getString(KEY_PROTOCOL, "http") ?: "http"

    fun isUsingHttps(): Boolean = getProtocol().lowercase() == "https"

    fun getHost(): String? = prefs.getString(KEY_HOST, null)

    fun getServerHost(): String = getHost() ?: ""

    fun getPort(): Int = prefs.getInt(KEY_PORT, 8000)

    fun getServerPort(): Int = getPort()

    fun getAuthToken(): String? = prefs.getString(KEY_AUTH_TOKEN, null)

    fun isLoggedIn(): Boolean = !getAuthToken().isNullOrBlank()

    fun saveAuthToken(token: String) {
        prefs.edit().putString(KEY_AUTH_TOKEN, token).apply()
    }

    fun clearAuthToken() {
        prefs.edit().remove(KEY_AUTH_TOKEN).apply()
    }

    fun getBaseUrl(): String? {
        val host = getHost() ?: return null
        val protocol = getProtocol()
        val port = getPort()

        val cleanHost = host.trim().replace(Regex("^https?://"), "").replace(Regex("/+$"), "")
        return if ((port == 80 && protocol == "http") || (port == 443 && protocol == "https")) {
            "$protocol://$cleanHost"
        } else {
            "$protocol://$cleanHost:$port"
        }
    }

    fun getFullServerUrl(): String = getBaseUrl() ?: "http://127.0.0.1:8000"

    fun saveServerConfig(protocol: String, host: String, port: Int) {
        val cleanHost = host.trim()
            .replace(Regex("^https?://"), "")
            .replace(Regex("/+$"), "")

        prefs.edit()
            .putString(KEY_PROTOCOL, protocol.lowercase())
            .putString(KEY_HOST, cleanHost)
            .putInt(KEY_PORT, port)
            .apply()
    }

    fun saveServerConfig(host: String, port: Int, useHttps: Boolean) {
        saveServerConfig(if (useHttps) "https" else "http", host, port)
    }

    fun clearServerConfig() {
        prefs.edit().clear().apply()
    }

    /**
     * Coroutine to test server connectivity and fetch /health telemetry.
     */
    suspend fun testConnection(baseUrl: String): Result<ServerHealth> = withContext(Dispatchers.IO) {
        try {
            val healthUrl = baseUrl.trimEnd('/') + "/health"
            val request = Request.Builder()
                .url(healthUrl)
                .get()
                .build()

            val response = httpClient.newCall(request).execute()
            if (!response.isSuccessful) {
                return@withContext Result.failure(Exception("HTTP error ${response.code}: ${response.message}"))
            }

            val body = response.body?.string() ?: return@withContext Result.failure(Exception("Empty response body"))
            val json = JSONObject(body)

            val healthInfo = ServerHealth(
                status = json.optString("status", "unknown"),
                app = json.optString("app", "FaceEngine"),
                version = json.optString("version", "1.0.0"),
                model = json.optString("model", "InsightFace"),
                engineReady = json.optBoolean("engine_ready", true)
            )

            Result.success(healthInfo)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    companion object {
        private const val PREFS_NAME = "face_engine_server_prefs"
        private const val KEY_PROTOCOL = "server_protocol"
        private const val KEY_HOST = "server_host"
        private const val KEY_PORT = "server_port"
        private const val KEY_AUTH_TOKEN = "server_auth_token"
    }
}
