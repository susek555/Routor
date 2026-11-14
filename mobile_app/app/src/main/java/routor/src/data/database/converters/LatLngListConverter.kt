package routor.src.data.database.converters

import androidx.room.TypeConverter
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import org.maplibre.android.geometry.LatLng

@Serializable
private data class LatLngDto(val lat: Double, val lon: Double)

class LatLngListConverter {
    @TypeConverter
    fun fromLatLngList(points: List<LatLng>): String {
        val dtoList = points.map { LatLngDto(it.latitude, it.longitude) }
        return Json.encodeToString(dtoList)
    }

    @TypeConverter
    fun toLatLngList(data: String): List<LatLng> {
        if (data.isBlank()) return emptyList()
        return Json.decodeFromString<List<LatLngDto>>(data)
            .map { LatLng(it.lat, it.lon) }
    }
}