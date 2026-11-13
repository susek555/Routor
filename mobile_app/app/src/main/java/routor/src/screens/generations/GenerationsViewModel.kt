package routor.src.screens.generations

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import org.maplibre.android.geometry.LatLng
import routor.src.data.repositories.GenerationsRepository
import routor.src.data.repositories.LocationRepository
import routor.src.network.api.types.route.FailedRouteGenerationTaskStatus
import routor.src.network.api.types.route.ProgressRouteGenerationTaskStatus
import routor.src.network.api.types.route.RouteGenerationTaskStatus
import routor.src.network.api.types.route.RouteGenerationTaskStatusEnum
import routor.src.state.ActiveRideHolder
import routor.src.state.GenerationsInfoHolder
import routor.src.state.types.FollowedRoute
import javax.inject.Inject

@HiltViewModel
class GenerationsViewModel @Inject constructor(
    private val generationsRepository: GenerationsRepository,
    private val locationRepository: LocationRepository,
    private val activeRideHolder: ActiveRideHolder,
    private val generationsInfoHolder: GenerationsInfoHolder
) : ViewModel() {

    private val _uiState = MutableStateFlow(GenerationsScreenUiState())
    val uiState = _uiState.asStateFlow()

    private var generationJob: Job? = null

    init {
        viewModelScope.launch {
            locationRepository.currentLocation.collect { loc ->
                if (loc != null && _uiState.value.centerPoint == null) {
                    _uiState.update { it.copy(centerPoint = loc) }
                }
            }
        }
    }

    fun onDistanceChanged(newDistanceKm: Float) {
        _uiState.update { it.copy(targetDistanceKm = newDistanceKm) }
    }

    fun onCenterPointChanged(newCenter: LatLng) {
        _uiState.update { it.copy(centerPoint = newCenter) }
    }

    fun startGeneration() {
        val center = _uiState.value.centerPoint
            ?: return _uiState.setError("Failed to set start point.")

        val distanceKm = _uiState.value.targetDistanceKm?.takeIf { it > 0f }
            ?: return _uiState.setError("Incorrect distance value.")

        val distanceMeters = distanceKm * 1000f

        generationJob?.cancel()
        generationJob = viewModelScope.launch {
            _uiState.update {
                it.copy(phase = GenerationsPhase.Generating(steps = initialGenerationSteps()))
            }
            var lastActiveOrder = GenerationStage.LOADING_GRAPH.order

            try {
                // 1. POST
                val taskId = generationsRepository.startRouteGeneration(
                    center = center,
                    targetDistanceMeters = distanceMeters
                )
                generationsInfoHolder.setTaskId(taskId)

                // 2. WS
                generationsRepository.observeTaskProgress(taskId)
                    .catch { e ->
                        val currentSteps = (_uiState.value.phase as? GenerationsPhase.Generating)?.steps.orEmpty()
                        _uiState.setError(
                            message = e.localizedMessage ?: "WebSocket connection failed",
                            steps = currentSteps
                        )
                    }
                    .collect { wsStatus ->
                        mapStateToOrder(wsStatus.state)?.let { lastActiveOrder = it }
                        val updatedSteps = buildStepsFromWsStatus(wsStatus, lastActiveOrder)

                        when (wsStatus.state) {
                            RouteGenerationTaskStatusEnum.LOADING_GRAPH,
                            RouteGenerationTaskStatusEnum.SIMPLIFYING_GRAPH,
                            RouteGenerationTaskStatusEnum.GENERATING_ROUTE -> {
                                _uiState.update {
                                    it.copy(phase = GenerationsPhase.Generating(updatedSteps))
                                }
                            }

                            RouteGenerationTaskStatusEnum.FAILED -> {
                                val errorMsg = (wsStatus.payload as? FailedRouteGenerationTaskStatus)?.errorMessage
                                    ?: "Failed to generate route - unknown error"
                                _uiState.setError(errorMsg, updatedSteps)
                            }

                            RouteGenerationTaskStatusEnum.COMPLETED -> {
                                _uiState.update {
                                    it.copy(phase = GenerationsPhase.Generating(updatedSteps))
                                }

                                val variants = generationsRepository.getRouteVariants(taskId)
                                if (variants.isEmpty()) {
                                    _uiState.setError("No route variants were returned.", updatedSteps)
                                } else {
                                    _uiState.update {
                                        it.copy(
                                            phase = GenerationsPhase.SelectingVariant(
                                                variants = variants,
                                                currentIndex = 0
                                            )
                                        )
                                    }
                                }
                            }
                        }
                    }
            } catch (e: Exception) {
                _uiState.setError(e.localizedMessage ?: "Unknown error")
            }
        }
    }

    fun selectNextVariant() {
        _uiState.update { state ->
            val currentPhase = state.phase as? GenerationsPhase.SelectingVariant ?: return@update state
            if (!currentPhase.hasNext) return@update state
            state.copy(phase = currentPhase.copy(currentIndex = currentPhase.currentIndex + 1))
        }
    }

    fun selectPreviousVariant() {
        _uiState.update { state ->
            val currentPhase = state.phase as? GenerationsPhase.SelectingVariant ?: return@update state
            if (!currentPhase.hasPrevious) return@update state
            state.copy(phase = currentPhase.copy(currentIndex = currentPhase.currentIndex - 1))
        }
    }

    fun confirmSelectedVariant(onNavigateToMain: () -> Unit) {
        val currentPhase = _uiState.value.phase as? GenerationsPhase.SelectingVariant ?: return
        val chosen = currentPhase.currentVariant ?: return

        activeRideHolder.setFollowedRoute(
            FollowedRoute(
                distanceMeters = chosen.distanceMeters,
                points = chosen.points
            )
        )
        onNavigateToMain()
    }

    fun resetToForm() {
        generationJob?.cancel()
        _uiState.update { it.copy(phase = GenerationsPhase.Configuring) }
    }

    private fun MutableStateFlow<GenerationsScreenUiState>.setError(
        message: String,
        steps: List<GenerationStepItem> = emptyList()
    ) {
        update {
            it.copy(phase = GenerationsPhase.Error(message = message, steps = steps))
        }
    }

    private fun mapStateToOrder(state: RouteGenerationTaskStatusEnum): Int? = when (state) {
        RouteGenerationTaskStatusEnum.LOADING_GRAPH -> GenerationStage.LOADING_GRAPH.order
        RouteGenerationTaskStatusEnum.SIMPLIFYING_GRAPH -> GenerationStage.SIMPLIFYING_GRAPH.order
        RouteGenerationTaskStatusEnum.GENERATING_ROUTE -> GenerationStage.GENERATING_ROUTE.order
        RouteGenerationTaskStatusEnum.COMPLETED -> GenerationStage.entries.size + 1
        RouteGenerationTaskStatusEnum.FAILED -> null
    }

    private fun initialGenerationSteps(): List<GenerationStepItem> =
        buildSteps(
            currentOrder = GenerationStage.LOADING_GRAPH.order,
            isCompleted = false,
            isFailed = false,
            generatingSubtitle = null
        )

    private fun buildStepsFromWsStatus(
        status: RouteGenerationTaskStatus,
        fallbackOrder: Int
    ): List<GenerationStepItem> {
        val progressPayload = status.payload as? ProgressRouteGenerationTaskStatus
        val currentOrder = mapStateToOrder(status.state) ?: fallbackOrder

        val generatingSubtitle = when {
            progressPayload != null -> "Variant ${progressPayload.done} of ${progressPayload.total}"
            status.state == RouteGenerationTaskStatusEnum.COMPLETED -> "All variants ready"
            else -> null
        }

        return buildSteps(
            currentOrder = currentOrder,
            isCompleted = status.state == RouteGenerationTaskStatusEnum.COMPLETED,
            isFailed = status.state == RouteGenerationTaskStatusEnum.FAILED,
            generatingSubtitle = generatingSubtitle
        )
    }

    private fun buildSteps(
        currentOrder: Int,
        isCompleted: Boolean,
        isFailed: Boolean,
        generatingSubtitle: String?
    ): List<GenerationStepItem> =
        GenerationStage.entries.map { stage ->
            val stepStatus = when {
                isCompleted -> StepStatus.COMPLETED
                isFailed && stage.order == currentOrder -> StepStatus.FAILED
                stage.order < currentOrder -> StepStatus.COMPLETED
                stage.order == currentOrder -> StepStatus.IN_PROGRESS
                else -> StepStatus.PENDING
            }

            GenerationStepItem(
                id = stage.id,
                title = stage.title,
                subtitle = if (stage == GenerationStage.GENERATING_ROUTE) generatingSubtitle else null,
                status = stepStatus
            )
        }
}