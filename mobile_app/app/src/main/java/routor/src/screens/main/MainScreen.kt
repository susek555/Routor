package routor.src.screens.main

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Place
import androidx.compose.material3.Button
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
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
import routor.src.dialogFactory.confirmDialog.ConfirmDialog
import routor.src.data.types.RouteStats
import routor.src.utils.MapHelper
import routor.src.utils.formatTime

@Composable
fun MainScreen(
    displayRoutesDetailsScreen: (id: Long) -> Unit,
    viewModel: MainViewModel
) {
    // UI state from viewModel
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    //map
    val context = LocalContext.current
    val mapView = remember {
        MapHelper.getMainScreenMapView(context)
    }
    MapHelper.SetupMapLifecycleEvents(mapView)

    //map center on request
    LaunchedEffect(Unit) {
        viewModel.centerMapEvent.collect { location ->
            MapHelper.centerCameraOnUserLocation(mapView, location)
        }
    }

    // draw followed route
    LaunchedEffect(uiState.followedRoute) {
        val points = uiState.followedRoute?.points.orEmpty()
        MapHelper.displayPlannedRoute(mapView, points)
        if (points.size >= 2) {
            MapHelper.zoomToRoute(mapView, points, paddingPx = 180)
        }
    }

    // animate route and user location
     LaunchedEffect(uiState.currentLocation, uiState.routeStats.points, uiState.isRecording) {
        if (uiState.isRecording) {
            if (uiState.routeStats.points.isNotEmpty()) {
                MapHelper.updateRoute(mapView, uiState.routeStats.points)
            }
        } else {
            if (uiState.currentLocation != null) {
                MapHelper.updateUserLocation(mapView, uiState.currentLocation!!)
            }
        }
    }

    // clear route on start or stop recording
    LaunchedEffect(uiState.isRecording) {
        MapHelper.clearRoute(mapView)
    }

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
            FloatingActionButton(
                onClick = {viewModel.onEvent(MainScreenEvent.CenterMapOnCurrentLocation)},
                modifier = Modifier
                .align(Alignment.BottomEnd)
                .padding(16.dp)
            ) { Icon(imageVector = Icons.Default.Place, contentDescription = "Center Map") }
        }
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
                        StatItem(label = "DISTANCE", value = "${"%.2f".format(uiState.routeStats.totalDistanceKm)} km")
                        StatItem(label = "SPEED", value = "${"%.2f".format(uiState.routeStats.speedKmh)} km/h")
                        StatItem(label = "DURATION", value = formatTime(uiState.duration))
                    }

                    if (uiState.followedRoute != null) {
                        val targetKm = uiState.followedRoute!!.distanceMeters / 1000.0
                        Spacer(modifier = Modifier.height(8.dp))
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            Text(
                                text = "Target route: ${"%.2f".format(targetKm)} km",
                                fontSize = 13.sp,
                                fontWeight = FontWeight.Medium,
                                color = Color(0xFF7E57C2)
                            )
                            if (!uiState.isRecording) {
                                TextButton(
                                    onClick = { viewModel.onEvent(MainScreenEvent.ClearFollowedRoute) },
                                    contentPadding = PaddingValues(horizontal = 6.dp, vertical = 0.dp)
                                ) {
                                    Text("Clear", fontSize = 12.sp)
                                }
                            }
                        }
                    }

                    if (uiState.isRecording) {
                        Spacer(modifier = Modifier.height(10.dp))
                        Text(
                            text = "Points: ${uiState.routeStats.numberOfPointsOnRoute}",
                            fontSize = 12.sp,
                            color = Color.Gray
                        )
                    }
                }

                //buttons
                Box(
                    modifier = Modifier.padding(bottom = 50.dp),
                    contentAlignment = Alignment.Center
                ) {
                    if (uiState.isRecording) {
                        StopButton(onClick = { viewModel.onEvent(MainScreenEvent.ShowStopRouteDialog) })
                    } else {
                        StartButton(onClick = { viewModel.onEvent(MainScreenEvent.StartRoute) })
                    }
                }
            }
        }
    }
    if(uiState.dialogState.isVisible){
        ConfirmDialog(uiState.dialogState.config!!)
    }
}

@Composable
private fun StatItem(label: String, value: String) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(text = label, style = TextStyle(fontSize = 10.sp, fontWeight = FontWeight.Bold))
        Text(text = value, style = TextStyle(fontSize = 18.sp, fontWeight = FontWeight.ExtraBold))
    }
}