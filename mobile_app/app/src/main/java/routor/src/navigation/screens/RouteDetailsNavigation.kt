package routor.src.navigation.screens

import kotlinx.serialization.Serializable
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import androidx.navigation.NavGraphBuilder
import androidx.navigation.compose.composable
import routor.src.screens.routeDetails.RouteDetailsScreen
import routor.src.screens.routeDetails.RouteDetailsViewModel


@Serializable
data class RouteDetailsNavRoute(val routeId: Long)

fun NavController.navigateToRouteDetails(routeId: Long) {
    navigate(RouteDetailsNavRoute(routeId))
}

fun NavGraphBuilder.routeDetailsScreen(onNavigateBack: () -> Unit) {
    composable<RouteDetailsNavRoute> { backStackEntry ->
        RouteDetailsScreen(
            viewModel = hiltViewModel<RouteDetailsViewModel>(backStackEntry),
            displayRoutesScreen = onNavigateBack
        )
    }
}