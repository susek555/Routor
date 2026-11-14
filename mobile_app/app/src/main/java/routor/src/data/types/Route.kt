package routor.src.data.types

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey
import kotlinx.datetime.LocalDate
import kotlinx.serialization.Serializable

@Entity(
    tableName = "routes",
    foreignKeys = [
        ForeignKey(
            entity = PlannedRoute::class,
            parentColumns = ["id"],
            childColumns = ["planned_route_id"],
            onDelete = ForeignKey.SET_NULL
        )
    ],
    indices = [Index(value = ["planned_route_id"])]
)
@Serializable
data class Route(
    @PrimaryKey(autoGenerate = true)
    var id: Long = 0,
    val name: String,
    val numberOfPoints: Int,
    val date: LocalDate,
    val duration: Long,
    val distanceKm: Float,
    @ColumnInfo(name = "planned_route_id")
    val plannedRouteId: Long? = null
)