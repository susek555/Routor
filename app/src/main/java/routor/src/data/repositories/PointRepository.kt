package routor.src.data.repositories

import routor.src.data.database.PointsDao
import routor.src.data.types.Point
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class PointRepository @Inject constructor(
    private val pointsDao: PointsDao
) {
    suspend fun addPointToDatabase(point: Point) {
        //TODO remove print
        println("route : point added")
        pointsDao.upsertPoint(point)
    }
}