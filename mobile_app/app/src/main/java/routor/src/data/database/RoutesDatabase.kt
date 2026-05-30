package routor.src.data.database

import androidx.room.Database
import androidx.room.RoomDatabase
import androidx.room.TypeConverters
import routor.src.data.types.Point
import routor.src.data.types.Route

@Database(
    entities = [Route::class, Point::class],
    version = 1
)
@TypeConverters(
    Converters::class
)
abstract class RoutesDatabase: RoomDatabase() {

    abstract fun routesDao(): RoutesDao
    abstract fun pointsDao(): PointsDao
}

