package routor.src.screens.routes

import routor.src.data.types.Route

sealed interface RoutesScreenEvent {
    data class ShowEditRouteDialog(val route: Route): RoutesScreenEvent
    data class ShowDeleteRouteDialog(val route: Route): RoutesScreenEvent
    data object HideRouteDialog: RoutesScreenEvent
    data class DeleteRoute(val route: Route): RoutesScreenEvent
    data class EditRoute(val route: Route, val name: String): RoutesScreenEvent
}