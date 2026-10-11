package com.facedetection.app.ui

import android.content.Intent
import android.os.Bundle
import android.view.View
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.facedetection.app.R
import com.facedetection.app.data.ServerConfigManager
import com.facedetection.app.databinding.ActivityServerSetupBinding
import kotlinx.coroutines.launch

/**
 * Rules for ServerSetupActivity:
 * 1. Variables must be declared at the top of the class.
 * 2. Asynchronous operations such as server ping checks must use Coroutines via lifecycleScope.
 * 3. Class documentation comments must be maintained for all changes.
 * 4. Provides UI to input, validate, test, and persist server connection parameters.
 */
class ServerSetupActivity : AppCompatActivity() {

    private lateinit var binding: ActivityServerSetupBinding
    private lateinit var configManager: ServerConfigManager
    private var isTestingConnection: Boolean = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityServerSetupBinding.inflate(layoutInflater)
        setContentView(binding.root)

        configManager = ServerConfigManager(this)

        populateExistingConfig()
        setupListeners()
    }

    private fun populateExistingConfig() {
        val existingHost = configManager.getHost()
        if (!existingHost.isNullOrBlank()) {
            binding.etHost.setText(existingHost)
            binding.etPort.setText(configManager.getPort().toString())
            if (configManager.getProtocol() == "https") {
                binding.rbHttps.isChecked = true
            } else {
                binding.rbHttp.isChecked = true
            }
        }
    }

    private fun setupListeners() {
        binding.btnTest.setOnClickListener {
            validateAndTestConnection()
        }

        binding.btnSaveAndConnect.setOnClickListener {
            validateAndSave()
        }
    }

    private fun buildCandidateUrl(): String? {
        val host = binding.etHost.text?.toString()?.trim() ?: ""
        if (host.isEmpty()) {
            binding.tilHost.error = getString(R.string.error_empty_host)
            return null
        }
        binding.tilHost.error = null

        val portStr = binding.etPort.text?.toString()?.trim() ?: "8000"
        val port = portStr.toIntOrNull()
        if (port == null || port !in 1..65535) {
            binding.tilPort.error = getString(R.string.error_invalid_port)
            return null
        }
        binding.tilPort.error = null

        val protocol = if (binding.rbHttps.isChecked) "https" else "http"
        val cleanHost = host.replace(Regex("^https?://"), "").replace(Regex("/+$"), "")

        return if ((port == 80 && protocol == "http") || (port == 443 && protocol == "https")) {
            "$protocol://$cleanHost"
        } else {
            "$protocol://$cleanHost:$port"
        }
    }

    private fun validateAndTestConnection() {
        if (isTestingConnection) return
        val candidateUrl = buildCandidateUrl() ?: return

        isTestingConnection = true
        binding.btnTest.isEnabled = false
        binding.tvStatus.visibility = View.VISIBLE
        binding.tvStatus.text = getString(R.string.status_testing)
        binding.tvStatus.setTextColor(ContextCompat.getColor(this, R.color.text_secondary))

        lifecycleScope.launch {
            val result = configManager.testConnection(candidateUrl)
            isTestingConnection = false
            binding.btnTest.isEnabled = true

            result.onSuccess { info ->
                binding.tvStatus.text = getString(
                    R.string.status_connected_success,
                    info.app,
                    info.version,
                    info.model
                )
                binding.tvStatus.setTextColor(ContextCompat.getColor(this@ServerSetupActivity, R.color.brand_emerald))
            }.onFailure { err ->
                binding.tvStatus.text = getString(
                    R.string.status_connection_failed,
                    err.localizedMessage ?: "Unknown error"
                )
                binding.tvStatus.setTextColor(ContextCompat.getColor(this@ServerSetupActivity, R.color.brand_rose))
            }
        }
    }

    private fun validateAndSave() {
        val host = binding.etHost.text?.toString()?.trim() ?: ""
        if (host.isEmpty()) {
            binding.tilHost.error = getString(R.string.error_empty_host)
            return
        }

        val portStr = binding.etPort.text?.toString()?.trim() ?: "8000"
        val port = portStr.toIntOrNull()
        if (port == null || port !in 1..65535) {
            binding.tilPort.error = getString(R.string.error_invalid_port)
            return
        }

        val protocol = if (binding.rbHttps.isChecked) "https" else "http"
        configManager.saveServerConfig(protocol, host, port)

        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
        }
        startActivity(intent)
        finish()
    }
}
