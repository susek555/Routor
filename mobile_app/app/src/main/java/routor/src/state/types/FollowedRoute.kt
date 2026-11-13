package routor.src.state.types

import org.maplibre.android.geometry.LatLng

data class FollowedRoute(
    val points: List<LatLng>,
    val distanceMeters: Double
) {}
