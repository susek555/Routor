package routor.src.dialogFactory.infoDialog

data class InfoDialogConfig(
    val mainText: String,
    val showProgress: Boolean = false,
    val canDismiss: Boolean? = true,
    val onDismiss: (() -> Unit)? = null
)