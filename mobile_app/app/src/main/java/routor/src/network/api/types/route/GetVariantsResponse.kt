package routor.src.network.api.types.route

import kotlinx.serialization.KSerializer
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.descriptors.SerialDescriptor
import kotlinx.serialization.descriptors.buildClassSerialDescriptor
import kotlinx.serialization.encoding.Decoder
import kotlinx.serialization.encoding.Encoder
import kotlinx.serialization.json.JsonDecoder
import kotlinx.serialization.json.double
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.maplibre.android.geometry.LatLng

@Serializable
data class GetVariantsResponse(
    @SerialName("task_id")
    val taskId: String,

    @SerialName("total_variants")
    val totalVariants: Int,

    val variants: List<RouteVariantDto>
) {
    @Serializable
    data class RouteVariantDto(
        val id: String,

        @SerialName("variant_index")
        val variantIndex: Int,

        @SerialName("distance_meters")
        val distanceMeters: Double,

        @SerialName("fitness_score")
        val fitnessScore: Double,

        @SerialName("geojson")
        val geojson: GeoJsonPoints
    ) {
        val points: List<LatLng> get() = geojson.points
    }
}

@Serializable(with = GeoJsonPointsSerializer::class)
data class GeoJsonPoints(
    val points: List<LatLng>
)

object GeoJsonPointsSerializer : KSerializer<GeoJsonPoints> {
    override val descriptor: SerialDescriptor =
        buildClassSerialDescriptor("GeoJsonPoints")

    override fun deserialize(decoder: Decoder): GeoJsonPoints {
        val jsonDecoder = decoder as? JsonDecoder
            ?: error("GeoJsonPointsSerializer works only with JSON")

        val jsonObject = jsonDecoder.decodeJsonElement().jsonObject
        val coordinatesArray = jsonObject["coordinates"]?.jsonArray
            ?: return GeoJsonPoints(emptyList())

        val latLngs = coordinatesArray.mapNotNull { pointElement ->
            val coords = pointElement.jsonArray
            if (coords.size >= 2) {
                val lon = coords[0].jsonPrimitive.double
                val lat = coords[1].jsonPrimitive.double
                LatLng(latitude = lat, longitude = lon)
            } else {
                null
            }
        }
        return GeoJsonPoints(latLngs)
    }

    override fun serialize(encoder: Encoder, value: GeoJsonPoints) {
        throw UnsupportedOperationException("Serialization of GeoJsonPoints is not needed")
    }
}