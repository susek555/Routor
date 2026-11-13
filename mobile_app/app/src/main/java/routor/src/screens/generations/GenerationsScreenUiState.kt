package routor.src.screens.generations

import org.maplibre.android.geometry.LatLng
import routor.src.network.api.types.route.GetVariantsResponse

enum class StepStatus {
    PENDING,
    IN_PROGRESS,
    COMPLETED,
    FAILED
}

data class GenerationStepItem(
    val id: String,
    val title: String,
    val subtitle: String? = null,
    val status: StepStatus = StepStatus.PENDING
)

enum class GenerationStage(
    val id: String,
    val title: String,
    val order: Int
) {
    LOADING_GRAPH(
        id = "load",
        title = "Loading map graph",
        order = 1
    ),
    SIMPLIFYING_GRAPH(
        id = "simplify",
        title = "Simplifying and preparing map to algorithm",
        order = 2
    ),
    GENERATING_ROUTE(
        id = "generate",
        title = "Calculating paths",
        order = 3
    )
}

sealed interface GenerationsPhase {
    data object Configuring : GenerationsPhase

    data class Generating(
        val steps: List<GenerationStepItem>
    ) : GenerationsPhase

    data class SelectingVariant(
        val variants: List<GetVariantsResponse.RouteVariantDto>,
        val currentIndex: Int = 0
    ) : GenerationsPhase {
        val currentVariant: GetVariantsResponse.RouteVariantDto?
            get() = variants.getOrNull(currentIndex)

        val hasPrevious: Boolean
            get() = currentIndex > 0

        val hasNext: Boolean
            get() = currentIndex < variants.lastIndex
    }

    data class Error(
        val message: String,
        val steps: List<GenerationStepItem>
    ) : GenerationsPhase
}

data class GenerationsScreenUiState(
    val centerPoint: LatLng? = null,
    val targetDistanceKm: Float? = null,
    val phase: GenerationsPhase = GenerationsPhase.Configuring
)