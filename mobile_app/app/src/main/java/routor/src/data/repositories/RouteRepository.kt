package routor.src.data.repositories

import kotlinx.coroutines.flow.Flow
import routor.src.data.database.RoutesDao
import routor.src.data.types.Route
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class RouteRepository @Inject constructor(
    private val routesDao: RoutesDao
) {
    suspend fun insertRoute(route: Route): Long {
        return routesDao.insertRoute(route)
    }

    suspend fun updateRoute(route: Route){
        routesDao.updateRoute(route)
    }

    suspend fun deleteRoute(route: Route){
        routesDao.deleteRoute(route)
    }

    fun getRoute(routeId: Long) : Flow<Route?> {
        return routesDao.getRoute(routeId)
    }

    suspend fun getAllRoutes(): List<Route> {
        return routesDao.getAllRoutes()
    }
}