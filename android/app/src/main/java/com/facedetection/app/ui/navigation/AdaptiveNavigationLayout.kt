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
 * Adaptive navigation scaffold supporting:
 * - Bottom NavigationBar when folded or on compact phones (< 600dp width)
 * - Side NavigationRail when unfolded on foldable devices or tablets (>= 600dp width)
 */
@Composable
fun AdaptiveNavigationLayout(
    currentRoute: String,
    onNavigate: (Screen) -> Unit,
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
            NavigationRail(
                modifier = Modifier.fillMaxHeight(),
                containerColor = BgSurface,
                contentColor = TextPrimary
            ) {
                Screen.navItems.forEach { screen ->
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
                            Text(text = screen.title, fontSize = 11.sp)
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
                NavigationBar(
                    containerColor = BgSurface,
                    tonalElevation = 8.dp
                ) {
                    Screen.navItems.forEach { screen ->
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
                                    text = screen.title,
                                    fontSize = 10.sp,
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
        ) { paddingValues ->
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(paddingValues)
            ) {
                content()
            }
        }
    }
}
