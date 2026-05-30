package routor.src.data.types

import org.maplibre.android.geometry.LatLng

data class RouteStats(
    val points: List<LatLng> = emptyList(),
    val speedKmh: Float = 0f,
    val totalDistanceKm: Float = 0f,
    val numberOfPointsOnRoute: Int = 0
)
