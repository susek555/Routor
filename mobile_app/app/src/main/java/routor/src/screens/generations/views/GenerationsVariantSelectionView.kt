package routor.src.screens.generations.views

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.filled.Check
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import routor.src.screens.generations.GenerationsPhase
import routor.src.utils.MapHelper
import java.util.Locale

@Composable
fun GenerationsVariantSelectionView(
    phase: GenerationsPhase.SelectingVariant,
    onPreviousVariant: () -> Unit,
    onNextVariant: () -> Unit,
    onConfirmVariant: () -> Unit,
    onRegenerate: () -> Unit
) {
    val context = LocalContext.current
    val mapView = remember {
        MapHelper.getRouteScreenMapView(context)
    }
    MapHelper.SetupMapLifecycleEvents(mapView)

    val currentVariant = phase.currentVariant

    // Redraw route on every variant change
    LaunchedEffect(currentVariant) {
        val points = currentVariant?.points.orEmpty()
        MapHelper.displayFullRoute(mapView, points)
        MapHelper.zoomToRoute(mapView, points, paddingPx = 180)
    }

    Box(modifier = Modifier.fillMaxSize()) {
        AndroidView(
            factory = { mapView },
            modifier = Modifier.fillMaxSize()
        )

        // Top go back button
        FilledTonalIconButton(
            onClick = onRegenerate,
            modifier = Modifier
                .align(Alignment.TopStart)
                .padding(16.dp)
        ) {
            Icon(imageVector = Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Regenerate")
        }

        // Bottom variants selection arrows
        ElevatedCard(
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .fillMaxWidth()
                .padding(16.dp),
            elevation = CardDefaults.elevatedCardElevation(defaultElevation = 6.dp)
        ) {
            Column(
                modifier = Modifier.padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    IconButton(
                        onClick = onPreviousVariant,
                        enabled = phase.hasPrevious
                    ) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "Previous variant"
                        )
                    }

                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(
                            text = "Variant ${phase.currentIndex + 1} of ${phase.variants.size}",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold
                        )
                        if (currentVariant != null) {
                            val km = currentVariant.distanceMeters / 1000.0
                            val matchPercent = (currentVariant.fitnessScore * 100).toInt()
                            Text(
                                text = String.format(Locale.US, "%.2f km • %d%% match", km, matchPercent),
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }

                    IconButton(
                        onClick = onNextVariant,
                        enabled = phase.hasNext
                    ) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.ArrowForward,
                            contentDescription = "Next variant"
                        )
                    }
                }

                Button(
                    onClick = onConfirmVariant,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(50.dp)
                ) {
                    Icon(imageVector = Icons.Default.Check, contentDescription = null)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Select This Route")
                }
            }
        }
    }
}