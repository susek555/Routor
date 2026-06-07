package routor.src.screens.main

import org.maplibre.android.geometry.LatLng
import routor.src.data.types.RouteStats
import routor.src.dialogFactory.confirmDialog.ConfirmDialogState

data class MainScreenUiState(
    val currentLocation: LatLng? = null,
    val routeStats: RouteStats = RouteStats(),
    val duration: Long = 0L,
    val isRecording: Boolean = false,
    val dialogState: ConfirmDialogState = ConfirmDialogState(false, null)
)
