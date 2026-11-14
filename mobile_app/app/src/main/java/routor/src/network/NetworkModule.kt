package routor.src.network

import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import de.jensklingenberg.ktorfit.Ktorfit
import io.ktor.client.HttpClient
import io.ktor.client.engine.cio.CIO
import io.ktor.client.plugins.HttpTimeout
import io.ktor.client.plugins.cache.HttpCache
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.plugins.defaultRequest
import io.ktor.client.plugins.websocket.WebSockets
import io.ktor.http.ContentType
import io.ktor.http.contentType
import io.ktor.serialization.kotlinx.json.json
import kotlinx.serialization.json.Json
import routor.src.network.api.RouteApi
import routor.src.network.api.createRouteApi
import javax.inject.Singleton


@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {
    // TODO move it to config file
    private const val BASE_URL = "prepare-observations-elizabeth-indices.trycloudflare.com"
    private const val BASE_HTTPS_URL = "https://$BASE_URL/"
    private const val BASE_WS_URL = "ws://$BASE_URL/"

    @Provides
    @Singleton
    fun provideHttpClient(): HttpClient {
        return HttpClient(CIO) {
            install(ContentNegotiation) {
                json(Json {
                    prettyPrint = true
                    ignoreUnknownKeys = true
                })
            }
            defaultRequest {
                contentType(ContentType.Application.Json)
            }
            install(HttpTimeout) {
                requestTimeoutMillis = 3000
            }
            install(HttpCache)
            install(WebSockets)
        }
    }

    @Provides
    @Singleton
    fun provideKtorfit(httpClient: HttpClient): Ktorfit {
        return Ktorfit.Builder()
            .baseUrl(BASE_HTTPS_URL)
            .httpClient(httpClient)
            .build()
    }

    @Provides
    @Singleton
    fun provideWebSocketService(): WebSocketService {
        return WebSocketService(
            httpClient = provideHttpClient(),
            baseUrl = BASE_WS_URL
        )
    }

    @Provides
    @Singleton
    fun provideRouteApi(ktorfit: Ktorfit): RouteApi {
        return ktorfit.createRouteApi()
    }
}