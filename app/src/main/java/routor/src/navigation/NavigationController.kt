package routor.src.navigation

import androidx.compose.runtime.Composable
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import routor.src.screens.main.MainScreen
import routor.src.screens.main.MainViewModel
import routor.src.screens.routes.RoutesScreen
import routor.src.screens.routes.RoutesViewModel

@Composable
fun NavigationController(
    startLocationService: () -> Unit,
    stopLocationService: () -> Unit,
) {
    val navController = rememberNavController()

    NavHost(
        navController = navController,
        startDestination = "MainScreen"
    ){
        composable("MainScreen") { backStackEntry ->
            MainScreen(
                viewModel = hiltViewModel<MainViewModel>(backStackEntry),
                startLocationService = startLocationService,
                stopLocationService = stopLocationService,
                displayRoutesScreen = {
                    navController.navigate("RoutesScreen")
                }
            )
        }

        composable("RoutesScreen") { backStackEntry ->
            RoutesScreen(
                viewModel = hiltViewModel<RoutesViewModel>(backStackEntry),
                displayMainScreen = {
                    navController.navigateUp()
                }
            )
        }
    }
}
