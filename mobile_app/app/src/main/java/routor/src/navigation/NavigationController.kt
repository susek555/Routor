package routor.src.navigation

import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Scaffold
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import routor.src.navigation.navBar.NavBar
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
    val navBackStackEntry by navController.currentBackStackEntryAsState()

    Scaffold(
        bottomBar = {
            NavBar(
                currentDestination = navBackStackEntry?.destination,
                onTabSelected = { tab -> navController.navigateToBottomTab(tab.route) }
            )
        }
    ) { innerPadding ->
        NavHost(
            navController = navController,
            startDestination = MainNavRoute,
            modifier = Modifier.padding(innerPadding)
        ) {
            mainScreen(
                onNavigateToRoutes = { navController.navigateToBottomTab(RoutesNavRoute) }
            )

            routesScreen(
                onNavigateToRouteDetails = { id: Long -> navController.navigateToRouteDetails(id) }
            )

            routeDetailsScreen(
                onNavigateBack = { navController.navigateUp() }
            )

            generationsScreen(
                onNavigateToMain = { navController.navigateToBottomTab(MainNavRoute) }
            )
        }
    }
}

private fun NavHostController.navigateToBottomTab(route: Any) {
    navigate(route) {
        popUpTo(graph.findStartDestination().id) {
            saveState = true
        }
        launchSingleTop = true
        restoreState = true
    }
}