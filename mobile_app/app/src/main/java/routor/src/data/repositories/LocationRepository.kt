package routor.src.data.repositories

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import org.maplibre.android.geometry.LatLng
import routor.src.data.types.Point
import javax.inject.Inject
import javax.inject.Singleton
import routor.src.data.types.RouteStats
import routor.src.utils.LocationStatsHelper

@Singleton
class LocationRepository @Inject constructor(
    private val pointRepository: PointRepository
) {
    private val repoScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    private var currentRouteId: Long? = null
    private var recordingStartTime: Long? = null
    private var points: List<LatLng> = emptyList()
    private var numberOfPointsOnRoute: Int = 0

    private val _routeStatsFlow = MutableStateFlow(RouteStats())
    val routeStatsFlow = _routeStatsFlow.asStateFlow()
    private val _currentLocation = MutableStateFlow<LatLng?>(null)
    val currentLocation = _currentLocation.asStateFlow()
    private val _duration = MutableStateFlow(0L)
    val duration = _duration.asStateFlow()

    fun updateDuration(seconds: Long) {
        _duration.value = seconds
    }

    //recording control
    fun startRecording(routeId: Long) {
        currentRouteId = routeId
        recordingStartTime = System.currentTimeMillis()
        totalDistanceKilometers = 0f
        lastPoint = null
        numberOfPointsOnRoute = 0
    }

    fun stopRecording() {
        currentRouteId = null
        recordingStartTime = null
        points = emptyList()
        _routeStatsFlow.value = RouteStats()
    }

    private var totalDistanceKilometers: Float = 0f
    private var lastPoint: Triple<Double, Double, Long>? = null

    @Synchronized
    fun handleSingleLocationUpdate(latitude: Double, longitude: Double) {
        //TODO remove prints
        println("point received")
        println("lat: $latitude  lon: $longitude")
        _currentLocation.value = LatLng(latitude, longitude)
    }

    @Synchronized
    fun handleLocationUpdate(latitude: Double, longitude: Double) {
        _currentLocation.value = LatLng(latitude, longitude)
        points += _currentLocation.value!!
        var distanceMeters: Float = 0f
        var speedKilometers: Float = 0f
        val currentTimeMillis = System.currentTimeMillis()

        lastPoint?.let { last ->
            distanceMeters = LocationStatsHelper.getDistanceMeters(
                last.first, last.second, latitude, longitude
            )

            // TODO check detect stop condition
            if (distanceMeters < 3.0f) return

            speedKilometers = LocationStatsHelper.calculateSpeedKilometers(
                distanceMeters, currentTimeMillis - last.third
            )
            totalDistanceKilometers += distanceMeters / 1000f
        }

        numberOfPointsOnRoute += 1
        val stats = RouteStats(points, speedKilometers, totalDistanceKilometers, numberOfPointsOnRoute)
        _routeStatsFlow.value = stats

        lastPoint = Triple(latitude, longitude, currentTimeMillis)

        currentRouteId?.let { routeId ->
            val start = recordingStartTime ?: return@let

            repoScope.launch {
                pointRepository.addPointToDatabase(
                    Point(
                        routeId = routeId,
                        latitude = latitude,
                        longitude = longitude,
                        time = (currentTimeMillis - start).toInt(),
                        speedKm = speedKilometers,
                        distanceFromLastKm = distanceMeters / 1000
                    )
                )
            }
        }
    }
}