package routor.src.dialogFactory.infoDialog

class InfoDialogFactory {
    fun create(
        state: InfoDialogConfigState,
        onDismiss: (() -> Unit)? = null,
        routeName: String? = "[ unknown ]",
        errorMessage: String? = ""
    ): InfoDialogConfig? {
        return when (state) {
            InfoDialogConfigState.None -> null
            InfoDialogConfigState.SavingRoute -> InfoDialogConfig(
                mainText = "Saving route...",
                showProgress = true,
                canDismiss = false,
                onDismiss = null
            )
        }
    }
}