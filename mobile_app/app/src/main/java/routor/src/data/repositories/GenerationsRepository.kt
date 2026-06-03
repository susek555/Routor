package routor.src.data.repositories

import kotlinx.coroutines.tasks.await
import com.google.firebase.messaging.FirebaseMessaging
import kotlinx.coroutines.flow.Flow
import routor.src.network.MyNotification
import routor.src.network.WebSocketService
import routor.src.network.api.DummyApi
import routor.src.network.api.TaskPayload
import routor.src.network.api.TaskResponse
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class GenerationsRepository @Inject constructor(
    private val generationsApi: DummyApi,
    private val webSocketService: WebSocketService
){

    suspend fun triggerDummyTask() : TaskResponse {
        return try {
            val fcmToken = FirebaseMessaging.getInstance().token.await()
            // TODO remove prints
            println("Downloaded device token: $fcmToken")

            // TODO connect token handling to userId (maybe)
            val payload = TaskPayload(
                fcm_token = fcmToken
            )

            val response = generationsApi.triggerDummyTask(payload)
            println("API received task: ${response.status}")

            response
        } catch (e: Exception) {
            println("Error during fetching token or API call: ${e.localizedMessage}")
            throw e
        }
    }

    fun listenToRouteUpdates(): Flow<MyNotification> {
        return webSocketService.observeNotifications()
    }
}