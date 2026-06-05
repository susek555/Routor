package routor.src.notifications;

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import androidx.core.app.NotificationCompat
import dagger.hilt.android.qualifiers.ApplicationContext
import routor.R
import routor.src.data.types.RouteStats
import javax.inject.Inject;
import javax.inject.Singleton;

@Singleton
class RouteFollowerNotificator @Inject constructor(
    @ApplicationContext context: Context
) {
    private val appContext = context.applicationContext
    private val NOTIFICATION_ID = 1
    private val CHANNEL_ID = "routor"

    private val notificationBuilder = NotificationCompat.Builder(appContext, CHANNEL_ID)
        .setContentTitle("Tracking route...")
        .setContentText("Stats: null")
        // TODO ikonka
        .setSmallIcon(R.drawable.ic_launcher_background)
        .setOngoing(true)
        .setPriority(NotificationCompat.PRIORITY_HIGH)
        .setOnlyAlertOnce(true)

    private val notificationManager = appContext.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

    init {
        //notifications
        val channel = NotificationChannel(
            "routor",
            "routor",
            NotificationManager.IMPORTANCE_HIGH
        )

        notificationManager.createNotificationChannel(channel)
    }

    fun update(routeStats: RouteStats, duration: Long) {
        val updatedNotification = notificationBuilder
            .setContentText("Duration : $duration s, Speed: ${routeStats.speedKmh} km/h, Distance: ${routeStats.totalDistanceKm} km")
            .build()

        notificationManager.notify(NOTIFICATION_ID, updatedNotification)
    }

    fun dismiss() {
        notificationManager.cancel(NOTIFICATION_ID)
    }
}