package routor.src.screens.routeDetails

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.navigation.toRoute
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.flow.receiveAsFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import org.maplibre.android.geometry.LatLng
import routor.src.data.repositories.PointRepository
import routor.src.data.repositories.RouteRepository
import routor.src.data.types.Route
import routor.src.dialogFactory.confirmDialog.ConfirmDialogConfig
import routor.src.dialogFactory.confirmDialog.ConfirmDialogConfigState
import routor.src.dialogFactory.confirmDialog.ConfirmDialogFactory
import routor.src.dialogFactory.confirmDialog.ConfirmDialogState
import routor.src.navigation.screens.RouteDetailsNavRoute
import javax.inject.Inject

@HiltViewModel
class RouteDetailsViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val routesRepository: RouteRepository,
    private val pointsRepository: PointRepository,
    private val dialogFactory: ConfirmDialogFactory
) : ViewModel() {
    private val routeId = savedStateHandle.toRoute<RouteDetailsNavRoute>().routeId

    // Init UI State
    val uiState: StateFlow<RouteDetailsUiState> = combine(
        routesRepository.getRoute(routeId),

        flow {
            emit(pointsRepository.getPointsForRoute(routeId))
        }.flowOn(Dispatchers.IO)
    ) { route, points ->
        if (route == null) {
            RouteDetailsUiState.Error
        } else {
            RouteDetailsUiState.Success(route = route, points = points)
        }
    }.stateIn(
        scope = viewModelScope,
        started = SharingStarted.WhileSubscribed(5000),
        initialValue = RouteDetailsUiState.Loading
    )

    // Route access
    private val currentRoute: Route?
        get() = (uiState.value as? RouteDetailsUiState.Success)?.route

    // Dialogs state
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

    // Navigate back on route deletion event
    private val _routeDeletedEvent = Channel<Boolean>()
    val routeDeletedEvent = _routeDeletedEvent.receiveAsFlow()



    fun onEvent(event: RouteDetailsEvent) {
        when(event) {
            is RouteDetailsEvent.DeleteRoute -> {
                val route = currentRoute ?: return
                viewModelScope.launch {
                    routesRepository.deleteRoute(route)
                    _routeDeletedEvent.send(true)
                }
                _isRouteDialogOpen.value = false
            }
            is RouteDetailsEvent.EditRoute -> {
                val route = currentRoute ?: return
                viewModelScope.launch {
                    routesRepository.updateRoute(route.copy(name = event.name))
                }
                _isRouteDialogOpen.value = false
            }
            RouteDetailsEvent.HideRouteDialog -> {
                _isRouteDialogOpen.value = false
            }
            is RouteDetailsEvent.ShowEditRouteDialog -> {
                //TODO remove print
                println(currentRoute!!)
                setDialogConfig(DialogConfig.EDIT, currentRoute!!)
                _isRouteDialogOpen.value = true
            }
            is RouteDetailsEvent.ShowDeleteRouteDialog -> {
                setDialogConfig(DialogConfig.DELETE, currentRoute!!)
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
                onConfirm = { name -> onEvent(RouteDetailsEvent.EditRoute(name!!))},
                onDismiss = { onEvent(RouteDetailsEvent.HideRouteDialog)},
                baseTextState = route.name
            )
        } else {
            _routeDialogConfig.value = dialogFactory.create(
                ConfirmDialogConfigState.DeleteRoute,
                onConfirm = { onEvent(RouteDetailsEvent.DeleteRoute)},
                onDismiss = { onEvent(RouteDetailsEvent.HideRouteDialog)},
                routeName = route.name
            )
        }
    }
}