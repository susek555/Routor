package routor.src.data.database

import androidx.room.Dao
import androidx.room.Query
import androidx.room.Upsert
import kotlinx.coroutines.flow.Flow
import routor.src.data.types.Point

@Dao
interface PointsDao {
    @Upsert
    suspend fun upsertPoint(point: Point)

    @Query("SELECT * FROM points WHERE routeId = :selectedRoute")
    fun getPointsForRoute(selectedRoute: Long): Flow<List<Point>>
}