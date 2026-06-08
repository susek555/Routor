package routor.src.utils

import android.animation.ValueAnimator
import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.view.animation.LinearInterpolator
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import org.maplibre.android.MapLibre
import org.maplibre.android.WellKnownTileServer
import org.maplibre.android.camera.CameraUpdateFactory
import org.maplibre.android.geometry.LatLng
import org.maplibre.android.maps.MapView
import org.maplibre.android.maps.Style
import org.maplibre.android.style.layers.Property
import org.maplibre.android.style.layers.PropertyFactory
import org.maplibre.android.style.layers.SymbolLayer
import org.maplibre.android.style.sources.GeoJsonSource
import org.maplibre.geojson.Feature
import org.maplibre.geojson.FeatureCollection
import org.maplibre.geojson.LineString
import org.maplibre.geojson.Point
import routor.R



object MapHelper {
    private const val MAP_STYLE_URL = "https://tiles.openfreemap.org/styles/liberty"
    private const val USER_ICON_ID = "user-icon"
    private const val USER_SOURCE_ID = "user-source"
    private const val USER_LAYER_ID = "user-layer"
    private const val ROUTE_SOURCE_ID = "route-source"
    private const val ROUTE_LAYER_ID = "route-layer"
    private const val START_ICON_ID = "start-icon"
    private const val START_SOURCE_ID = "start-source"
    private const val START_LAYER_ID = "start-layer"
    private const val END_ICON_ID = "end-icon"
    private const val END_SOURCE_ID = "end-source"
    private const val END_LAYER_ID = "end-layer"

    private fun init(context: Context) {
        MapLibre.getInstance(context, null, WellKnownTileServer.MapLibre)
    }

    private fun getBitmapFromVectorDrawable(context: Context, drawableId: Int): Bitmap {
        val drawable = ContextCompat.getDrawable(context, drawableId)!!
        val bitmap = Bitmap.createBitmap(
            drawable.intrinsicWidth,
            drawable.intrinsicHeight,
            Bitmap.Config.ARGB_8888
        )
        val canvas = Canvas(bitmap)
        drawable.setBounds(0, 0, canvas.width, canvas.height)
        drawable.draw(canvas)
        return bitmap
    }

    private fun setupUserLocationLayer(style: Style, context: Context) {
        val bitmap = getBitmapFromVectorDrawable(context, R.drawable.user_location_dot)
        style.addImage(USER_ICON_ID, bitmap)

        val emptySource = GeoJsonSource(USER_SOURCE_ID)
        style.addSource(emptySource)

        // TODO probably turn off rotation due to visual bugs

        val symbolLayer = SymbolLayer(USER_LAYER_ID, USER_SOURCE_ID)
        symbolLayer.setProperties(
            PropertyFactory.iconImage(USER_ICON_ID),
            PropertyFactory.iconAllowOverlap(true),
            PropertyFactory.iconIgnorePlacement(true),
            PropertyFactory.iconRotationAlignment(Property.ICON_ROTATION_ALIGNMENT_VIEWPORT),
        )
        style.addLayer(symbolLayer)
    }

    private fun setupRouteLayer(style: Style) {
        val geoJsonSource = GeoJsonSource(ROUTE_SOURCE_ID)
        style.addSource(geoJsonSource)

        val lineLayer = org.maplibre.android.style.layers.LineLayer(ROUTE_LAYER_ID, ROUTE_SOURCE_ID)
        lineLayer.setProperties(
            PropertyFactory.lineColor(android.graphics.Color.parseColor("#4285F4")),
            PropertyFactory.lineWidth(5f),
            PropertyFactory.lineJoin(Property.LINE_JOIN_ROUND),
            PropertyFactory.lineCap(Property.LINE_CAP_ROUND),
            PropertyFactory.lineOpacity(0.8f)
        )

        if (style.getLayer(USER_LAYER_ID) != null) {
            style.addLayerBelow(lineLayer, USER_LAYER_ID)
        } else {
            style.addLayer(lineLayer)
        }
    }

    private fun setupRouteStartLayer(style: Style, context: Context) {
        val bitmap = getBitmapFromVectorDrawable(context, R.drawable.route_begin_dot)
        style.addImage(START_ICON_ID, bitmap)

        val emptySource = GeoJsonSource(START_SOURCE_ID)
        style.addSource(emptySource)

        val symbolLayer = SymbolLayer(START_LAYER_ID, START_SOURCE_ID)
        symbolLayer.setProperties(
            PropertyFactory.iconImage(START_ICON_ID),
            PropertyFactory.iconAllowOverlap(true),
            PropertyFactory.iconIgnorePlacement(true),
            PropertyFactory.iconRotationAlignment(Property.ICON_ROTATION_ALIGNMENT_VIEWPORT)
        )

        style.addLayerAbove(symbolLayer, ROUTE_LAYER_ID)
    }

    private fun setupRouteEndLayer(style: Style, context: Context) {
        val bitmap = getBitmapFromVectorDrawable(context, R.drawable.route_end_dot)
        style.addImage(END_LAYER_ID, bitmap)

        val emptySource = GeoJsonSource(END_SOURCE_ID)
        style.addSource(emptySource)

        val symbolLayer = SymbolLayer(END_LAYER_ID, END_SOURCE_ID)
        symbolLayer.setProperties(
            PropertyFactory.iconImage(END_ICON_ID),
            PropertyFactory.iconAllowOverlap(true),
            PropertyFactory.iconIgnorePlacement(true),
            PropertyFactory.iconRotationAlignment(Property.ICON_ROTATION_ALIGNMENT_VIEWPORT)
        )

        style.addLayerAbove(symbolLayer, ROUTE_LAYER_ID)
    }

    private fun getMapView(context: Context, hasUserLocation: Boolean): MapView {
        init(context)
        val mapView = MapView(context)

        mapView.getMapAsync { map ->
            map.setStyle(MAP_STYLE_URL) { style ->

                setupRouteLayer(style)
                setupRouteStartLayer(style, context)

                if(hasUserLocation) {
                    setupUserLocationLayer(style, context)
                } else {
                    setupRouteEndLayer(style, context)
                }
            }

            map.uiSettings.apply {
                isCompassEnabled = true
                isRotateGesturesEnabled = true
                isTiltGesturesEnabled = false
                setCompassMargins(50, 300, 50, 50)
            }

            map.addOnCameraMoveListener {}
        }

        return mapView
    }

    fun getMainScreenMapView(context: Context): MapView {
        return getMapView(
            context = context,
            hasUserLocation = true
        )
    }

    fun getRouteScreenMapView(context: Context): MapView {
        return getMapView(
            context = context,
            hasUserLocation = false
        )
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



    fun centerCameraOnUserLocation(mapView: MapView, userLocation: LatLng) {
        mapView.getMapAsync { map ->
            val cameraUpdate = CameraUpdateFactory.newLatLngZoom(userLocation, 15.0)
            map.animateCamera(cameraUpdate, 1000)
        }
    }

    fun updateUserLocation(mapView: MapView, newLocation: LatLng) {
        mapView.getMapAsync { map ->
            val style = map.style ?: return@getMapAsync
            val userSource = style.getSourceAs<GeoJsonSource>(USER_SOURCE_ID) ?: return@getMapAsync

            // animation
            val oldAnimator = mapView.getTag(R.id.map_animator_tag) as? ValueAnimator
            val newAnimator = animateLocation(userSource, oldAnimator, newLocation)
            mapView.setTag(R.id.map_animator_tag, newAnimator)
        }
    }

    private fun animateLocation(
        userSource: GeoJsonSource,
        oldAnimator: ValueAnimator?,
        destPoint: LatLng,
        routeSource: GeoJsonSource? = null,
        previousRoutePoints: List<Point> = emptyList()
    ): ValueAnimator? {

        val lastFeature = userSource.querySourceFeatures(null).firstOrNull()
        val lastPoint = lastFeature?.geometry() as? Point

        if (lastPoint == null) {
            val point = Point.fromLngLat(destPoint.longitude, destPoint.latitude)
            userSource.setGeoJson(Feature.fromGeometry(point))
            return null
        }

        oldAnimator?.cancel()

        val newAnimator = ValueAnimator.ofFloat(0f, 1f).apply {
            duration = 1000
            interpolator = LinearInterpolator()

            addUpdateListener { animation ->
                val fraction = animation.animatedValue as Float

                val lon = lastPoint.longitude() + (destPoint.longitude - lastPoint.longitude()) * fraction
                val lat = lastPoint.latitude() + (destPoint.latitude - lastPoint.latitude()) * fraction
                val intermediatePoint = Point.fromLngLat(lon, lat)

                // Animate dot always
                userSource.setGeoJson(Feature.fromGeometry(intermediatePoint))

                // Route only if source passed
                if (routeSource != null) {
                    val updatedRoute = previousRoutePoints + intermediatePoint
                    routeSource.setGeoJson(Feature.fromGeometry(LineString.fromLngLats(updatedRoute)))
                }
            }
            start()
        }
        return newAnimator
    }

    fun updateRoute(mapView: MapView, points: List<LatLng>) {
        mapView.getMapAsync { map ->
            val style = map.style ?: return@getMapAsync
            val routeSource = style.getSourceAs<GeoJsonSource>(ROUTE_SOURCE_ID) ?: return@getMapAsync
            val startSource = style.getSourceAs<GeoJsonSource>(START_SOURCE_ID) ?: return@getMapAsync
            val userSource = style.getSourceAs<GeoJsonSource>(USER_SOURCE_ID) ?: return@getMapAsync

            if (points.isEmpty()) {
                clearRoute(mapView)
                return@getMapAsync
            }

            // start green point
            val firstPoint = Point.fromLngLat(points.first().longitude, points.first().latitude)
            startSource.setGeoJson(Feature.fromGeometry(firstPoint))

            if (points.size >= 2) {
                // all previous points on route
                val mapboxPoints = points.map { Point.fromLngLat(it.longitude, it.latitude) }
                val previousPoints = mapboxPoints.dropLast(1)

                // animation
                val oldAnimator = mapView.getTag(R.id.map_animator_tag) as? ValueAnimator
                val newAnimator = animateLocation(
                    userSource = userSource,
                    oldAnimator = oldAnimator,
                    destPoint = points.last(),
                    routeSource = routeSource,
                    previousRoutePoints = previousPoints
                )
                mapView.setTag(R.id.map_animator_tag, newAnimator)
            }
        }
    }

    fun clearRoute(mapView: MapView) {
        mapView.getMapAsync { map ->
            val style = map.style ?: return@getMapAsync
            val routeSource = style.getSourceAs<GeoJsonSource>(ROUTE_SOURCE_ID)
            val startSource = style.getSourceAs<GeoJsonSource>(START_SOURCE_ID)

            routeSource?.setGeoJson(FeatureCollection.fromFeatures(emptyList()))
            startSource?.setGeoJson(FeatureCollection.fromFeatures(emptyList()))
        }
    }
}