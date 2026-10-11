package com.facedetection.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.VideocamOff
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import com.facedetection.app.data.FaceEngineApiClient
import com.facedetection.app.data.models.RtspStatus
import com.facedetection.app.ui.components.FaceEngineTopBar
import com.facedetection.app.ui.components.GlassCard
import com.facedetection.app.ui.theme.BgInput
import com.facedetection.app.ui.theme.BgRoot
import com.facedetection.app.ui.theme.BrandEmerald
import com.facedetection.app.ui.theme.BrandRose
import com.facedetection.app.ui.theme.TextMuted
import com.facedetection.app.ui.theme.TextPrimary
import com.facedetection.app.ui.theme.TextSecondary
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * Screen for viewing real-time RTSP camera surveillance snapshots and controlling the worker.
 */
@Composable
fun RtspScreen(
    apiClient: FaceEngineApiClient,
    onSwitchServer: () -> Unit
) {
    val coroutineScope = rememberCoroutineScope()
    var rtspStatus by remember { mutableStateOf<RtspStatus?>(null) }
    var isToggling by remember { mutableStateOf(false) }
    var snapshotTimestamp by remember { mutableStateOf(System.currentTimeMillis()) }

    fun refreshStatus() {
        coroutineScope.launch {
            apiClient.getRtspStatus().onSuccess {
                rtspStatus = it
            }
        }
    }

    LaunchedEffect(Unit) {
        refreshStatus()
        // Snapshot refresh poll loop
        while (true) {
            delay(1500)
            snapshotTimestamp = System.currentTimeMillis()
            refreshStatus()
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(BgRoot)
    ) {
        FaceEngineTopBar(
            title = "Live Camera Feed",
            serverHost = apiClient.getBaseUrl().removePrefix("http://").removePrefix("https://"),
            isConnected = rtspStatus != null,
            onRefresh = {
                refreshStatus()
                snapshotTimestamp = System.currentTimeMillis()
            },
            onServerClick = onSwitchServer
        )

        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(20.dp)
        ) {
            // Live Video / Snapshot Viewfinder
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .aspectRatio(16f / 9f)
                    .clip(RoundedCornerShape(16.dp))
                    .background(BgInput),
                contentAlignment = Alignment.Center
            ) {
                if (rtspStatus?.running == true) {
                    AsyncImage(
                        model = "${apiClient.getBaseUrl()}/api/v1/rtsp/preview?t=$snapshotTimestamp",
                        contentDescription = "Live RTSP camera snapshot",
                        modifier = Modifier.fillMaxSize(),
                        contentScale = ContentScale.Crop
                    )

                    // LIVE badge
                    Box(
                        modifier = Modifier
                            .align(Alignment.TopStart)
                            .padding(12.dp)
                            .clip(RoundedCornerShape(6.dp))
                            .background(BrandRose)
                            .padding(horizontal = 8.dp, vertical = 4.dp)
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Box(
                                modifier = Modifier
                                    .size(6.dp)
                                    .clip(CircleShape)
                                    .background(TextPrimary)
                            )
                            Spacer(modifier = Modifier.width(6.dp))
                            Text(
                                text = "LIVE",
                                color = TextPrimary,
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }
                } else {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(
                            imageVector = Icons.Default.VideocamOff,
                            contentDescription = null,
                            tint = TextMuted,
                            modifier = Modifier.size(48.dp)
                        )
                        Spacer(modifier = Modifier.height(10.dp))
                        Text(
                            text = "Camera Stream Inactive",
                            color = TextSecondary,
                            fontSize = 14.sp
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            // Status Details Card
            GlassCard(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.fillMaxWidth()) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Box(
                            modifier = Modifier
                                .size(10.dp)
                                .clip(CircleShape)
                                .background(if (rtspStatus?.running == true) BrandEmerald else BrandRose)
                        )
                        Spacer(modifier = Modifier.width(10.dp))
                        Text(
                            text = if (rtspStatus?.running == true) "Surveillance Worker Running" else "Surveillance Worker Stopped",
                            color = TextPrimary,
                            fontWeight = FontWeight.Bold,
                            fontSize = 15.sp
                        )
                    }

                    Spacer(modifier = Modifier.height(12.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(text = "FPS Throughput", color = TextSecondary, fontSize = 13.sp)
                        Text(text = "${rtspStatus?.fps ?: 0f} fps", color = BrandEmerald, fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
                    }

                    Spacer(modifier = Modifier.height(8.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(text = "Detection State", color = TextSecondary, fontSize = 13.sp)
                        Text(
                            text = if (rtspStatus?.idleMode == true) "Idle (No face motion)" else "Active Surveillance",
                            color = TextPrimary,
                            fontSize = 13.sp
                        )
                    }

                    Spacer(modifier = Modifier.height(8.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(text = "Processed Frames", color = TextSecondary, fontSize = 13.sp)
                        Text(
                            text = "${rtspStatus?.framesProcessed ?: 0L}",
                            color = TextPrimary,
                            fontSize = 13.sp
                        )
                    }

                    Spacer(modifier = Modifier.height(20.dp))

                    Button(
                        onClick = {
                            coroutineScope.launch {
                                isToggling = true
                                if (rtspStatus?.running == true) {
                                    apiClient.stopRtsp()
                                } else {
                                    apiClient.startRtsp()
                                }
                                refreshStatus()
                                isToggling = false
                            }
                        },
                        enabled = !isToggling,
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(48.dp),
                        shape = RoundedCornerShape(12.dp),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = if (rtspStatus?.running == true) BrandRose else BrandEmerald,
                            contentColor = TextPrimary
                        )
                    ) {
                        if (isToggling) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(18.dp),
                                strokeWidth = 2.dp,
                                color = TextPrimary
                            )
                        } else {
                            Icon(
                                imageVector = if (rtspStatus?.running == true) Icons.Default.Stop else Icons.Default.PlayArrow,
                                contentDescription = null,
                                modifier = Modifier.size(18.dp)
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                text = if (rtspStatus?.running == true) "Stop Surveillance" else "Start Surveillance",
                                fontWeight = FontWeight.SemiBold
                            )
                        }
                    }
                }
            }
        }
    }
}
