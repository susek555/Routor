package routor.src.navigation.navBar

import androidx.lifecycle.ViewModel
import dagger.hilt.android.lifecycle.HiltViewModel
import routor.src.state.ActiveRideHolder
import javax.inject.Inject

@HiltViewModel
class NavBarViewModel @Inject constructor(
    activeRideHolder: ActiveRideHolder
) : ViewModel() {
    val isRecording = activeRideHolder.isRecording
}