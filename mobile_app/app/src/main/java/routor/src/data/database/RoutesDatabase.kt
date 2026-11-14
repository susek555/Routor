package routor.src.data.database

import androidx.room.Database
import androidx.room.RoomDatabase
import androidx.room.TypeConverters
import routor.src.data.database.converters.LatLngListConverter
import routor.src.data.database.converters.LocalDateConverter
import routor.src.data.types.PlannedRoute
import routor.src.data.types.Point
import routor.src.data.types.Route

@Database(
    entities = [Route::class, Point::class, PlannedRoute::class],
    version = 4
)
@TypeConverters(
    LocalDateConverter::class,
    LatLngListConverter::class
)
abstract class RoutesDatabase: RoomDatabase() {

    abstract fun routesDao(): RoutesDao
    abstract fun pointsDao(): PointsDao
    abstract fun plannedRoutesDao(): PlannedRoutesDao
}

