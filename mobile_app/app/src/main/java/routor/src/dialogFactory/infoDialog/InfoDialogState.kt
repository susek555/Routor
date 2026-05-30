package routor.src.dialogFactory.infoDialog

import routor.src.dialogFactory.infoDialog.InfoDialogConfig


data class InfoDialogState (
    val isVisible: Boolean,
    val config: InfoDialogConfig?
)