package routor.src.data.repositories

import routor.src.network.api.DummyApi
import routor.src.network.api.TaskResponse
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class GenerationsRepository @Inject constructor(
    private val generationsApi: DummyApi
){

    suspend fun triggerDummyTask() : TaskResponse {
        return generationsApi.triggerDummyTask()
    }
}