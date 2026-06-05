package routor.src.screens.main

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
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
    displayRoutesScreen: () -> Unit,
    displayGenerationsScreen: () -> Unit,
    viewModel: MainViewModel
) {
    val isServiceRecordingRoute by viewModel.isServiceRecordingRoute.collectAsStateWithLifecycle()
    val stopRouteDialogState by viewModel.stopRouteDialogState.collectAsStateWithLifecycle()

    val currentLocation by viewModel.currentLocation.collectAsStateWithLifecycle()
    val routeStats by viewModel.locationStats.collectAsStateWithLifecycle()
    val duration by viewModel.duration.collectAsStateWithLifecycle()

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

    // animate route and user location
     LaunchedEffect(currentLocation, routeStats.points, isServiceRecordingRoute) {
        if (isServiceRecordingRoute) {
            if (routeStats.points.isNotEmpty()) {
                MapHelper.updateRoute(mapView, routeStats.points)
            }
        } else {
            if (currentLocation != null) {
                MapHelper.updateUserLocation(mapView, currentLocation!!)
            }
        }
    }

    // clear route on start or stop recording
    LaunchedEffect(isServiceRecordingRoute) {
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
            if (!isServiceRecordingRoute) {

                //TODO rearrange to NavBar
                Button(
                    modifier = Modifier
                        .align(Alignment.TopStart)
                        .offset(x = (-20).dp, y = 40.dp),
                    onClick = displayGenerationsScreen
                ) {
                    Text("Generate")
                }

                Button(
                    modifier = Modifier
                        .align(Alignment.TopEnd)
                        .offset(x = (-20).dp, y = 40.dp),
                    onClick = displayRoutesScreen
                ) {
                    Text("My Routes")
                }
            }
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
                        StatItem(label = "DISTANCE", value = "${"%.2f".format(routeStats.totalDistanceKm)} km")
                        StatItem(label = "SPEED", value = "${"%.2f".format(routeStats.speedKmh)} km/h")
                        StatItem(label = "DURATION", value = formatTime(duration))
                    }

                    if (isServiceRecordingRoute) {
                        Spacer(modifier = Modifier.height(10.dp))
                        Text(
                            text = "Points: ${routeStats.numberOfPointsOnRoute}",
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
                    if (isServiceRecordingRoute) {
                        StopButton(onClick = { viewModel.onEvent(MainScreenEvent.ShowStopRouteDialog) })
                    } else {
                        StartButton(onClick = { viewModel.onEvent(MainScreenEvent.StartRoute) })
                    }
                }
            }
        }
    }
    if(stopRouteDialogState.isVisible){
        ConfirmDialog(stopRouteDialogState.config!!)
    }
}

@Composable
private fun StatItem(label: String, value: String) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(text = label, style = TextStyle(fontSize = 10.sp, fontWeight = FontWeight.Bold))
        Text(text = value, style = TextStyle(fontSize = 18.sp, fontWeight = FontWeight.ExtraBold))
    }
}