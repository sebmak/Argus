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
 * - Supports compact 5-tab mobile bottom bar and expanded tablet/foldable rail.
 * - navItems uses a dynamic getter to prevent circular static initialization null references.
 */
sealed class Screen(
    val route: String,
    val title: String,
    val icon: ImageVector? = null,
    val shortTitle: String = title
) {
    data object ServerSetup : Screen("server_setup", "Server Setup")
    data object Login : Screen("login", "Authentication")
    data object Dashboard : Screen("dashboard", "Overview", Icons.Default.Dashboard, "Overview")
    data object Review : Screen("review", "Review Queue", Icons.Default.RateReview, "Review")
    data object Household : Screen("household", "Household", Icons.Default.People, "Household")
    data object Rtsp : Screen("rtsp", "Live Camera", Icons.Default.Videocam, "Camera")
    data object Sandbox : Screen("sandbox", "Test Sandbox", Icons.Default.Science, "Sandbox")
    data object Events : Screen("events", "Event Log", Icons.Default.History, "Events")
    data object Settings : Screen("settings", "Settings", Icons.Default.Settings, "Settings")
    data object Account : Screen("account", "Account & Security", Icons.Default.Lock, "Account")

    companion object {
        val compactNavItems: List<Screen>
            get() = listOf(
                Dashboard,
                Review,
                Household,
                Rtsp,
                Events
            )

        val expandedNavItems: List<Screen>
            get() = listOf(
                Dashboard,
                Review,
                Household,
                Rtsp,
                Sandbox,
                Events,
                Settings
            )

        val navItems: List<Screen>
            get() = expandedNavItems
    }
}
