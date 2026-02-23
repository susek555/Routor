package routor.src.utils

import android.animation.ValueAnimator
import android.content.Context
import android.graphics.Point
import android.view.View
import android.view.animation.DecelerateInterpolator
import androidx.core.graphics.contains
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

            // Overlays init (by priority)
            overlays.add(compass)
            overlays.add(rotation)
        }
    }

    private fun createCompass(mapView: MapView, context: Context): CompassOverlay {
        val provider = object : IOrientationProvider {
            override fun startOrientationProvider(orientationConsumer: IOrientationConsumer?): Boolean {
                orientationConsumer?.onOrientationChanged(0f, this)
                return true
            }
            override fun stopOrientationProvider() {}
            override fun getLastKnownOrientation(): Float = 0f
            override fun destroy() {}
        }

        //set north if clicked
        return object : CompassOverlay(context, provider, mapView){
            override fun onSingleTapUp(e: android.view.MotionEvent?, mapView: MapView?): Boolean {
                if (e == null || mapView == null) return false

                val location = IntArray(2)
                mapView.getLocationOnScreen(location)

                val screenX = (e.rawX - location[0]).toInt()
                val screenY = (e.rawY - location[1]).toInt()

                if (mCompassFrameBitmap.contains(Point(screenX, screenY))) {
                    val currentRotation = mapView.mapOrientation
                    ValueAnimator.ofFloat(currentRotation, 0f).apply {
                        duration = 500
                        interpolator = DecelerateInterpolator()

                        addUpdateListener { animator ->
                            val animatedValue = animator.animatedValue as Float
                            mapView.mapOrientation = animatedValue
                            onOrientationChanged(-animatedValue, null)
                            mapView.invalidate()
                        }
                        start()
                    }
                    return true
                }
                return super.onSingleTapUp(e, mapView)
            }
        }.apply {
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