package routor.src.screens.generations

import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import routor.src.screens.generations.views.GenerationsConfiguringView
import routor.src.screens.generations.views.GenerationsErrorView
import routor.src.screens.generations.views.GenerationsProgressView
import routor.src.screens.generations.views.GenerationsVariantSelectionView

@Composable
fun GenerationsScreen(
    onNavigateToMain: () -> Unit,
    viewModel: GenerationsViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    Surface(modifier = Modifier.fillMaxSize()) {
        when (val phase = uiState.phase) {
            is GenerationsPhase.Configuring -> {
                GenerationsConfiguringView(
                    centerPoint = uiState.centerPoint,
                    targetDistanceKm = uiState.targetDistanceKm,
                    onDistanceChanged = viewModel::onDistanceChanged,
                    onCenterPointChanged = viewModel::onCenterPointChanged,
                    onStartGeneration = viewModel::startGeneration
                )
            }

            is GenerationsPhase.Generating -> {
                GenerationsProgressView(
                    steps = phase.steps,
                    onCancel = viewModel::resetToForm
                )
            }

            is GenerationsPhase.SelectingVariant -> {
                GenerationsVariantSelectionView(
                    phase = phase,
                    onPreviousVariant = viewModel::selectPreviousVariant,
                    onNextVariant = viewModel::selectNextVariant,
                    onConfirmVariant = { viewModel.confirmSelectedVariant(onNavigateToMain) },
                    onRegenerate = viewModel::resetToForm
                )
            }

            is GenerationsPhase.Error -> {
                GenerationsErrorView(
                    message = phase.message,
                    steps = phase.steps,
                    onRetry = viewModel::resetToForm
                )
            }
        }
    }
}