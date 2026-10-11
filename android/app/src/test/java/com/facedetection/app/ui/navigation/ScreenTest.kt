package com.facedetection.app.ui.navigation

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Rules for ScreenTest:
 * 1. Variables must be declared at the top of the test class.
 * 2. Asynchronous operations must prefer Coroutines where appropriate.
 * 3. Class documentation comments must be maintained for all changes.
 * 4. Validates Screen definitions, route uniqueness, and responsive nav item collections.
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
    fun testCompactNavItemsFollowMaterial3Guidelines() {
        val compactItems = Screen.compactNavItems
        assertEquals(5, compactItems.size)
        val expectedRoutes = listOf(
            Screen.Dashboard.route,
            Screen.Review.route,
            Screen.Household.route,
            Screen.Rtsp.route,
            Screen.Events.route
        )
        assertEquals(expectedRoutes, compactItems.map { it.route })
        compactItems.forEach { screen ->
            assertTrue("shortTitle must not be blank", screen.shortTitle.isNotBlank())
            assertTrue("shortTitle should be concise for compact bottom bar", screen.shortTitle.length <= 12)
        }
    }

    @Test
    fun testExpandedNavItemsContainAllSections() {
        val expandedItems = Screen.expandedNavItems
        assertEquals(7, expandedItems.size)
        assertEquals(Screen.navItems.map { it.route }, expandedItems.map { it.route })
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
