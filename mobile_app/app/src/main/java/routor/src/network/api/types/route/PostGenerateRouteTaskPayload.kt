package routor.src.network.api.types.route

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import org.maplibre.android.geometry.LatLng

@Serializable
data class PostGenerateRouteTaskPayload(
    @SerialName("fcm_token")
    val fcmToken: String,

    @SerialName("user_id")
    val userId: String,

    val center: GeoPoint,

    @SerialName("target_distance")
    val targetDistance: Float
) {
    constructor(
        fcmToken: String,
        userId: String,
        center: LatLng,
        targetDistance: Float
    ) : this(
        fcmToken = fcmToken,
        userId = userId,
        center = GeoPoint(
            longitude = center.longitude,
            latitude = center.latitude
        ),
        targetDistance = targetDistance
    )

    @Serializable
    data class GeoPoint(
        val longitude: Double,
        val latitude: Double
    )
}