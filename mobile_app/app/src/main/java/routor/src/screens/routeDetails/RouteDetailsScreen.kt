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
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import org.maplibre.android.geometry.LatLng
import routor.src.dialogFactory.confirmDialog.ConfirmDialog
import routor.src.utils.MapHelper
import routor.src.utils.formatTime
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RouteDetailsScreen(
    displayRoutesScreen: () -> Unit,
    displayMainScreen: () -> Unit,
    viewModel: RouteDetailsViewModel
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val routeDialogState by viewModel.routeDialogState.collectAsStateWithLifecycle()

    LaunchedEffect(viewModel.routeDeletedEvent) {
        viewModel.routeDeletedEvent.collect {
            displayRoutesScreen()
        }
    }

    LaunchedEffect(viewModel.navigateToMainEvent) {
        viewModel.navigateToMainEvent.collect {
            displayMainScreen()
        }
    }

    // Map
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
                    CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
                }

                RouteDetailsUiState.Error -> {
                    Text(
                        text = "Route not found",
                        modifier = Modifier.align(Alignment.Center)
                    )
                }

                is RouteDetailsUiState.Success -> {
                    LaunchedEffect(currentState.points, currentState.plannedRoute) {
                        val plannedPoints = currentState.plannedRoute?.points.orEmpty()
                        MapHelper.displayPlannedRoute(mapView, plannedPoints)
                        MapHelper.displayFullRoute(mapView, currentState.points)

                        val boundsPoints = currentState.points.map { LatLng(it.latitude, it.longitude) } + plannedPoints
                        MapHelper.zoomToRoute(mapView, boundsPoints, paddingPx = 200)
                    }

                    val avgSpeedKmh = if (currentState.route.duration > 0) {
                        currentState.route.distanceKm / (currentState.route.duration / 3600.0)
                    } else {
                        0.0
                    }

                    Column(
                        modifier = Modifier.fillMaxSize()
                    ) {
                        Box(
                            modifier = Modifier
                                .fillMaxSize()
                                .weight(3f)
                        ) {
                            AndroidView(
                                factory = { mapView },
                                update = {}
                            )
                        }

                        Spacer(modifier = Modifier.height(5.dp))

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
                                // Stats
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
                                            value = String.format(Locale.US, "%.2f km", currentState.route.distanceKm)
                                        )
                                        StatItem(
                                            label = "AVERAGE SPEED",
                                            value = String.format(Locale.US, "%.2f km/h", avgSpeedKmh)
                                        )
                                        StatItem(
                                            label = "DURATION",
                                            value = formatTime(currentState.route.duration)
                                        )
                                    }

                                    if (currentState.plannedRoute != null) {
                                        val plannedKm = currentState.plannedRoute.targetDistanceMeters / 1000.0
                                        Spacer(modifier = Modifier.height(12.dp))
                                        Text(
                                            text = String.format(Locale.US, "Planned target: %.2f km", plannedKm),
                                            style = MaterialTheme.typography.bodySmall,
                                            fontWeight = FontWeight.Medium,
                                            color = Color(0xFF7E57C2)
                                        )
                                    }
                                }

                                // Action button to follow route again
                                Button(
                                    onClick = { viewModel.onEvent(RouteDetailsEvent.FollowRouteAgain) },
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .height(48.dp)
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.PlayArrow,
                                        contentDescription = null
                                    )
                                    Spacer(modifier = Modifier.width(8.dp))
                                    Text(
                                        text = if (currentState.plannedRoute != null) {
                                            "Follow This Route Again"
                                        } else {
                                            "Follow This Recording as Route"
                                        }
                                    )
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