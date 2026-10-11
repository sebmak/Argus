package com.facedetection.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Dns
import androidx.compose.material.icons.filled.Error
import androidx.compose.material.icons.filled.Lan
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.RadioButton
import androidx.compose.material3.RadioButtonDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.facedetection.app.data.FaceEngineApiClient
import com.facedetection.app.data.ServerConfigManager
import com.facedetection.app.ui.components.GlassCard
import com.facedetection.app.ui.theme.BgInput
import com.facedetection.app.ui.theme.BgRoot
import com.facedetection.app.ui.theme.BorderAccent
import com.facedetection.app.ui.theme.BorderSubtle
import com.facedetection.app.ui.theme.BrandCyan
import com.facedetection.app.ui.theme.BrandEmerald
import com.facedetection.app.ui.theme.BrandPrimary
import com.facedetection.app.ui.theme.BrandPurple
import com.facedetection.app.ui.theme.BrandRose
import com.facedetection.app.ui.theme.TextMuted
import com.facedetection.app.ui.theme.TextPrimary
import com.facedetection.app.ui.theme.TextSecondary
import kotlinx.coroutines.launch

/**
 * Screen for configuring the FaceEngine backend server address (IP or hostname).
 */
@Composable
fun ServerSetupScreen(
    configManager: ServerConfigManager,
    apiClient: FaceEngineApiClient,
    onConfigured: () -> Unit,
    onCancel: (() -> Unit)? = null
) {
    val coroutineScope = rememberCoroutineScope()
    var host by remember { mutableStateOf(configManager.getServerHost()) }
    var port by remember { mutableStateOf(configManager.getServerPort().toString()) }
    var useHttps by remember { mutableStateOf(configManager.isUsingHttps()) }

    var isTesting by remember { mutableStateOf(false) }
    var testResult by remember { mutableStateOf<String?>(null) }
    var testSuccess by remember { mutableStateOf(false) }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(BgRoot)
            .padding(24.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .verticalScroll(rememberScrollState()),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // App Branding Icon
            Box(
                modifier = Modifier
                    .size(64.dp)
                    .clip(RoundedCornerShape(18.dp))
                    .background(
                        Brush.linearGradient(
                            listOf(BrandPrimary, BrandPurple)
                        )
                    ),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = Icons.Default.Dns,
                    contentDescription = "Server Setup",
                    tint = TextPrimary,
                    modifier = Modifier.size(32.dp)
                )
            }

            Spacer(modifier = Modifier.height(16.dp))

            Text(
                text = "Connect to FaceEngine",
                color = TextPrimary,
                fontSize = 24.sp,
                fontWeight = FontWeight.Bold
            )

            Text(
                text = "Specify your home server IP address or domain name",
                color = TextSecondary,
                fontSize = 13.sp,
                modifier = Modifier.padding(top = 4.dp, bottom = 24.dp)
            )

            GlassCard(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.fillMaxWidth()) {
                    Text(
                        text = "Protocol",
                        color = TextSecondary,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Medium
                    )

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            RadioButton(
                                selected = !useHttps,
                                onClick = { useHttps = false },
                                colors = RadioButtonDefaults.colors(selectedColor = BrandPrimary)
                            )
                            Text(text = "HTTP (LAN)", color = TextPrimary, fontSize = 13.sp)
                        }
                        Spacer(modifier = Modifier.width(20.dp))
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            RadioButton(
                                selected = useHttps,
                                onClick = { useHttps = true },
                                colors = RadioButtonDefaults.colors(selectedColor = BrandPrimary)
                            )
                            Text(text = "HTTPS (Domain)", color = TextPrimary, fontSize = 13.sp)
                        }
                    }

                    Spacer(modifier = Modifier.height(16.dp))

                    Text(
                        text = "Server IP / Hostname",
                        color = TextSecondary,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Medium
                    )
                    Spacer(modifier = Modifier.height(6.dp))
                    OutlinedTextField(
                        value = host,
                        onValueChange = { host = it },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true,
                        placeholder = { Text("e.g. 192.168.1.100 or server.local", color = TextMuted) },
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedContainerColor = BgInput,
                            unfocusedContainerColor = BgInput,
                            focusedBorderColor = BrandPrimary,
                            unfocusedBorderColor = BorderSubtle,
                            focusedTextColor = TextPrimary,
                            unfocusedTextColor = TextPrimary
                        ),
                        shape = RoundedCornerShape(12.dp)
                    )

                    Spacer(modifier = Modifier.height(16.dp))

                    Text(
                        text = "Port",
                        color = TextSecondary,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Medium
                    )
                    Spacer(modifier = Modifier.height(6.dp))
                    OutlinedTextField(
                        value = port,
                        onValueChange = { port = it },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true,
                        placeholder = { Text("8000", color = TextMuted) },
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedContainerColor = BgInput,
                            unfocusedContainerColor = BgInput,
                            focusedBorderColor = BrandPrimary,
                            unfocusedBorderColor = BorderSubtle,
                            focusedTextColor = TextPrimary,
                            unfocusedTextColor = TextPrimary
                        ),
                        shape = RoundedCornerShape(12.dp)
                    )

                    if (testResult != null) {
                        Spacer(modifier = Modifier.height(16.dp))
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(10.dp))
                                .background(
                                    if (testSuccess) BrandEmerald.copy(alpha = 0.15f)
                                    else BrandRose.copy(alpha = 0.15f)
                                )
                                .padding(12.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(
                                imageVector = if (testSuccess) Icons.Default.CheckCircle else Icons.Default.Error,
                                contentDescription = null,
                                tint = if (testSuccess) BrandEmerald else BrandRose,
                                modifier = Modifier.size(18.dp)
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                text = testResult ?: "",
                                color = if (testSuccess) BrandEmerald else BrandRose,
                                fontSize = 12.sp
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(24.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        Button(
                            onClick = {
                                coroutineScope.launch {
                                    isTesting = true
                                    testResult = null
                                    val portInt = port.toIntOrNull() ?: 8000
                                    val protocol = if (useHttps) "https" else "http"
                                    val url = "$protocol://$host:$portInt"
                                    val isOk = apiClient.testConnection(url)
                                    isTesting = false
                                    testSuccess = isOk
                                    testResult = if (isOk) "Connected to FaceEngine successfully!" else "Could not reach server. Verify IP & port."
                                }
                            },
                            enabled = !isTesting && host.isNotBlank(),
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(12.dp),
                            colors = ButtonDefaults.buttonColors(
                                containerColor = BgInput,
                                contentColor = BrandCyan
                            )
                        ) {
                            if (isTesting) {
                                CircularProgressIndicator(
                                    modifier = Modifier.size(16.dp),
                                    strokeWidth = 2.dp,
                                    color = BrandCyan
                                )
                            } else {
                                Text("Test Ping")
                            }
                        }

                        Button(
                            onClick = {
                                val portInt = port.toIntOrNull() ?: 8000
                                configManager.saveServerConfig(host.trim(), portInt, useHttps)
                                onConfigured()
                            },
                            enabled = host.isNotBlank(),
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(12.dp),
                            colors = ButtonDefaults.buttonColors(
                                containerColor = BrandPrimary,
                                contentColor = TextPrimary
                            )
                        ) {
                            Text("Connect")
                        }
                    }

                    if (onCancel != null) {
                        Spacer(modifier = Modifier.height(8.dp))
                        TextButton(
                            onClick = onCancel,
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text("Cancel", color = TextMuted)
                        }
                    }
                }
            }
        }
    }
}
