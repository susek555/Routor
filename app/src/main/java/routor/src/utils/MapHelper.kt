package routor.src.utils

import android.content.Context
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import org.maplibre.android.MapLibre
import org.maplibre.android.WellKnownTileServer
import org.maplibre.android.camera.CameraPosition
import org.maplibre.android.camera.CameraUpdateFactory
import org.maplibre.android.maps.MapView
import org.maplibre.android.maps.MapLibreMap

private const val mapStyleUrl = "https://tiles.openfreemap.org/styles/liberty"

object MapHelper {
    private fun init(context: Context) {
        MapLibre.getInstance(context, null, WellKnownTileServer.MapLibre)
    }

    fun getMapView(context: Context): MapView {
        init(context)
        val mapView = MapView(context)

        mapView.getMapAsync { map ->
            map.setStyle(mapStyleUrl) {}

            map.uiSettings.apply {
                isCompassEnabled = true
                isRotateGesturesEnabled = true
                isTiltGesturesEnabled = false
                setCompassMargins(50, 50, 50, 50)
            }

            map.addOnCameraMoveListener {}
        }

        return mapView
    }

    @Composable
    fun SetupMapLifecycleEvents(mapView: MapView){
        LifecycleEventEffect(Lifecycle.Event.ON_CREATE) { mapView.onCreate(null) }
        LifecycleEventEffect(Lifecycle.Event.ON_START) { mapView.onStart() }
        LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { mapView.onResume() }
        LifecycleEventEffect(Lifecycle.Event.ON_PAUSE) { mapView.onPause() }
        LifecycleEventEffect(Lifecycle.Event.ON_STOP) { mapView.onStop() }

        DisposableEffect(mapView) {
            onDispose {
                mapView.onStop()
                mapView.onDestroy()
            }
        }
    }

    //TODO remove if still unused
    fun resetToNorth(map: MapLibreMap) {
        val currentPos = map.cameraPosition
        val cameraUpdate = CameraUpdateFactory.newCameraPosition(
            CameraPosition.Builder()
                .bearing(0.0)
                .target(currentPos.target)
                .zoom(currentPos.zoom)
                .build()
        )
        map.animateCamera(cameraUpdate, 500)
    }
}