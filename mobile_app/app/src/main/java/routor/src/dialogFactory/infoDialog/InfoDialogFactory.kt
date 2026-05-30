package routor.src.dialogFactory.infoDialog

import kotlinx.coroutines.flow.Flow
import routor.src.dialogFactory.infoDialog.InfoDialogConfig
import routor.src.dialogFactory.infoDialog.InfoDialogConfigState

class InfoDialogFactory {
    fun create(
        state: InfoDialogConfigState,
        onDismiss: (() -> Unit)? = null,
        routeName: String? = "[ unknown ]",
        errorMessage: String? = ""
    ) : InfoDialogConfig? {
        return when(state) {
            InfoDialogConfigState.None -> null
        }
    }
}