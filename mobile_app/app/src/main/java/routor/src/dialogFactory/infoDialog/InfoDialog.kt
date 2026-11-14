package routor.src.dialogFactory.infoDialog

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable
fun InfoDialog(
    config: InfoDialogConfig
) {
    AlertDialog(
        onDismissRequest = {
            if (config.canDismiss == true) {
                config.onDismiss?.invoke()
            }
        },
        title = {
            Text(text = config.mainText)
        },
        text = if (config.showProgress) {
            {
                LinearProgressIndicator(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 8.dp)
                )
            }
        } else null,
        confirmButton = {},
        dismissButton = {
            if (config.canDismiss == true && config.onDismiss != null) {
                TextButton(onClick = config.onDismiss) {
                    Text("Dismiss")
                }
            }
        }
    )
}