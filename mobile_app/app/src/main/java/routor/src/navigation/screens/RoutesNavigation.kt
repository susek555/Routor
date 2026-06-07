package routor.src.navigation.screens

import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import androidx.navigation.NavGraphBuilder
import androidx.navigation.compose.composable
import kotlinx.serialization.Serializable
import routor.src.screens.routes.RoutesScreen
import routor.src.screens.routes.RoutesViewModel

@Serializable
object RoutesNavRoute

fun NavController.navigateToRoutes() {
    navigate(RoutesNavRoute)
}

fun NavGraphBuilder.routesScreen(
    onNavigateToMain: () -> Unit,
    onNavigateToRouteDetails: (Long) -> Unit
) {
    composable<RoutesNavRoute> { backStackEntry ->
        RoutesScreen(
            viewModel = hiltViewModel<RoutesViewModel>(backStackEntry),
            displayMainScreen = {
                onNavigateToMain()
            },
            displayRouteDetailsScreen = { id ->
                onNavigateToRouteDetails(id)
            }
        )
    }
}