package routor.src.dialogFactory.confirmDialog

data class ConfirmDialogConfig (
    val mainText: String,
    val hasTextField: Boolean = false,
    val textFieldShadowText: String = "",
    val baseTextState: String = "",
    val onConfirm: (String?) -> Unit,
    val onDismiss: () -> Unit
)