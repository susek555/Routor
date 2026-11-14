package routor.src.screens.routeDetails

import routor.src.data.types.PlannedRoute
import routor.src.data.types.Point
import routor.src.data.types.Route

sealed interface RouteDetailsUiState {
    data object Loading : RouteDetailsUiState
    data class Success(
        val route: Route,
        val points: List<Point>,
        val plannedRoute: PlannedRoute? = null
    ) : RouteDetailsUiState
    data object Error : RouteDetailsUiState
}