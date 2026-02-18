package routor.src.location

import android.location.Location.distanceBetween
import routor.src.data.types.Point

object LocationHelper {
    fun getDistanceMeters(lat1: Double, lon1: Double, lat2: Double, lon2: Double): Float {
        val results = FloatArray(1)
        distanceBetween(lat1, lon1, lat2, lon2, results)
        return results[0]
    }

    fun calculateSpeedKilometers(distanceMeters: Float, timeDiffMillis: Long): Float {
        if (timeDiffMillis <= 0) return 0f
        val speedMetersPerSecond = distanceMeters / (timeDiffMillis / 1000f)
        return speedMetersPerSecond * 3.6f // to km per h
    }
}