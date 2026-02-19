package routor.src.dialogFactory.confirmDialog

import routor.src.dialogFactory.confirmDialog.ConfirmDialogConfig
import routor.src.dialogFactory.confirmDialog.ConfirmDialogConfigState
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class ConfirmDialogFactory @Inject constructor() {
    fun create(
        state: ConfirmDialogConfigState,
        onConfirm: (String?) -> Unit,
        onDismiss: () -> Unit,
        routeName: String? = "[ unknown ]",
        baseTextState: String? = ""
    ) : ConfirmDialogConfig? {
        return when(state) {
            ConfirmDialogConfigState.RouteAskForName -> ConfirmDialogConfig(
                mainText = "Enter name for this route",
                hasTextField = true,
                textFieldShadowText = "Name...",
                onConfirm = onConfirm,
                onDismiss = onDismiss
            )
            ConfirmDialogConfigState.RouteNotLongEnough -> ConfirmDialogConfig(
                mainText = "Route is not long enough",
                onConfirm = onConfirm,
                onDismiss = onDismiss
            )
            ConfirmDialogConfigState.EditRoute -> ConfirmDialogConfig(
                mainText = "Change name of this route",
                hasTextField = true,
                textFieldShadowText = "Name...",
                baseTextState = baseTextState!!,
                onConfirm = onConfirm,
                onDismiss = onDismiss
            )
            ConfirmDialogConfigState.DeleteRoute -> ConfirmDialogConfig(
                mainText = "Are you sure you want to delete route named $routeName",
                onConfirm = onConfirm,
                onDismiss = onDismiss
            )
            ConfirmDialogConfigState.None -> null
        }
    }
}