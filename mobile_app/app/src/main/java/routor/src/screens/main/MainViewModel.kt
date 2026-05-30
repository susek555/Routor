package routor.src.screens.main

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
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.isActive
import kotlinx.datetime.Clock
import kotlinx.datetime.TimeZone
import kotlinx.datetime.toLocalDateTime
import routor.src.data.repositories.LocationRepository
import routor.src.data.repositories.PointRepository
import routor.src.data.repositories.RouteRepository
import routor.src.data.types.Point
import routor.src.data.types.Route
import routor.src.location.LocationStats
import javax.inject.Inject

@HiltViewModel
class MainViewModel @Inject constructor(
    private val locationRepository: LocationRepository,
    private val routeRepository: RouteRepository,
    private val dialogFactory: ConfirmDialogFactory
) : ViewModel() {

    val locationStats = locationRepository.locationStatsFlow

    private val _isLocationServiceOn = MutableStateFlow<Boolean>(false)
    val isLocationServiceOn: StateFlow<Boolean> get() = _isLocationServiceOn

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
                startRecording()
            }
            is MainScreenEvent.SaveRoute -> {
                viewModelScope.launch { saveRoute(name = event.name) }
                stopRecording()
                _isStopRouteDialogOpen.value = false
            }
            MainScreenEvent.CancelRoute -> {
                viewModelScope.launch { cancelRoute() }
                stopRecording()
                _isStopRouteDialogOpen.value = false
            }
        }
    }

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

    private fun startRecording(){
        //TODO remove prints
        println("new route started")
        //prepare route
        viewModelScope.launch {
            val localDate = Clock.System.now()
                .toLocalDateTime(TimeZone.currentSystemDefault())
                .date

            val newRoute = Route(name = "", numberOfPoints = 0, time = localDate)

            // wait for ID
            val routeId = routeRepository.insertRoute(newRoute)
            currentRoute.value = newRoute.copy(id = routeId)

            locationRepository.startRecording(routeId)
            _isLocationServiceOn.value = true
            startTimer()
        }
    }

    private fun stopRecording(){
        _isLocationServiceOn.value = false
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
        routeRepository.updateRoute(currentRoute.value!!.copy(name = name, numberOfPoints = locationStats.value.numberOfPointsOnRoute))
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