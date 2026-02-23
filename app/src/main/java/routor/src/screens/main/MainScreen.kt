package routor.src.screens.main

import android.view.View
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Button
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
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
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import org.osmdroid.tileprovider.tilesource.TileSourceFactory
import org.osmdroid.util.GeoPoint
import org.osmdroid.views.CustomZoomButtonsController
import org.osmdroid.views.MapView
import org.osmdroid.views.overlay.compass.CompassOverlay
import org.osmdroid.views.overlay.compass.InternalCompassOrientationProvider
import org.osmdroid.views.overlay.gestures.RotationGestureOverlay
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
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { mapView.onResume() }
    LifecycleEventEffect(Lifecycle.Event.ON_PAUSE) { mapView.onPause() }


    Box(
        modifier = Modifier
            .fillMaxSize()
            .padding(20.dp)
    ) {
        Button(
            modifier = Modifier
                .align(Alignment.TopEnd)
                .offset(x = 0.dp, y = 20.dp),
            onClick = displayRoutesScreen
        ){
            Text("My Routes")
        }
        AndroidView(
            factory = { context ->
                mapView.apply {
                    mapOrientation = 0f
                    controller.setZoom(15.0)
                    controller.setCenter(GeoPoint(52.2297, 21.0122))
                }
            },
            modifier = Modifier
                .align(Alignment.TopCenter)
                .offset(y = 60.dp)
                .size(400.dp),
            update = {}
        )
        Text(
            text = "LOCATION:",
            modifier = Modifier
                .align(Alignment.TopCenter)
                .offset(x = 0.dp, y = 60.dp)
        )
        Text(
            text = "Latitude = ${locationStats.latitude}",
            modifier = Modifier
                .align(Alignment.TopCenter)
                .offset(x = 0.dp, y = 90.dp)
        )
        Text(
            text = "Longitude = ${locationStats.longitude}",
            modifier = Modifier
                .align(Alignment.TopCenter)
                .offset(x = 0.dp, y = 120.dp)
        )
        Text(
            text = "Total distance = ${locationStats.totalDistanceKm} km",
            modifier = Modifier
                .align(Alignment.TopCenter)
                .offset(x = 0.dp, y = 150.dp)
        )
        Text(
            text = "Current speed = ${locationStats.speedKmh} km/h",
            modifier = Modifier
                .align(Alignment.TopCenter)
                .offset(x = 0.dp, y = 180.dp)
        )

        if (isServiceRunning) {
            Text(
                text = "DURATION",
                modifier = Modifier
                    .align(Alignment.Center)
                    .offset(x = 0.dp, y = (-20).dp),
                style = TextStyle(
                    fontWeight = FontWeight.Bold,
                    fontSize = 20.sp
                )
            )
            Text(
                text = formatTime(duration),
                modifier = Modifier
                    .align(Alignment.Center)
                    .offset(x = 0.dp, y = 20.dp),
                style = TextStyle(
                    fontWeight = FontWeight.Bold,
                    fontSize = 20.sp
                )
            )
            Text(
                text = "Number of points on current route : ${locationStats.numberOfPointsOnRoute}",
                modifier = Modifier
                    .align(Alignment.Center)
                    .offset(x = 0.dp, y = 90.dp)
            )
            StopButton(
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .offset(x = 0.dp, y = (-100).dp),
                onClick = {
                    viewModel.onEvent(MainScreenEvent.ShowStopRouteDialog)
                }
            )
        } else {
            StartButton(
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .offset(x = 0.dp, y = (-100).dp),
                onClick = {
                    viewModel.onEvent(MainScreenEvent.StartRoute)
                }
            )
        }
    }
    if(stopRouteDialogState.isVisible){
        ConfirmDialog(stopRouteDialogState.config!!)
    }
}