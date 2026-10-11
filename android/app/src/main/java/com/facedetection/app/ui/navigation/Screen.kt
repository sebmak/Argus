package com.facedetection.app.ui.navigation

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Dashboard
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.People
import androidx.compose.material.icons.filled.RateReview
import androidx.compose.material.icons.filled.Science
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Videocam
import androidx.compose.ui.graphics.vector.ImageVector

/**
 * Rules for Screen:
 * - Represents all navigation destinations within the FaceEngine application.
 * - Variables and route identifiers must be declared at the top of the class/sealed class.
 * - Subclasses must provide a unique route string and appropriate title/icon metadata.
 * - Includes Account destination for credential management and remote exposure security.
 */
sealed class Screen(
    val route: String,
    val title: String,
    val icon: ImageVector? = null
) {
    object ServerSetup : Screen("server_setup", "Server Setup")
    object Login : Screen("login", "Authentication")
    object Dashboard : Screen("dashboard", "Overview", Icons.Default.Dashboard)
    object Review : Screen("review", "Review Queue", Icons.Default.RateReview)
    object Household : Screen("household", "Household", Icons.Default.People)
    object Rtsp : Screen("rtsp", "Live Camera", Icons.Default.Videocam)
    object Sandbox : Screen("sandbox", "Test Sandbox", Icons.Default.Science)
    object Events : Screen("events", "Event Log", Icons.Default.History)
    object Settings : Screen("settings", "Settings", Icons.Default.Settings)
    object Account : Screen("account", "Account & Security", Icons.Default.Lock)

    companion object {
        val navItems = listOf(
            Dashboard,
            Review,
            Household,
            Rtsp,
            Sandbox,
            Events,
            Settings
        )
    }
}
