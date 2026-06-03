package routor.src.screens.main

import android.content.Context
import android.content.Intent
import android.os.SystemClock
import androidx.compose.runtime.MutableState
import androidx.compose.runtime.mutableStateOf
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import routor.src.dialogFactory.confirmDialog.ConfirmDialogConfig
import routor.src.dialogFactory.confirmDialog.ConfirmDialogFactory
import routor.src.dialogFactory.confirmDialog.ConfirmDialogConfigState
import routor.src.dialogFactory.confirmDialog.ConfirmDialogState
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.isActive
import kotlinx.datetime.Clock
import kotlinx.datetime.TimeZone
import kotlinx.datetime.toLocalDateTime
import routor.src.data.repositories.LocationRepository
import routor.src.data.repositories.RouteRepository
import routor.src.data.types.Route
import routor.src.location.LocationService
import javax.inject.Inject

@HiltViewModel
class MainViewModel @Inject constructor(
    private val locationRepository: LocationRepository,
    private val routeRepository: RouteRepository,
    private val dialogFactory: ConfirmDialogFactory,
    @ApplicationContext private val context: Context,
) : ViewModel() {

    // TODO detach class UI state

    val locationStats = locationRepository.locationStatsFlow
    val currentLocation = locationRepository.currentLocation

    private val _isServiceRecordingRoute = MutableStateFlow(false)
    val isServiceRecordingRoute = _isServiceRecordingRoute.asStateFlow()

    private var currentRoute: MutableState<Route?> = mutableStateOf(null)

    private val minimumNumberOfPoints = 10

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
    private val _centerMapEvent = MutableSharedFlow<Unit>(replay = 0)
    val centerMapEvent = _centerMapEvent.asSharedFlow()

     init {
         viewModelScope.launch {
             if (!_isServiceRecordingRoute.value){
                 sendActionToLocationService(LocationService.ACTION_GET_SINGLE_LOCATION)
                 delay(1000)
                 _centerMapEvent.emit(Unit)
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
                if(!_isServiceRecordingRoute.value){
                    startRecording()
                }
            }
            is MainScreenEvent.SaveRoute -> {
                if(_isServiceRecordingRoute.value){
                    viewModelScope.launch { saveRoute(name = event.name) }
                    stopRecording()
                    _isStopRouteDialogOpen.value = false
                }
            }
            MainScreenEvent.CancelRoute -> {
                if(_isServiceRecordingRoute.value){
                    viewModelScope.launch { cancelRoute() }
                    stopRecording()
                    _isStopRouteDialogOpen.value = false
                }
            }
            MainScreenEvent.CenterMapOnCurrentLocation -> {
                if (!_isServiceRecordingRoute.value){
                    val oldLocation = currentLocation.value
                    sendActionToLocationService(LocationService.ACTION_GET_SINGLE_LOCATION)
                    viewModelScope.launch {
                        currentLocation.first { it != oldLocation}
                        _centerMapEvent.emit(Unit)
                    }
                } else {
                    viewModelScope.launch { _centerMapEvent.emit(Unit) }
                }
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
        if(locationStats.value.numberOfPointsOnRoute < minimumNumberOfPoints){
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
            _isServiceRecordingRoute.value = true
            startTimer()
        }
    }

    private fun stopRecording(){
        sendActionToLocationService(LocationService.ACTION_STOP_RECORDING)
        _isServiceRecordingRoute.value = false
        stopTimer()
        locationRepository.stopRecording()
    }

    private suspend fun cancelRoute() {
        println("route cancelled")
        routeRepository.deleteRoute(currentRoute.value!!)
    }

    private suspend fun saveRoute(name: String){
        //TODO remove print and temp
        println("route stopped")
        println(name)
        routeRepository.updateRoute(currentRoute.value!!.copy(
            name = name,
            numberOfPoints = locationStats.value.numberOfPointsOnRoute,
            duration = _elapsedTime.value,
            distanceKm = locationStats.value.totalDistanceKm,
        ))
    }

    // timer
    private var startTimestamp: Long = 0L
    private val _elapsedTime = MutableStateFlow<Long>(0)
    val elapsedTime: StateFlow<Long> get() = _elapsedTime

    private var timerJob: Job? = null

    private fun startTimer() {
        startTimestamp = SystemClock.elapsedRealtime()

        timerJob?.cancel()
        timerJob = viewModelScope.launch {
            while (isActive) {
                _elapsedTime.value = SystemClock.elapsedRealtime() - startTimestamp
                delay(1000)
            }
        }
    }

    private fun stopTimer() {
        timerJob?.cancel()
        timerJob = null
        _elapsedTime.value = 0
    }
}