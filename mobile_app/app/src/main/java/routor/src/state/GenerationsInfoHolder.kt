package routor.src.state

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class GenerationsInfoHolder @Inject constructor() {
    val usedId: String = "00000000-0000-0000-0000-000000000001"

    private val _taskId = MutableStateFlow<String?>(null)
    val taskId: StateFlow<String?> = _taskId.asStateFlow()

    fun setTaskId(id: String?) {
        _taskId.value = id
    }
}