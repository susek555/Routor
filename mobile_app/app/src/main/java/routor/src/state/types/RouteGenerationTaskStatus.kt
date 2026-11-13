package routor.src.state.types

import kotlinx.serialization.DeserializationStrategy
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonContentPolymorphicSerializer
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.jsonObject

@Serializable
enum class RouteGenerationTaskStatusEnum {
    LOADING_GRAPH,
    SIMPLIFYING_GRAPH,
    GENERATING_ROUTE,
    COMPLETED,
    FAILED
}

@Serializable(with = RouteGenerationTaskStatusPayloadSerializer::class)
sealed interface RouteGenerationTaskStatusPayload

@Serializable
data class FailedRouteGenerationTaskStatus(
    @SerialName("error_message")
    val errorMessage: String
) : RouteGenerationTaskStatusPayload

@Serializable
data class ProgressRouteGenerationTaskStatus(
    val done: Int,
    val total: Int
) : RouteGenerationTaskStatusPayload

@Serializable
data class RouteGenerationTaskStatus(
    val state: RouteGenerationTaskStatusEnum,
    val payload: RouteGenerationTaskStatusPayload? = null
)

object RouteGenerationTaskStatusPayloadSerializer :
    JsonContentPolymorphicSerializer<RouteGenerationTaskStatusPayload>(
        RouteGenerationTaskStatusPayload::class
    ) {
    override fun selectDeserializer(element: JsonElement): DeserializationStrategy<RouteGenerationTaskStatusPayload> {
        val jsonObject = element.jsonObject
        return when {
            "error_message" in jsonObject -> FailedRouteGenerationTaskStatus.serializer()
            "done" in jsonObject -> ProgressRouteGenerationTaskStatus.serializer()
            else -> throw IllegalArgumentException("Unknown payload structure: $jsonObject")
        }
    }
}