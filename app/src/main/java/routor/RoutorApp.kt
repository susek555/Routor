package routor

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.preference.PreferenceManager
import dagger.hilt.android.HiltAndroidApp
import org.osmdroid.config.Configuration

@HiltAndroidApp
class RoutorApp: Application() {
    override fun onCreate() {
        super.onCreate()
        //osm user agent
        Configuration.getInstance().userAgentValue = packageName

        //notifications
        val channel = NotificationChannel(
            "routor",
            "routor",
            NotificationManager.IMPORTANCE_HIGH
        )
        val notificationManager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        notificationManager.createNotificationChannel(channel)
    }
}