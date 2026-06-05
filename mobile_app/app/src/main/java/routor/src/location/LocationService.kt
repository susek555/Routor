package routor.src.location

import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Binder
import android.os.IBinder
import android.widget.Toast
import androidx.core.app.NotificationCompat
import routor.R
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import routor.src.data.repositories.LocationRepository
import routor.src.notifications.RouteFollowerNotificator
import javax.inject.Inject

@AndroidEntryPoint
class LocationService: Service() {

    @Inject lateinit var repository: LocationRepository
    @Inject lateinit var locationClient: LocationClient
    @Inject lateinit var notificator: RouteFollowerNotificator

    private var serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val binder = LocationBinder()

    private var duration = 0L


    inner class LocationBinder: Binder() {
        fun getService(): LocationService = this@LocationService
    }

    override fun onBind(intent: Intent?): IBinder {
        return binder
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when(intent?.action){
            ACTION_START_RECORDING -> start()
            ACTION_STOP_RECORDING -> stop()
            ACTION_GET_SINGLE_LOCATION -> getSingleLocation()
        }
        return super.onStartCommand(intent, flags, startId)
    }

    private fun start() {
        if (serviceScope.isActive.not()) {
            serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
        }

        locationClient
            .getLocationUpdates(2500L)
            .catch {e -> e.printStackTrace() }
            .onEach { location ->
                repository.handleLocationUpdate(location.latitude, location.longitude)
            }
            .launchIn(serviceScope)

        //timer
        serviceScope.launch {
            while (isActive) {
                delay(1000)
                duration++

                repository.updateDuration(duration)

                val currentStats = repository.locationStatsFlow.value
                notificator.update(currentStats, duration)
            }
        }

//        Toast.makeText(this, "Location updates started (inside service)", Toast.LENGTH_SHORT).show()
    }

    private fun stop() {
        serviceScope.cancel()
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()

//        Toast.makeText(this, "Location updates stopped (inside service)", Toast.LENGTH_SHORT).show()
    }

    private fun getSingleLocation() {
        serviceScope.launch {
            locationClient
                .getFreshLocation { location ->
                    if (location != null) {
                        repository.handleSingleLocationUpdate(location.latitude, location.longitude)
                    }
                }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        serviceScope.cancel()
    }

    companion object {
        const val ACTION_START_RECORDING = "ACTION_START_RECORDING"
        const val ACTION_STOP_RECORDING = "ACTION_STOP_RECORDING"
        const val ACTION_GET_SINGLE_LOCATION = "ACTION_GET_SINGLE_LOCATION"
    }
}