package com.facedetection.app.ui.navigation

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.NavigationRail
import androidx.compose.material3.NavigationRailItem
import androidx.compose.material3.NavigationRailItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.facedetection.app.ui.theme.BgRoot
import com.facedetection.app.ui.theme.BgSurface
import com.facedetection.app.ui.theme.BrandPrimary
import com.facedetection.app.ui.theme.TextMuted
import com.facedetection.app.ui.theme.TextPrimary

/**
 * Rules for AdaptiveNavigationLayout:
 * 1. Preserves single NavHost composition subtree across all screen transitions.
 * 2. Mobile/folded viewport (< 600dp width) renders Screen.compactNavItems in Bottom NavigationBar.
 * 3. Expanded/tablet viewport (>= 600dp width) renders Screen.expandedNavItems in Side NavigationRail.
 * 4. Renders concise shortTitle labels and Material 3 touch targets to avoid overlapping mis-clicks.
 * 5. Toggles navigation container visibility via showNavigation without recreating child content.
 */
@Composable
fun AdaptiveNavigationLayout(
    currentRoute: String,
    onNavigate: (Screen) -> Unit,
    showNavigation: Boolean = true,
    content: @Composable () -> Unit
) {
    val configuration = LocalConfiguration.current
    val isExpanded = configuration.screenWidthDp >= 600

    if (isExpanded) {
        // Foldable unfolded / tablet mode: Side Navigation Rail
        Row(
            modifier = Modifier
                .fillMaxSize()
                .background(BgRoot)
        ) {
            if (showNavigation) {
                NavigationRail(
                    modifier = Modifier.fillMaxHeight(),
                    containerColor = BgSurface,
                    contentColor = TextPrimary
                ) {
                    Screen.expandedNavItems.forEach { screen ->
                        val isSelected = currentRoute == screen.route
                        NavigationRailItem(
                            selected = isSelected,
                            onClick = { onNavigate(screen) },
                            icon = {
                                screen.icon?.let {
                                    Icon(imageVector = it, contentDescription = screen.title)
                                }
                            },
                            label = {
                                Text(text = screen.shortTitle, fontSize = 11.sp)
                            },
                            colors = NavigationRailItemDefaults.colors(
                                selectedIconColor = TextPrimary,
                                selectedTextColor = BrandPrimary,
                                indicatorColor = BrandPrimary,
                                unselectedIconColor = TextMuted,
                                unselectedTextColor = TextMuted
                            )
                        )
                    }
                }
            }

            Box(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxHeight()
            ) {
                content()
            }
        }
    } else {
        // Compact phone / folded mode: Bottom Navigation Bar
        Scaffold(
            containerColor = BgRoot,
            bottomBar = {
                if (showNavigation) {
                    NavigationBar(
                        containerColor = BgSurface,
                        tonalElevation = 8.dp
                    ) {
                        Screen.compactNavItems.forEach { screen ->
                            val isSelected = currentRoute == screen.route
                            NavigationBarItem(
                                selected = isSelected,
                                onClick = { onNavigate(screen) },
                                icon = {
                                    screen.icon?.let {
                                        Icon(imageVector = it, contentDescription = screen.title)
                                    }
                                },
                                label = {
                                    Text(
                                        text = screen.shortTitle,
                                        fontSize = 11.sp,
                                        maxLines = 1
                                    )
                                },
                                colors = NavigationBarItemDefaults.colors(
                                    selectedIconColor = TextPrimary,
                                    selectedTextColor = BrandPrimary,
                                    indicatorColor = BrandPrimary,
                                    unselectedIconColor = TextMuted,
                                    unselectedTextColor = TextMuted
                                )
                            )
                        }
                    }
                }
            }
        ) { paddingValues ->
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(if (showNavigation) paddingValues else androidx.compose.foundation.layout.PaddingValues(0.dp))
            ) {
                content()
            }
        }
    }
}
