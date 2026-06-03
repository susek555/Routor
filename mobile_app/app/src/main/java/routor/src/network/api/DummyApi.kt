package routor.src.network.api

import de.jensklingenberg.ktorfit.http.POST
import kotlinx.serialization.Serializable

@Serializable
data class TaskResponse(
    val status: String,
    val message: String,
    val task_id : String
)

interface DummyApi {

    @POST("dummy-task")
    suspend fun triggerDummyTask() : TaskResponse
}