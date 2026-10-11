package com.facedetection.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Dns
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.facedetection.app.ui.theme.BgRoot
import com.facedetection.app.ui.theme.BrandCyan
import com.facedetection.app.ui.theme.BrandEmerald
import com.facedetection.app.ui.theme.BrandPrimary
import com.facedetection.app.ui.theme.BrandPurple
import com.facedetection.app.ui.theme.BrandRose
import com.facedetection.app.ui.theme.TextMuted
import com.facedetection.app.ui.theme.TextPrimary
import com.facedetection.app.ui.theme.TextSecondary

/**
 * Rules for FaceEngineTopBar:
 * - Top app bar displaying FaceEngine branding, live server connectivity chip, and quick actions.
 * - Top-level variables and layout parameters must be declared at the top of the composable.
 * - Supports refresh action, switch server dialog action, and optional quick settings navigation.
 */
@Composable
fun FaceEngineTopBar(
    title: String,
    serverHost: String,
    isConnected: Boolean,
    onRefresh: (() -> Unit)? = null,
    onServerClick: (() -> Unit)? = null,
    onSettingsClick: (() -> Unit)? = null
) {
    Surface(
        color = BgRoot,
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 20.dp, vertical = 12.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                // Gradient Icon / Brand Tag
                Box(
                    modifier = Modifier
                        .size(36.dp)
                        .clip(RoundedCornerShape(10.dp))
                        .background(
                            Brush.linearGradient(
                                listOf(BrandPrimary, BrandPurple)
                            )
                        ),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "FE",
                        color = TextPrimary,
                        fontWeight = FontWeight.Bold,
                        fontSize = 14.sp
                    )
                }

                Spacer(modifier = Modifier.width(12.dp))

                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = title,
                        color = TextPrimary,
                        fontSize = 20.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Row(
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Box(
                            modifier = Modifier
                                .size(7.dp)
                                .clip(CircleShape)
                                .background(if (isConnected) BrandEmerald else BrandRose)
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            text = if (isConnected) serverHost else "Disconnected ($serverHost)",
                            color = if (isConnected) TextSecondary else BrandRose,
                            fontSize = 11.sp
                        )
                    }
                }

                if (onServerClick != null) {
                    IconButton(onClick = onServerClick) {
                        Icon(
                            imageVector = Icons.Default.Dns,
                            contentDescription = "Switch Server",
                            tint = BrandCyan,
                            modifier = Modifier.size(20.dp)
                        )
                    }
                }

                if (onRefresh != null) {
                    IconButton(onClick = onRefresh) {
                        Icon(
                            imageVector = Icons.Default.Refresh,
                            contentDescription = "Refresh",
                            tint = TextSecondary,
                            modifier = Modifier.size(22.dp)
                        )
                    }
                }

                if (onSettingsClick != null) {
                    IconButton(onClick = onSettingsClick) {
                        Icon(
                            imageVector = Icons.Default.Settings,
                            contentDescription = "Settings",
                            tint = TextSecondary,
                            modifier = Modifier.size(20.dp)
                        )
                    }
                }
            }
        }
    }
}
