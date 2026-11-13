package routor.src.network.api

import de.jensklingenberg.ktorfit.http.Body
import de.jensklingenberg.ktorfit.http.GET
import de.jensklingenberg.ktorfit.http.POST
import de.jensklingenberg.ktorfit.http.Path
import routor.src.network.api.types.route.GetVariantsResponse
import routor.src.network.api.types.route.PostGenerateRouteTaskPayload
import routor.src.network.api.types.route.PostGenerateRouteTaskResponse

interface RouteApi {

    @POST("routes/generate")
    suspend fun postGenerateRouteTask(
        @Body payload: PostGenerateRouteTaskPayload
    ) : PostGenerateRouteTaskResponse

    @GET("routes/{task_id}")
    suspend fun getVariants(
        @Path("task_id") taskId: String
    ): GetVariantsResponse
}