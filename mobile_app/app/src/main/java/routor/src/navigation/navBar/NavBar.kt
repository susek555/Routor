package routor.src.navigation.navBar

import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavDestination

@Composable
fun NavBar(
    currentDestination: NavDestination?,
    onTabSelected: (Destinations) -> Unit,
    viewModel: NavBarViewModel = hiltViewModel()
) {
    if (!Destinations.isTopLevel(currentDestination)) return

    val isRecording by viewModel.isRecording.collectAsStateWithLifecycle()

    NavigationBar {
        Destinations.entries.forEach { tab ->
            val selected = tab.matches(currentDestination)
            NavigationBarItem(
                selected = selected,
                enabled = !isRecording || selected,
                onClick = {
                    if (!selected && !isRecording) {
                        onTabSelected(tab)
                    }
                },
                icon = { Icon(imageVector = tab.icon, contentDescription = tab.label) },
                label = { Text(text = tab.label) }
            )
        }
    }
}