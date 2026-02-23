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
    fun getMapView(context: Context): MapView{
        return MapView(context).apply {
            id = View.generateViewId()
            //source
            setTileSource(TileSourceFactory.MAPNIK)
            //gestures
            setMultiTouchControls(true)
            //rotation
            val rotationOverlay = RotationGestureOverlay(this)
            rotationOverlay.isEnabled = true
            overlays.add(rotationOverlay)
            //hide default buttons
            zoomController.setVisibility(CustomZoomButtonsController.Visibility.NEVER)
            //caching tiles to smooth map moving
            setLayerType(View.LAYER_TYPE_HARDWARE, null)
            isTilesScaledToDpi = true
            //compass
            val compassOverlay = CompassOverlay(context, getOrientationProvider(context), this)
            compassOverlay.enableCompass()
            overlays.add(compassOverlay)
        }
    }

    private fun getOrientationProvider(context: Context): IOrientationProvider {
        return object : IOrientationProvider {
            private var consumer: IOrientationConsumer? = null

            override fun startOrientationProvider(orientationConsumer: IOrientationConsumer?): Boolean {
                consumer = orientationConsumer
                consumer?.onOrientationChanged(0f, this)
                return true
            }

            override fun stopOrientationProvider() {
                consumer = null
            }

            override fun getLastKnownOrientation(): Float = 0f

            override fun destroy() {}
        }
    }
}