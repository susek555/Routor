package routor.src.screens.routes

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import routor.src.data.repositories.RouteRepository
import routor.src.data.types.Route
import routor.src.dialogFactory.confirmDialog.ConfirmDialogConfig
import routor.src.dialogFactory.confirmDialog.ConfirmDialogConfigState
import routor.src.dialogFactory.confirmDialog.ConfirmDialogFactory
import routor.src.dialogFactory.confirmDialog.ConfirmDialogState
import javax.inject.Inject

@HiltViewModel
class RoutesViewModel @Inject constructor(
    private val routesRepository: RouteRepository,
    private val dialogFactory: ConfirmDialogFactory
)  : ViewModel() {

    private val _routes = MutableStateFlow<List<Route>>(emptyList())
    val routes: StateFlow<List<Route>> = _routes.asStateFlow()

    init {
        loadRoutes()
    }

    private fun loadRoutes() {
        viewModelScope.launch {
            _routes.value = routesRepository.getAllRoutes()  // Runs in background
        }
    }

    private val _isRouteDialogOpen = MutableStateFlow(false)
    private val _routeDialogConfig = MutableStateFlow<ConfirmDialogConfig?>(
        dialogFactory.create(
            ConfirmDialogConfigState.None,
            onConfirm = {},
            onDismiss = {}
        )
    )
    val routeDialogState = combine(_isRouteDialogOpen, _routeDialogConfig) { isVisible, config ->
        ConfirmDialogState(isVisible, config)
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), ConfirmDialogState(false, null))

    fun onEvent(event: RoutesScreenEvent) {
        when(event) {
            is RoutesScreenEvent.DeleteRoute -> {
                viewModelScope.launch {
                    routesRepository.deleteRoute(event.route)
                    _routes.value = routesRepository.getAllRoutes()
                }
                _isRouteDialogOpen.value = false
            }
            is RoutesScreenEvent.EditRoute -> {
                val updatedRoute = event.route.copy(name = event.name)
                viewModelScope.launch{
                    routesRepository.updateRoute(updatedRoute)
                    _routes.value = routesRepository.getAllRoutes()
                }
                _isRouteDialogOpen.value = false
            }
            RoutesScreenEvent.HideRouteDialog -> {
                _isRouteDialogOpen.value = false
            }
            is RoutesScreenEvent.ShowEditRouteDialog -> {
                setDialogConfig(DialogConfig.EDIT, event.route)
                _isRouteDialogOpen.value = true
            }
            is RoutesScreenEvent.ShowDeleteRouteDialog -> {
                setDialogConfig(DialogConfig.DELETE, event.route)
                _isRouteDialogOpen.value = true
            }
        }
    }

    private enum class DialogConfig {
        EDIT, DELETE
    }

    private fun setDialogConfig(config: DialogConfig, route: Route) {
        if(config == DialogConfig.EDIT){
            _routeDialogConfig.value = dialogFactory.create(
                ConfirmDialogConfigState.EditRoute,
                onConfirm = { name -> onEvent(RoutesScreenEvent.EditRoute(route, name!!))},
                onDismiss = { onEvent(RoutesScreenEvent.HideRouteDialog)},
                baseTextState = route.name
            )
        } else {
            _routeDialogConfig.value = dialogFactory.create(
                ConfirmDialogConfigState.DeleteRoute,
                onConfirm = { onEvent(RoutesScreenEvent.DeleteRoute(route))},
                onDismiss = { onEvent(RoutesScreenEvent.HideRouteDialog)}
            )
        }
    }
}