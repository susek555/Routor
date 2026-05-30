package routor.src.data.types

import androidx.room.Entity
import androidx.room.PrimaryKey
import kotlinx.datetime.LocalDate
import kotlinx.serialization.Serializable

@Entity(
    tableName = "routes"
)
@Serializable
data class Route(
    @PrimaryKey(autoGenerate = true)
    var id: Long = 0,
    val name: String,
    val numberOfPoints: Int,
    val time: LocalDate
)