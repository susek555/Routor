package routor.src.data.database

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.Query
import routor.src.data.types.PlannedRoute

@Dao
interface PlannedRoutesDao {
    @Insert
    suspend fun insertRoute(route: PlannedRoute) : Long

    @Query("SELECT * FROM planned_routes WHERE id = :routeId")
    fun getRoute(routeId: Long) : PlannedRoute?
}