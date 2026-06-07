package routor.src.navigation.screens

import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import androidx.navigation.NavGraphBuilder
import androidx.navigation.compose.composable
import kotlinx.serialization.Serializable
import routor.src.screens.main.MainScreen
import routor.src.screens.main.MainViewModel

@Serializable
object MainNavRoute

fun NavController.navigateToMain() {
    navigate(MainNavRoute)
}

fun NavGraphBuilder.mainScreen(
    onNavigateToRoutes: () -> Unit,
    onNavigateToGenerations: () -> Unit
) {
    composable<MainNavRoute> { backStackEntry ->
        MainScreen(
            viewModel = hiltViewModel<MainViewModel>(backStackEntry),
            displayRoutesScreen = onNavigateToRoutes,
            displayGenerationsScreen = onNavigateToGenerations
        )
    }
}