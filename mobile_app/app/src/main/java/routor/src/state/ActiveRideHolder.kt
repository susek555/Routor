package routor.src.state

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import routor.src.state.types.FollowedRoute
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class ActiveRideHolder @Inject constructor() {
    private val _followedRoute = MutableStateFlow<FollowedRoute?>(null)
    val followedRoute: StateFlow<FollowedRoute?> = _followedRoute.asStateFlow()

    private val _isRecording = MutableStateFlow(false)
    val isRecording: StateFlow<Boolean> = _isRecording.asStateFlow()

    fun setFollowedRoute(route: FollowedRoute?) {
        _followedRoute.value = route
    }

    fun setRecording(recording: Boolean) {
        _isRecording.value = recording
    }
}