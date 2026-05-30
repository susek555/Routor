package routor.src.dialogFactory.confirmDialog

import routor.src.dialogFactory.confirmDialog.ConfirmDialogConfig

data class ConfirmDialogState (
    val isVisible: Boolean,
    val config: ConfirmDialogConfig?
)