package routor.src.data.repositories

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import routor.src.data.types.Point
import javax.inject.Inject
import javax.inject.Singleton
import routor.src.location.LocationStats
import routor.src.location.LocationHelper

@Singleton
class LocationRepository @Inject constructor(
    private val pointRepository: PointRepository
) {
    private val repoScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    private var currentRouteId: Long? = null
    private var recordingStartTime: Long? = null
    private var numberOfPointsOnRoute: Int = 0

    private val _locationStatsFlow = MutableStateFlow(LocationStats())
    val locationStatsFlow = _locationStatsFlow.asStateFlow()

    //recording control
    fun startRecording(routeId: Long) {
        currentRouteId = routeId
        recordingStartTime = System.currentTimeMillis()
        totalDistanceKilometers = 0f
        lastPoint = null
    }

    fun stopRecording() {
        currentRouteId = null
        recordingStartTime = null
        numberOfPointsOnRoute = 0
    }

    private var totalDistanceKilometers: Float = 0f
    private var lastPoint: Triple<Double, Double, Long>? = null

    @Synchronized
    fun handleLocationUpdate(latitude: Double, longitude: Double) {
        var distanceMeters: Float = 0f
        var speedKilometers: Float = 0f
        val currentTimeMillis = System.currentTimeMillis()

        lastPoint?.let { last ->
            distanceMeters = LocationHelper.getDistanceMeters(
                last.first, last.second, latitude, longitude
            )

            // TODO check detect stop condition
            if (distanceMeters < 1.0f) return

            speedKilometers = LocationHelper.calculateSpeedKilometers(
                distanceMeters, currentTimeMillis - last.third
            )
            totalDistanceKilometers += distanceMeters / 1000f
        }

        numberOfPointsOnRoute += 1
        val stats = LocationStats(latitude, longitude, speedKilometers, totalDistanceKilometers, numberOfPointsOnRoute)
        _locationStatsFlow.value = stats

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