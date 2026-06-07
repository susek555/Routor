package routor.src.screens.routeDetails

import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import routor.src.dialogFactory.confirmDialog.ConfirmDialog

@Composable
fun RouteDetailsScreen(
    displayRoutesScreen: () -> Unit,
    viewModel: RouteDetailsViewModel
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    LaunchedEffect(viewModel.routeDeletedEvent) {
        viewModel.routeDeletedEvent.collect {
            displayRoutesScreen()
        }
    }

    // TODO

    when (val currentState = uiState) {
        RouteDetailsUiState.Loading -> {
        }
        RouteDetailsUiState.Error -> {
            Text("Route not found")
        }
        is RouteDetailsUiState.Success -> {
            Text(text = "Route name: ${currentState.route.name}")
        }
    }


//    if(routeDialogState.isVisible){
//        ConfirmDialog(routeDialogState.config!!)
//    }
}