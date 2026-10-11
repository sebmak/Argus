package com.facedetection.app.ui.theme

import android.app.Activity
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

private val DarkColorScheme = darkColorScheme(
    primary = BrandPrimary,
    onPrimary = TextPrimary,
    primaryContainer = BrandPrimaryHover,
    onPrimaryContainer = TextPrimary,
    secondary = BrandCyan,
    onSecondary = BgRoot,
    secondaryContainer = BgSurfaceCard,
    onSecondaryContainer = TextPrimary,
    tertiary = BrandPurple,
    onTertiary = TextPrimary,
    background = BgRoot,
    onBackground = TextPrimary,
    surface = BgSurface,
    onSurface = TextPrimary,
    surfaceVariant = BgSurfaceCard,
    onSurfaceVariant = TextSecondary,
    outline = BorderAccent,
    error = BrandRose,
    onError = TextPrimary
)

@Composable
fun FaceEngineTheme(
    darkTheme: Boolean = true,
    content: @Composable () -> Unit
) {
    val colorScheme = DarkColorScheme
    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            window.statusBarColor = BgRoot.toArgb()
            window.navigationBarColor = BgRoot.toArgb()
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = false
            WindowCompat.getInsetsController(window, view).isAppearanceLightNavigationBars = false
        }
    }

    MaterialTheme(
        colorScheme = colorScheme,
        content = content
    )
}
