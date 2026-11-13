package routor.src.data.repositories

import com.google.firebase.messaging.FirebaseMessaging
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.tasks.await
import org.maplibre.android.geometry.LatLng
import routor.src.network.WebSocketService
import routor.src.network.api.RouteApi
import routor.src.network.api.types.route.GetVariantsResponse
import routor.src.network.api.types.route.PostGenerateRouteTaskPayload
import routor.src.network.api.types.route.PostGenerateRouteTaskResponse
import routor.src.network.api.types.route.RouteGenerationTaskStatus
import routor.src.state.GenerationsInfoHolder
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class GenerationsRepository @Inject constructor(
    private val routeApi: RouteApi,
    private val webSocketService: WebSocketService,
    private val generationsInfoHolder: GenerationsInfoHolder
) {
    //TODO prints to logs

    suspend fun startRouteGeneration(
        center: LatLng,
        targetDistanceMeters: Float
    ): String {
        val fcmToken = runCatching {
            FirebaseMessaging.getInstance().token.await()
        }.getOrElse { e ->
            println("Warning: Could not fetch FCM token (${e.localizedMessage}), using empty fallback")
            ""
        }

        val payload = PostGenerateRouteTaskPayload(
            fcmToken = fcmToken,
            userId = generationsInfoHolder.usedId,
            center = center,
            targetDistance = targetDistanceMeters
        )

        val response: PostGenerateRouteTaskResponse = routeApi.postGenerateRouteTask(payload)
        println("API created route generation task: ${response.taskId}")
        return response.taskId
    }

    fun observeTaskProgress(taskId: String): Flow<RouteGenerationTaskStatus> {
        return webSocketService.observeRouteGeneration(taskId)
    }

    suspend fun getRouteVariants(taskId: String): List<GetVariantsResponse.RouteVariantDto> {
        val response = routeApi.getVariants(taskId)
        return response.variants.sortedBy { it.variantIndex }
    }
}