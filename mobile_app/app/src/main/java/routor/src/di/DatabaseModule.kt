package routor.src.di

import android.content.Context
import androidx.room.Room
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import routor.src.data.database.PointsDao
import routor.src.data.database.RoutesDao
import routor.src.data.database.RoutesDatabase
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object DatabaseModule {

    @Provides
    @Singleton
    fun provideDatabase(@ApplicationContext context: Context): RoutesDatabase {
        return Room.databaseBuilder(
            context,
            RoutesDatabase::class.java,
            "routes_database"
        )
            .fallbackToDestructiveMigration(false) //TODO change it
            .build()
    }

    @Provides
    fun providePointsDao(database: RoutesDatabase): PointsDao {
        return database.pointsDao()
    }

    @Provides
    fun provideRoutesDao(database: RoutesDatabase): RoutesDao {
        return database.routesDao()
    }
}