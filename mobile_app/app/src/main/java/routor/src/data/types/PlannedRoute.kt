package routor.src.data.types

import androidx.room.Entity
import androidx.room.PrimaryKey
import org.maplibre.android.geometry.LatLng

@Entity(
    tableName = "planned_routes"
)
data class PlannedRoute(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    val targetDistanceMeters: Double,
    val points: List<LatLng>
)