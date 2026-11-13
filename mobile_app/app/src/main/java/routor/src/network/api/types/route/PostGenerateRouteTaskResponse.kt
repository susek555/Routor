package routor.src.network.api.types.route

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class PostGenerateRouteTaskResponse(
    @SerialName("task_id")
    val taskId: String
)
