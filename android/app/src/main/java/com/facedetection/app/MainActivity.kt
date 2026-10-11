package com.facedetection.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.facedetection.app.data.FaceEngineApiClient
import com.facedetection.app.data.ServerConfigManager
import com.facedetection.app.ui.navigation.AdaptiveNavigationLayout
import com.facedetection.app.ui.navigation.Screen
import com.facedetection.app.ui.screens.DashboardScreen
import com.facedetection.app.ui.screens.EventsScreen
import com.facedetection.app.ui.screens.HouseholdScreen
import com.facedetection.app.ui.screens.LoginScreen
import com.facedetection.app.ui.screens.ReviewQueueScreen
import com.facedetection.app.ui.screens.RtspScreen
import com.facedetection.app.ui.screens.SandboxScreen
import com.facedetection.app.ui.screens.ServerSetupScreen
import com.facedetection.app.ui.screens.SettingsScreen
import com.facedetection.app.ui.theme.FaceEngineTheme

/**
 * Rules for MainActivity:
 * 1. Variables must be declared at the top of the class.
 * 2. Asynchronous operations and network calls must prefer Coroutines.
 * 3. Class documentation comments must be maintained for all changes.
 * 4. Provides native Jetpack Compose architecture with adaptive foldable navigation.
 */
class MainActivity : ComponentActivity() {

    private lateinit var configManager: ServerConfigManager
    private lateinit var apiClient: FaceEngineApiClient

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        configManager = ServerConfigManager(this)
        apiClient = FaceEngineApiClient(configManager)

        setContent {
            FaceEngineTheme {
                FaceEngineAppContent(
                    configManager = configManager,
                    apiClient = apiClient
                )
            }
        }
    }
}

/**
 * Root Composable orchestrating navigation and adaptive foldable shell.
 */
@Composable
fun FaceEngineAppContent(
    configManager: ServerConfigManager,
    apiClient: FaceEngineApiClient
) {
    val navController = rememberNavController()
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = navBackStackEntry?.destination?.route ?: Screen.Dashboard.route

    val initialRoute = when {
        !configManager.isConfigured() -> Screen.ServerSetup.route
        configManager.getAuthToken().isNullOrBlank() -> Screen.Login.route
        else -> Screen.Dashboard.route
    }

    val isTopLevelDestination = Screen.navItems.any { it.route == currentRoute }

    if (isTopLevelDestination) {
        AdaptiveNavigationLayout(
            currentRoute = currentRoute,
            onNavigate = { screen ->
                navController.navigate(screen.route) {
                    popUpTo(navController.graph.findStartDestination().id) {
                        saveState = true
                    }
                    launchSingleTop = true
                    restoreState = true
                }
            }
        ) {
            AppNavHost(
                navController = navController,
                startDestination = initialRoute,
                configManager = configManager,
                apiClient = apiClient
            )
        }
    } else {
        AppNavHost(
            navController = navController,
            startDestination = initialRoute,
            configManager = configManager,
            apiClient = apiClient
        )
    }
}

@Composable
private fun AppNavHost(
    navController: androidx.navigation.NavHostController,
    startDestination: String,
    configManager: ServerConfigManager,
    apiClient: FaceEngineApiClient
) {
    NavHost(
        navController = navController,
        startDestination = startDestination
    ) {
        composable(Screen.ServerSetup.route) {
            ServerSetupScreen(
                configManager = configManager,
                apiClient = apiClient,
                onConfigured = {
                    navController.navigate(Screen.Login.route) {
                        popUpTo(Screen.ServerSetup.route) { inclusive = true }
                    }
                },
                onCancel = if (configManager.isConfigured()) {
                    { navController.popBackStack() }
                } else null
            )
        }

        composable(Screen.Login.route) {
            LoginScreen(
                configManager = configManager,
                apiClient = apiClient,
                onLoginSuccess = {
                    navController.navigate(Screen.Dashboard.route) {
                        popUpTo(Screen.Login.route) { inclusive = true }
                    }
                },
                onChangeServer = {
                    navController.navigate(Screen.ServerSetup.route)
                }
            )
        }

        composable(Screen.Dashboard.route) {
            DashboardScreen(
                apiClient = apiClient,
                onNavigate = { destination ->
                    navController.navigate(destination.route)
                },
                onSwitchServer = {
                    navController.navigate(Screen.ServerSetup.route)
                }
            )
        }

        composable(Screen.Review.route) {
            ReviewQueueScreen(
                apiClient = apiClient,
                onSwitchServer = {
                    navController.navigate(Screen.ServerSetup.route)
                }
            )
        }

        composable(Screen.Household.route) {
            HouseholdScreen(
                apiClient = apiClient,
                onSwitchServer = {
                    navController.navigate(Screen.ServerSetup.route)
                }
            )
        }

        composable(Screen.Rtsp.route) {
            RtspScreen(
                apiClient = apiClient,
                onSwitchServer = {
                    navController.navigate(Screen.ServerSetup.route)
                }
            )
        }

        composable(Screen.Sandbox.route) {
            SandboxScreen(
                apiClient = apiClient,
                onSwitchServer = {
                    navController.navigate(Screen.ServerSetup.route)
                }
            )
        }

        composable(Screen.Events.route) {
            EventsScreen(
                apiClient = apiClient,
                onSwitchServer = {
                    navController.navigate(Screen.ServerSetup.route)
                }
            )
        }

        composable(Screen.Settings.route) {
            SettingsScreen(
                configManager = configManager,
                apiClient = apiClient,
                onSwitchServer = {
                    navController.navigate(Screen.ServerSetup.route)
                },
                onLogout = {
                    navController.navigate(Screen.Login.route) {
                        popUpTo(0) { inclusive = true }
                    }
                }
            )
        }
    }
}
