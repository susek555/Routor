package routor.src.dialogFactory.infoDialog

import kotlinx.coroutines.flow.Flow

data class InfoDialogConfig (
    val mainText: String,
    val canDismiss: Boolean? = true,
    val onDismiss: (() -> Unit)? = null
)