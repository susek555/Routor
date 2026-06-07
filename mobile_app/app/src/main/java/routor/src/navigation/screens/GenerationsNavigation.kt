package routor.src.navigation.screens

import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import androidx.navigation.NavGraphBuilder
import androidx.navigation.compose.composable
import kotlinx.serialization.Serializable
import routor.src.screens.generations.GenerateScreen
import routor.src.screens.generations.GenerationsViewModel

@Serializable
object GenerationsNavRoute

fun NavController.navigateToGenerations() {
    navigate(GenerationsNavRoute)
}

fun NavGraphBuilder.generationsScreen(
    onNavigateToMain: () -> Unit
) {
    composable<GenerationsNavRoute> { backStackEntry ->
        GenerateScreen(
            viewModel = hiltViewModel<GenerationsViewModel>(backStackEntry),
            displayMainScreen = {
                onNavigateToMain()
            }
        )
    }
}