package routor.src.data.repositories

import routor.src.data.database.PlannedRoutesDao
import routor.src.data.types.PlannedRoute
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class PlannedRoutesRepository @Inject constructor(
    private val plannedRoutesDao: PlannedRoutesDao
) {
    suspend fun insertRoute(route: PlannedRoute): Long{
        return plannedRoutesDao.insertRoute(route)
    }

    fun getRoute(id: Long): PlannedRoute? {
        return plannedRoutesDao.getRoute(id)
    }
}