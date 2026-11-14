package routor.src.network

import io.ktor.client.HttpClient
import io.ktor.client.plugins.websocket.webSocket
import io.ktor.websocket.CloseReason
import io.ktor.websocket.Frame
import io.ktor.websocket.close
import io.ktor.websocket.readText
import kotlinx.coroutines.channels.ClosedReceiveChannelException
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.serialization.json.Json
import routor.src.network.api.types.route.RouteGenerationTaskStatus
import routor.src.network.api.types.route.RouteGenerationTaskStatusEnum

class WebSocketService(
    private val httpClient: HttpClient,
    private val baseUrl: String
) {
    private val json = Json {
        ignoreUnknownKeys = true
        isLenient = true
    }

    //TODO prints to logs

    fun observeRouteGeneration(taskId: String): Flow<RouteGenerationTaskStatus> = flow {
        val url = "${baseUrl}routes/ws/$taskId"

        try {
            httpClient.webSocket(urlString = url) {
                println("[WS-Kotlin] Connected to $url")

                for (frame in incoming) {
                    if (frame is Frame.Text) {
                        val text = frame.readText()
                        println("[WS-Kotlin] Raw frame received: $text")

                        val status = json.decodeFromString<RouteGenerationTaskStatus>(text)
                        emit(status)

                        if (status.state == RouteGenerationTaskStatusEnum.COMPLETED ||
                            status.state == RouteGenerationTaskStatusEnum.FAILED
                        ) {
                            send(Frame.Text("ACK"))
                            close(CloseReason(CloseReason.Codes.NORMAL, "Terminal state received"))
                            break
                        }
                    }
                }
            }
        } catch (_: ClosedReceiveChannelException) {
            println("[WS-Kotlin] Channel closed normally by server")
        } catch (e: Exception) {
            println("[WS-Kotlin] Error or Disconnect: ${e.localizedMessage}")
            throw e
        }
    }
}