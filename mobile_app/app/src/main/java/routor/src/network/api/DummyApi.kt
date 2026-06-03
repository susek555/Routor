package routor.src.network.api

import de.jensklingenberg.ktorfit.http.Body
import de.jensklingenberg.ktorfit.http.POST
import kotlinx.serialization.Serializable

@Serializable
data class TaskResponse(
    val status: String,
    val message: String,
    val task_id : String
)

@Serializable
data class TaskPayload(
    val fcm_token: String
)

interface DummyApi {

    @POST("dummy-task")
    suspend fun triggerDummyTask(@Body payload: TaskPayload) : TaskResponse
}