package routor.src.screens.routeDetails

sealed interface RouteDetailsEvent {
    data object ShowEditRouteDialog: RouteDetailsEvent
    data object ShowDeleteRouteDialog: RouteDetailsEvent
    data object HideRouteDialog: RouteDetailsEvent
    data object DeleteRoute: RouteDetailsEvent
    data class EditRoute(val name: String): RouteDetailsEvent
}