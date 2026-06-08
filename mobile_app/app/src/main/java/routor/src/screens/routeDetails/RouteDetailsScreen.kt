package routor.src.screens.routeDetails

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import routor.src.dialogFactory.confirmDialog.ConfirmDialog
import routor.src.utils.MapHelper
import routor.src.utils.formatTime

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RouteDetailsScreen(
    displayRoutesScreen: () -> Unit,
    viewModel: RouteDetailsViewModel
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val routeDialogState by viewModel.routeDialogState.collectAsStateWithLifecycle()

    LaunchedEffect(viewModel.routeDeletedEvent) {
        viewModel.routeDeletedEvent.collect {
            displayRoutesScreen()
        }
    }

    //map
    val context = LocalContext.current
    val mapView = remember {
        MapHelper.getRouteScreenMapView(context)
    }
    MapHelper.SetupMapLifecycleEvents(mapView)

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    if (uiState is RouteDetailsUiState.Success) {
                        Text(
                            text = (uiState as RouteDetailsUiState.Success).route.name,
                            style = TextStyle(fontSize = 20.sp, fontWeight = FontWeight.Bold)
                        )
                    } else {
                        Text(text = "Route Details")
                    }
                },
                navigationIcon = {
                    IconButton(onClick = displayRoutesScreen) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "Back"
                        )
                    }
                },
                actions = {
                    if (uiState is RouteDetailsUiState.Success) {
                        IconButton(onClick = { viewModel.onEvent(RouteDetailsEvent.ShowEditRouteDialog) }) {
                            Icon(
                                imageVector = Icons.Default.Edit,
                                contentDescription = "Edit"
                            )
                        }
                        IconButton(onClick = { viewModel.onEvent(RouteDetailsEvent.ShowDeleteRouteDialog) }) {
                            Icon(
                                imageVector = Icons.Default.Delete,
                                contentDescription = "Delete"
                            )
                        }
                    }
                }
            )
        }
    ) { innerPadding ->

        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
        ) {
            when (val currentState = uiState) {
                RouteDetailsUiState.Loading -> {
                }
                RouteDetailsUiState.Error -> {
                    Text("Route not found")
                }
                is RouteDetailsUiState.Success -> {
                    MapHelper.displayFullRoute(mapView, currentState.points)

                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                    ) {
                        Box(
                            modifier = Modifier
                                .fillMaxSize()
                                .weight(3f),
                        ) {
                            AndroidView(
                                factory = { mapView },
                                update = {}
                            )
                        }
                        Spacer(
                            modifier = Modifier
                                .padding(5.dp)
                        )
                        Box(
                            modifier = Modifier
                                .fillMaxSize()
                                .weight(2f)
                                .padding(20.dp)
                        ) {
                            Column(
                                modifier = Modifier.fillMaxSize(),
                                horizontalAlignment = Alignment.CenterHorizontally,
                                verticalArrangement = Arrangement.SpaceBetween
                            ) {
                                //stats
                                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                    Text(
                                        text = "STATS",
                                        style = TextStyle(fontWeight = FontWeight.Light, fontSize = 12.sp)
                                    )

                                    Spacer(modifier = Modifier.height(16.dp))

                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.SpaceEvenly
                                    ) {
                                        StatItem(
                                            label = "DISTANCE",
                                            value = "${"%.2f".format(currentState.route.distanceKm)} km"
                                        )
                                        StatItem(
                                            label = "AVERAGE SPEED",
                                            value = "${"%.2f".format(currentState.route.distanceKm / (currentState.route.duration * 60 * 60))} km/h"
                                        )
                                        StatItem(label = "DURATION", value = formatTime(currentState.route.duration))
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    if (routeDialogState.isVisible && routeDialogState.config != null) {
        ConfirmDialog(routeDialogState.config!!)
    }
}

@Composable
private fun StatItem(label: String, value: String) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(text = label, style = TextStyle(fontSize = 10.sp, fontWeight = FontWeight.Bold))
        Text(text = value, style = TextStyle(fontSize = 18.sp, fontWeight = FontWeight.ExtraBold))
    }
}