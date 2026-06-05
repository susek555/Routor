package routor.src.location

import android.location.Location
import kotlinx.coroutines.flow.Flow

interface LocationClient {
    fun getLocationUpdates(interval: Long): Flow<Location>
    fun getFreshLocation(onLocation: (Location?) -> Unit)

    class LocationException(message: String): Exception()
}