package routor.src.network

import android.app.Notification
import io.ktor.client.HttpClient
import io.ktor.client.plugins.websocket.webSocket
import io.ktor.websocket.Frame
import io.ktor.websocket.readText
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.serialization.json.Json

class WebSocketService(
    private val httpClient: HttpClient,
    private val BASE_WS_URL: String
) {
    fun observeNotifications(): Flow<MyNotification> = flow {
        try {
            httpClient.webSocket(BASE_WS_URL) {
                //TODO remove prints
                println(" [WS-Kotlin] Connected to WebSocket successfully!")

                for (frame in incoming) {
                    if (frame is Frame.Text) {
                        val text = frame.readText()
                        println(" [WS-Kotlin] Raw frame received: $text")

                        val notification = Json.decodeFromString<MyNotification>(text)

                        emit(notification)
                    }
                }
            }
        } catch (e: Exception) {
            println(" [WS-Kotlin] Error or Disconnect: ${e.localizedMessage}")
            throw e
        }
    }
}