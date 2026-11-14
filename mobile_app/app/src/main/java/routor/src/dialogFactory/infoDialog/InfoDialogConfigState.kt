package routor.src.dialogFactory.infoDialog

sealed class InfoDialogConfigState {
    data object None : InfoDialogConfigState()
    data object SavingRoute : InfoDialogConfigState()
}