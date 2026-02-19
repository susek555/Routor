package routor.src.dialogFactory.confirmDialog

sealed class ConfirmDialogConfigState {
    data object None: ConfirmDialogConfigState()
    data object RouteNotLongEnough: ConfirmDialogConfigState()
    data object RouteAskForName: ConfirmDialogConfigState()
    data object EditRoute: ConfirmDialogConfigState()
    data object DeleteRoute: ConfirmDialogConfigState()
}