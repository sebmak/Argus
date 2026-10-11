package com.facedetection.app.ui.navigation

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Rules for ScreenTest:
 * - Validates Screen definitions and navigation items list.
 * - Ensures no null pointers occur during static or dynamic class loading.
 */
class ScreenTest {

    @Test
    fun testNavItemsAreNonNullAndValid() {
        val items = Screen.navItems
        assertEquals(7, items.size)
        items.forEach { screen ->
            assertNotNull("Screen in navItems must not be null", screen)
            assertNotNull("Screen route must not be null", screen.route)
            assertTrue("Screen route must not be blank", screen.route.isNotBlank())
            assertNotNull("Screen title must not be null", screen.title)
        }
    }

    @Test
    fun testAllScreensHaveUniqueRoutes() {
        val allScreens = listOf(
            Screen.ServerSetup,
            Screen.Login,
            Screen.Dashboard,
            Screen.Review,
            Screen.Household,
            Screen.Rtsp,
            Screen.Sandbox,
            Screen.Events,
            Screen.Settings,
            Screen.Account
        )
        val routes = allScreens.map { it.route }
        assertEquals(routes.size, routes.distinct().size)
    }
}
