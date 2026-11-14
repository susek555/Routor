package routor.src.screens.main

import android.content.Context
import android.content.Intent
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import routor.src.dialogFactory.confirmDialog.ConfirmDialogConfig
import routor.src.dialogFactory.confirmDialog.ConfirmDialogFactory
import routor.src.dialogFactory.confirmDialog.ConfirmDialogConfigState
import routor.src.dialogFactory.confirmDialog.ConfirmDialogState
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.stateIn
import kotlinx.datetime.Clock
import kotlinx.datetime.TimeZone
import kotlinx.datetime.toLocalDateTime
import org.maplibre.android.geometry.LatLng
import routor.src.data.repositories.LocationRepository
import routor.src.data.repositories.PlannedRoutesRepository
import routor.src.data.repositories.RouteRepository
import routor.src.data.types.PlannedRoute
import routor.src.data.types.Route
import routor.src.dialogFactory.infoDialog.InfoDialogConfigState
import routor.src.dialogFactory.infoDialog.InfoDialogState
import routor.src.dialogFactory.infoDialog.InfoDialogFactory
import routor.src.location.LocationService
import routor.src.state.ActiveRideHolder
import javax.inject.Inject

@HiltViewModel
class MainViewModel @Inject constructor(
    private val activeRideHolder: ActiveRideHolder,
    private val locationRepository: LocationRepository,
    private val routeRepository: RouteRepository,
    private val plannedRoutesRepository: PlannedRoutesRepository,
    private val dialogFactory: ConfirmDialogFactory,
    private val infoDialogFactory: InfoDialogFactory,
    @ApplicationContext private val context: Context,
) : ViewModel() {
    // Constant
    private val MINIMUM_NUMBER_OF_POINTS = 10

    // recording route toggle
    val isServiceRecordingRoute = activeRideHolder.isRecording

    // currently recorded route
    private var currentRoute: MutableStateFlow<Route?> = MutableStateFlow(null)

    // end route dialogs state
    private val _isSavingRoute = MutableStateFlow(false)
    private val _isStopRouteDialogOpen = MutableStateFlow(false)
    private val _stopRouteDialogConfig = MutableStateFlow<ConfirmDialogConfig?>(
        dialogFactory.create(
            ConfirmDialogConfigState.None,
            onConfirm = {},
            onDismiss = {}
        )
    )
    val stopRouteDialogState = combine(_isStopRouteDialogOpen, _stopRouteDialogConfig) {isVisible, config ->
        ConfirmDialogState(isVisible, config)
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), ConfirmDialogState(false, null))

    // center map event
    private val _centerMapEvent = MutableSharedFlow<LatLng>(replay = 0)
    val centerMapEvent = _centerMapEvent.asSharedFlow()

    private val _navigateToDetailsEvent = MutableSharedFlow<Long>(replay = 0)
    val navigateToDetailsEvent = _navigateToDetailsEvent.asSharedFlow()

    // UI state
    val uiState = combine(
        locationRepository.currentLocation,
        locationRepository.routeStatsFlow,
        locationRepository.duration,
        activeRideHolder.followedRoute,
        combine(
            isServiceRecordingRoute,
            _isSavingRoute,
            _isStopRouteDialogOpen,
            _stopRouteDialogConfig
        ) { recording, saving, isConfirmVisible, confirmConfig ->
            val infoState = InfoDialogState(
                isVisible = saving,
                config = if (saving) infoDialogFactory.create(InfoDialogConfigState.SavingRoute) else null
            )
            Triple(recording, ConfirmDialogState(isConfirmVisible, confirmConfig), infoState)
        }
    ) { loc, stats, dur, followed, (recording, confirmDialog, infoDialog) ->
        MainScreenUiState(
            currentLocation = loc,
            routeStats = stats,
            duration = dur,
            followedRoute = followed,
            isRecording = recording,
            dialogState = confirmDialog,
            infoDialogState = infoDialog
        )
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), MainScreenUiState())

     init {
         viewModelScope.launch {
             // center map on user location
             if (!isServiceRecordingRoute.value){
                 sendActionToLocationService(LocationService.ACTION_GET_SINGLE_LOCATION)

                 // wait for location to appear
                 locationRepository.currentLocation.first { it != null }
                 _centerMapEvent.emit(locationRepository.currentLocation.value!!)
             }
         }
    }

    fun onEvent(event: MainScreenEvent) {
        when(event) {
            MainScreenEvent.HideStopRouteDialog -> {
                _isStopRouteDialogOpen.value = false
            }
            MainScreenEvent.ShowStopRouteDialog -> {
                setDialogConfig()
                _isStopRouteDialogOpen.value = true
            }
            MainScreenEvent.StartRoute -> {
                if(!isServiceRecordingRoute.value){
                    startRecording()
                }
            }
            is MainScreenEvent.SaveRoute -> {
                if (isServiceRecordingRoute.value && !_isSavingRoute.value) {
                    _isStopRouteDialogOpen.value = false
                    viewModelScope.launch {
                        saveRouteAndNavigate(name = event.name)
                    }
                }
            }
            MainScreenEvent.CancelRoute -> {
                if(isServiceRecordingRoute.value){
                    viewModelScope.launch { cancelRoute() }
                    stopRecording()
                    _isStopRouteDialogOpen.value = false
                }
            }
            MainScreenEvent.CenterMapOnCurrentLocation -> {
                locationRepository.currentLocation.value?.let {
                    viewModelScope.launch { _centerMapEvent.emit(locationRepository.currentLocation.value!!) }
                    if (!isServiceRecordingRoute.value){
                        sendActionToLocationService(LocationService.ACTION_GET_SINGLE_LOCATION)
                    }
                }
            }

            MainScreenEvent.ClearFollowedRoute -> {
                activeRideHolder.setFollowedRoute(null)
            }
        }
    }

    //location service
    private fun sendActionToLocationService(action: String) {
        Intent(context, LocationService::class.java).apply {
            this.action = action
            context.startService(this)
        }
    }

    //dialog
    private fun setDialogConfig() {
        if(locationRepository.routeStatsFlow.value.numberOfPointsOnRoute < MINIMUM_NUMBER_OF_POINTS){
            _stopRouteDialogConfig.value = dialogFactory.create(
                ConfirmDialogConfigState.RouteNotLongEnough,
                onConfirm = { onEvent(MainScreenEvent.CancelRoute)},
                onDismiss = { onEvent(MainScreenEvent.HideStopRouteDialog)}
            )
        } else {
            _stopRouteDialogConfig.value = dialogFactory.create(
                ConfirmDialogConfigState.RouteAskForName,
                onConfirm = { name -> onEvent(MainScreenEvent.SaveRoute(name!!))},
                onDismiss = { onEvent(MainScreenEvent.HideStopRouteDialog)}
            )
        }
    }

    //recording
    private fun startRecording(){
        //prepare route
        viewModelScope.launch {
            val localDate = Clock.System.now()
                .toLocalDateTime(TimeZone.currentSystemDefault())
                .date

            val newRoute = Route(
                name = "",
                numberOfPoints = 0,
                date = localDate,
                duration = 0,
                distanceKm = 0f,
            )

            // wait for ID
            val routeId = routeRepository.insertRoute(newRoute)
            currentRoute.value = newRoute.copy(id = routeId)

            locationRepository.startRecording(routeId)

            sendActionToLocationService(LocationService.ACTION_START_RECORDING)
            activeRideHolder.setRecording(true)
        }
    }

    private fun stopRecording(){
        sendActionToLocationService(LocationService.ACTION_STOP_RECORDING)
        activeRideHolder.setRecording(false)
        locationRepository.stopRecording()
    }

    private suspend fun cancelRoute() {
        println("route cancelled")
        routeRepository.deleteRoute(currentRoute.value!!)
    }

    private suspend fun saveRouteAndNavigate(name: String) {
        val baseRoute = currentRoute.value ?: return
        _isSavingRoute.value = true

        try {
            // 1. Collect stats and stop the recording
            val finalPointsCount = locationRepository.routeStatsFlow.value.numberOfPointsOnRoute
            val finalDuration = locationRepository.duration.value
            val finalDistanceKm = locationRepository.routeStatsFlow.value.totalDistanceKm
            stopRecording()

            // 2. Save followed route if present
            val followed = activeRideHolder.followedRoute.value
            val plannedRouteId: Long? = if (followed != null) {
                plannedRoutesRepository.insertRoute(
                    PlannedRoute(
                        targetDistanceMeters = followed.distanceMeters,
                        points = followed.points
                    )
                )
            } else {
                null
            }

            // 3. Update current route with name and stats
            val updatedRoute = baseRoute.copy(
                name = name,
                numberOfPoints = finalPointsCount,
                duration = finalDuration,
                distanceKm = finalDistanceKm,
                plannedRouteId = plannedRouteId
            )
            routeRepository.updateRoute(updatedRoute)

            // 4. Clear holder and navigate to route details
            activeRideHolder.setFollowedRoute(null)
            currentRoute.value = null
            _navigateToDetailsEvent.emit(updatedRoute.id)
        } finally {
            _isSavingRoute.value = false
        }
    }
}