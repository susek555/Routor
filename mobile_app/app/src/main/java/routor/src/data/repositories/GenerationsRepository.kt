package routor.src.data.repositories

import android.app.Notification
import kotlinx.coroutines.flow.Flow
import routor.src.network.MyNotification
import routor.src.network.WebSocketService
import routor.src.network.api.DummyApi
import routor.src.network.api.TaskResponse
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class GenerationsRepository @Inject constructor(
    private val generationsApi: DummyApi,
    private val webSocketService: WebSocketService
){

    suspend fun triggerDummyTask() : TaskResponse {
        return generationsApi.triggerDummyTask()
    }

    fun listenToRouteUpdates(): Flow<MyNotification> {
        return webSocketService.observeNotifications()
    }
}