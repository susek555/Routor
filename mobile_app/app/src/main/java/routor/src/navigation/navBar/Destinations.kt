package routor.src.navigation.navBar

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Place
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.navigation.NavDestination
import androidx.navigation.NavDestination.Companion.hasRoute
import routor.src.navigation.screens.GenerationsNavRoute
import routor.src.navigation.screens.MainNavRoute
import routor.src.navigation.screens.RoutesNavRoute

enum class Destinations(
    val label: String,
    val icon: ImageVector,
    val route: Any
) {
    GENERATE(
        label = "Generate",
        icon = Icons.Default.Add,
        route = GenerationsNavRoute
    ),
    EXPLORE(
        label = "Explore",
        icon = Icons.Default.Place,
        route = MainNavRoute
    ),
    ROUTES(
        label = "Routes",
        icon = Icons.AutoMirrored.Filled.List,
        route = RoutesNavRoute
    );

    fun matches(destination: NavDestination?): Boolean = when (this) {
        GENERATE -> destination?.hasRoute<GenerationsNavRoute>() == true
        EXPLORE -> destination?.hasRoute<MainNavRoute>() == true
        ROUTES -> destination?.hasRoute<RoutesNavRoute>() == true
    }

    companion object {
        fun isTopLevel(destination: NavDestination?): Boolean =
            entries.any { it.matches(destination) }
    }
}