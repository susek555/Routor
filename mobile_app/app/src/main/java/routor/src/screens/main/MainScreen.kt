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
import androidx.compose.material3.Button
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
import routor.src.dialogFactory.confirmDialog.ConfirmDialog
import routor.src.location.LocationStats
import routor.src.utils.MapHelper
import routor.src.utils.formatTime

@Composable
fun MainScreen(
    startLocationService: () -> Unit,
    stopLocationService: () -> Unit,
    displayRoutesScreen: () -> Unit,
    viewModel: MainViewModel
) {
    val isServiceRunning by viewModel.isLocationServiceOn.collectAsState()

    LaunchedEffect(isServiceRunning){
        if(isServiceRunning){
            startLocationService()
        } else {
            stopLocationService()
        }
    }

    val stopRouteDialogState by viewModel.stopRouteDialogState.collectAsState()

    val locationStats by viewModel.locationStats.collectAsState(initial = LocationStats())
    val duration by viewModel.elapsedTime.collectAsState()

    //map
    val context = LocalContext.current

    val mapView = remember {
        MapHelper.getMapView(context)
    }
    MapHelper.SetupMapLifecycleEvents(mapView)

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
                factory = {
                    mapView.apply {
                        getMapAsync { map ->
                            val startPos = org.maplibre.android.camera.CameraPosition.Builder()
                                .target(org.maplibre.android.geometry.LatLng(52.2297, 21.0122))
                                .zoom(15.0)
                                .build()

                            map.moveCamera(org.maplibre.android.camera.CameraUpdateFactory.newCameraPosition(startPos))
                        }
                    }
                },
                update = {}
            )
            Button(
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .offset(x = (-20).dp, y = 40.dp),
                onClick = displayRoutesScreen
            ){
                Text("My Routes")
            }
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
                        StatItem(label = "DISTANCE", value = "${locationStats.totalDistanceKm} km")
                        StatItem(label = "SPEED", value = "${locationStats.speedKmh} km/h")
                        StatItem(label = "DURATION", value = formatTime(duration))
                    }

                    if (isServiceRunning) {
                        Spacer(modifier = Modifier.height(10.dp))
                        Text(
                            text = "Points: ${locationStats.numberOfPointsOnRoute}",
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
                    if (isServiceRunning) {
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