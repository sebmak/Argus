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
import androidx.compose.material.icons.filled.Bedtime
import androidx.compose.material.icons.filled.People
import androidx.compose.material.icons.filled.RateReview
import androidx.compose.material.icons.filled.Videocam
import androidx.compose.material.icons.filled.WbSunny
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import com.facedetection.app.data.FaceEngineApiClient
import com.facedetection.app.data.models.RecentActivity
import com.facedetection.app.data.models.RtspStatus
import com.facedetection.app.data.models.SystemStats
import com.facedetection.app.ui.components.FaceEngineTopBar
import com.facedetection.app.ui.components.GlassCard
import com.facedetection.app.ui.components.MetricCard
import com.facedetection.app.ui.navigation.Screen
import com.facedetection.app.ui.theme.BgRoot
import com.facedetection.app.ui.theme.BgSurfaceCard
import com.facedetection.app.ui.theme.BrandAmber
import com.facedetection.app.ui.theme.BrandCyan
import com.facedetection.app.ui.theme.BrandEmerald
import com.facedetection.app.ui.theme.BrandPrimary
import com.facedetection.app.ui.theme.BrandPurple
import com.facedetection.app.ui.theme.BrandRose
import com.facedetection.app.ui.theme.TextMuted
import com.facedetection.app.ui.theme.TextPrimary
import com.facedetection.app.ui.theme.TextSecondary
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Rules for DashboardScreen:
 * 1. State variables and reactive properties must be declared at the top of the composable.
 * 2. Asynchronous operations and API polling must prefer Coroutines.
 * 3. Class documentation comments must be maintained for all changes.
 * 4. Provides real-time telemetry, camera status, and quick navigation to all application modules.
 */
@Composable
fun DashboardScreen(
    apiClient: FaceEngineApiClient,
    onNavigate: (Screen) -> Unit,
    onSwitchServer: () -> Unit
) {
    val coroutineScope = rememberCoroutineScope()
    var stats by remember { mutableStateOf<SystemStats?>(null) }
    var rtspStatus by remember { mutableStateOf<RtspStatus?>(null) }
    var isLoading by remember { mutableStateOf(true) }
    var errorMessage by remember { mutableStateOf<String?>(null) }

    fun refreshStats() {
        coroutineScope.launch {
            isLoading = true
            errorMessage = null
            apiClient.getStats().onSuccess {
                stats = it
            }.onFailure {
                errorMessage = it.message ?: "Failed to load dashboard metrics"
            }

            apiClient.getRtspStatus().onSuccess {
                rtspStatus = it
            }
            isLoading = false
        }
    }

    LaunchedEffect(Unit) {
        refreshStats()
    }

    val configuration = LocalConfiguration.current
    val isExpanded = configuration.screenWidthDp >= 600

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(BgRoot)
    ) {
        FaceEngineTopBar(
            title = "FaceEngine Dashboard",
            serverHost = apiClient.getBaseUrl().removePrefix("http://").removePrefix("https://"),
            isConnected = stats != null,
            onRefresh = { refreshStats() },
            onServerClick = onSwitchServer,
            onSettingsClick = { onNavigate(Screen.Settings) }
        )

        if (isLoading && stats == null) {
            Box(
                modifier = Modifier.fillMaxSize(),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator(color = BrandPrimary)
            }
        } else {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .verticalScroll(rememberScrollState())
                    .padding(horizontal = 20.dp, vertical = 12.dp)
            ) {
                val currentStats = stats
                val currentRtsp = rtspStatus

                // Telemetry Metrics Row 1
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    MetricCard(
                        modifier = Modifier.weight(1f),
                        title = "Household",
                        value = "${currentStats?.householdCount ?: 0}",
                        icon = Icons.Default.People,
                        accentColor = BrandPrimary,
                        subtitle = "Registered members"
                    )

                    MetricCard(
                        modifier = Modifier.weight(1f),
                        title = "Review Queue",
                        value = "${currentStats?.unrecognizedCount ?: 0}",
                        icon = Icons.Default.RateReview,
                        accentColor = if ((currentStats?.unrecognizedCount ?: 0) > 0) BrandAmber else BrandEmerald,
                        subtitle = "Pending approvals"
                    )
                }

                Spacer(modifier = Modifier.height(12.dp))

                // Telemetry Metrics Row 2
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    MetricCard(
                        modifier = Modifier.weight(1f),
                        title = "RTSP Camera",
                        value = if (currentRtsp?.running == true) "Active" else "Stopped",
                        icon = Icons.Default.Videocam,
                        accentColor = if (currentRtsp?.running == true) BrandEmerald else BrandRose,
                        subtitle = "${currentRtsp?.fps ?: 0f} FPS"
                    )

                    MetricCard(
                        modifier = Modifier.weight(1f),
                        title = "Detection Mode",
                        value = if (currentRtsp?.idleMode == true) "Idle Mode" else "Surveillance",
                        icon = if (currentRtsp?.idleMode == true) Icons.Default.Bedtime else Icons.Default.WbSunny,
                        accentColor = if (currentRtsp?.idleMode == true) BrandPurple else BrandCyan,
                        subtitle = "${currentStats?.faceDetectorType ?: "YOLOv8"}"
                    )
                }

                Spacer(modifier = Modifier.height(20.dp))

                // Quick Navigation Actions
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Button(
                        onClick = { onNavigate(Screen.Review) },
                        modifier = Modifier.weight(1f),
                        shape = RoundedCornerShape(12.dp),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = BrandPrimary,
                            contentColor = TextPrimary
                        )
                    ) {
                        Text("Open Review (${currentStats?.unrecognizedCount ?: 0})", fontSize = 12.sp)
                    }

                    OutlinedButton(
                        onClick = { onNavigate(Screen.Rtsp) },
                        modifier = Modifier.weight(1f),
                        shape = RoundedCornerShape(12.dp)
                    ) {
                        Text("Live Camera", color = BrandCyan, fontSize = 12.sp)
                    }
                }

                Spacer(modifier = Modifier.height(10.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    OutlinedButton(
                        onClick = { onNavigate(Screen.Sandbox) },
                        modifier = Modifier.weight(1f),
                        shape = RoundedCornerShape(12.dp)
                    ) {
                        Text("Test Sandbox", color = BrandPurple, fontSize = 12.sp)
                    }

                    OutlinedButton(
                        onClick = { onNavigate(Screen.Settings) },
                        modifier = Modifier.weight(1f),
                        shape = RoundedCornerShape(12.dp)
                    ) {
                        Text("Settings", color = TextSecondary, fontSize = 12.sp)
                    }
                }

                Spacer(modifier = Modifier.height(24.dp))

                // Recent Detections Stream
                Text(
                    text = "Recent Detection Stream",
                    color = TextPrimary,
                    fontSize = 17.sp,
                    fontWeight = FontWeight.Bold
                )

                Spacer(modifier = Modifier.height(12.dp))

                val activities = currentStats?.recentActivity ?: emptyList()
                if (activities.isEmpty()) {
                    GlassCard(modifier = Modifier.fillMaxWidth()) {
                        Text(
                            text = "No recent detections recorded yet.",
                            color = TextMuted,
                            fontSize = 13.sp
                        )
                    }
                } else {
                    activities.forEach { activity ->
                        RecentActivityRow(
                            item = activity,
                            baseUrl = apiClient.getBaseUrl()
                        )
                        Spacer(modifier = Modifier.height(10.dp))
                    }
                }

                Spacer(modifier = Modifier.height(24.dp))
            }
        }
    }
}

@Composable
private fun RecentActivityRow(
    item: RecentActivity,
    baseUrl: String
) {
    val formattedTime = remember(item.timestamp) {
        if (item.timestamp > 0) {
            val date = Date((item.timestamp * 1000).toLong())
            SimpleDateFormat("h:mm:ss a", Locale.getDefault()).format(date)
        } else {
            "Recent"
        }
    }

    GlassCard(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(52.dp)
                    .clip(RoundedCornerShape(10.dp))
                    .background(BgSurfaceCard),
                contentAlignment = Alignment.Center
            ) {
                val imageUrl = item.thumbnailUrl ?: if (!item.thumbnailPath.isNullOrBlank()) {
                    "$baseUrl/api/v1/thumbnails/${item.thumbnailPath}"
                } else null

                if (!imageUrl.isNullOrBlank()) {
                    val fullUrl = if (imageUrl.startsWith("http")) imageUrl else "$baseUrl$imageUrl"
                    AsyncImage(
                        model = fullUrl,
                        contentDescription = item.matchedName ?: "Detection crop",
                        modifier = Modifier.fillMaxSize(),
                        contentScale = ContentScale.Crop
                    )
                } else {
                    Icon(
                        imageVector = Icons.Default.People,
                        contentDescription = null,
                        tint = TextMuted,
                        modifier = Modifier.size(24.dp)
                    )
                }
            }

            Spacer(modifier = Modifier.width(14.dp))

            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = item.matchedName ?: "Unknown Face",
                    color = TextPrimary,
                    fontSize = 15.sp,
                    fontWeight = FontWeight.SemiBold
                )
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = "${item.cameraId ?: "Camera"} • $formattedTime",
                    color = TextMuted,
                    fontSize = 11.sp
                )
            }

            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(8.dp))
                    .background(
                        if (item.isRecognized) BrandEmerald.copy(alpha = 0.15f)
                        else BrandAmber.copy(alpha = 0.15f)
                    )
                    .padding(horizontal = 8.dp, vertical = 4.dp)
            ) {
                Text(
                    text = if (item.isRecognized) "${String.format("%.0f", (item.similarity ?: 0f) * 100)}%" else "Unknown",
                    color = if (item.isRecognized) BrandEmerald else BrandAmber,
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Bold
                )
            }
        }
    }
}
