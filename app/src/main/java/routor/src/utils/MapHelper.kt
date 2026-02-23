package routor.src.utils

import android.content.Context
import android.view.View
import org.osmdroid.tileprovider.tilesource.TileSourceFactory
import org.osmdroid.views.CustomZoomButtonsController
import org.osmdroid.views.MapView
import org.osmdroid.views.overlay.compass.CompassOverlay
import org.osmdroid.views.overlay.compass.IOrientationConsumer
import org.osmdroid.views.overlay.compass.IOrientationProvider
import org.osmdroid.views.overlay.gestures.RotationGestureOverlay

object MapHelper {
    fun getMapView(context: Context): MapView {
        return MapView(context).apply {
            id = View.generateViewId()
            setTileSource(TileSourceFactory.MAPNIK)
            setMultiTouchControls(true)

            // UI & Performance
            zoomController.setVisibility(CustomZoomButtonsController.Visibility.NEVER)
            setLayerType(View.LAYER_TYPE_HARDWARE, null)
            isTilesScaledToDpi = true

            // Components init
            val compass = createCompass(this, context)
            val rotation = createRotation(this, compass)

            // Overlays init
            overlays.add(rotation)
            overlays.add(compass)
        }
    }

    private fun createCompass(mapView: MapView, context: Context): CompassOverlay {
        val provider = object : IOrientationProvider {
            override fun startOrientationProvider(orientationConsumer: IOrientationConsumer?): Boolean {
                return true
            }
            override fun stopOrientationProvider() {}
            override fun getLastKnownOrientation(): Float = 0f
            override fun destroy() {}
        }

        return CompassOverlay(context, provider, mapView).apply {
            enableCompass()
        }
    }

    private fun createRotation(mapView: MapView, compassOverlay: CompassOverlay): RotationGestureOverlay {
        return object : RotationGestureOverlay(mapView) {
            override fun onRotate(deltaAngle: Float) {
                super.onRotate(deltaAngle)
                compassOverlay.onOrientationChanged(-mapView.mapOrientation, null)
            }
        }.apply {
            isEnabled = true
        }
    }
}