package routor.src.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.rememberNavController
import routor.src.navigation.screens.GenerationsNavRoute
import routor.src.navigation.screens.MainNavRoute
import routor.src.navigation.screens.RoutesNavRoute
import routor.src.navigation.screens.generationsScreen
import routor.src.navigation.screens.mainScreen
import routor.src.navigation.screens.navigateToGenerations
import routor.src.navigation.screens.navigateToRouteDetails
import routor.src.navigation.screens.navigateToRoutes
import routor.src.navigation.screens.routeDetailsScreen
import routor.src.navigation.screens.routesScreen

@Composable
fun NavigationController() {
    val navController = rememberNavController()

    NavHost(
        navController = navController,
        startDestination = MainNavRoute
    ) {
        mainScreen(
            onNavigateToRoutes = { navController.navigateToRoutes() },
            onNavigateToGenerations = { navController.navigateToGenerations() }
        )

        routesScreen(
            onNavigateToMain = { navController.navigateUp() },
            onNavigateToRouteDetails = { id: Long -> navController.navigateToRouteDetails(id) }
        )

        routeDetailsScreen(
            onNavigateBack = { navController.navigateUp() }
        )

        generationsScreen(
            onNavigateToMain = { navController.navigateUp() }
        )
    }
}