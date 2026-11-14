package routor.src.screens.generations.views

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import org.maplibre.android.geometry.LatLng
import java.util.Locale

@Composable
fun GenerationsConfiguringView(
    centerPoint: LatLng?,
    targetDistanceKm: Float,
    onDistanceChanged: (Float) -> Unit,
    onCenterPointChanged: (LatLng) -> Unit,
    onStartGeneration: () -> Unit
) {

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.SpaceBetween
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(24.dp)) {
            Text(
                text = "Generate a Route",
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.Bold
            )

            OutlinedCard(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.LocationOn,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.primary
                        )
                        Text(
                            text = "Starting Point",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold
                        )
                    }

                    if (centerPoint != null) {
                        Text(
                            text = String.format(
                                Locale.US,
                                "Lat: %.5f, Lon: %.5f",
                                centerPoint.latitude,
                                centerPoint.longitude
                            ),
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    } else {
                        Text(
                            text = "Waiting for GPS location...",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.error
                        )
                        //TODO remove temp demo
                        TextButton(
                            onClick = { onCenterPointChanged(LatLng(52.2297, 21.0122)) },
                            contentPadding = PaddingValues(0.dp)
                        ) {
                            Text("Use Demo Location (Warsaw)")
                        }
                    }
                }
            }

            OutlinedCard(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.Bottom
                    ) {
                        Text(
                            text = "Target Distance",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold
                        )
                        Text(
                            text = String.format(Locale.US, "%.1f km", targetDistanceKm),
                            style = MaterialTheme.typography.headlineSmall,
                            color = MaterialTheme.colorScheme.primary,
                            fontWeight = FontWeight.Bold
                        )
                    }

                    Slider(
                        value = targetDistanceKm,
                        onValueChange = { raw ->
                            // Rounded to 0.5km
                            val stepped = (raw * 2).toInt() / 2f
                            onDistanceChanged(stepped.coerceAtLeast(1.0f))
                        },
                        valueRange = 1f..30f
                    )

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text("1 km", style = MaterialTheme.typography.labelSmall)
                        Text("15 km", style = MaterialTheme.typography.labelSmall)
                        Text("30 km", style = MaterialTheme.typography.labelSmall)
                    }
                }
            }
        }

        Button(
            onClick = onStartGeneration,
            enabled = centerPoint != null,
            modifier = Modifier
                .fillMaxWidth()
                .height(54.dp)
        ) {
            Icon(imageVector = Icons.Default.PlayArrow, contentDescription = null)
            Spacer(modifier = Modifier.width(8.dp))
            Text("Generate Routes", style = MaterialTheme.typography.titleMedium)
        }
    }
}