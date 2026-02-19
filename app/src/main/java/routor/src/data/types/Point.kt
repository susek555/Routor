package routor.src.data.types

import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.PrimaryKey
import kotlinx.serialization.Serializable

@Entity(
    tableName = "points",
    foreignKeys = [
        ForeignKey(
            entity = Route::class,
            parentColumns = ["id"],
            childColumns = ["routeId"],
            onDelete = ForeignKey.CASCADE
        )
    ]
)
@Serializable
data class Point(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    val routeId: Long,
    val latitude: Double,
    val longitude: Double,
    val time: Int,
    val speedKm: Float,
    val distanceFromLastKm: Float
)