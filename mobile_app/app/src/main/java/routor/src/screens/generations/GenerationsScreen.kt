package routor.src.screens.generations

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier

@Composable
fun GenerateScreen(
    displayMainScreen: () -> Unit,
    viewModel: GenerationsViewModel
) {
    val response = viewModel.response.collectAsState()
    val notification = viewModel.notification.collectAsState()

    Scaffold(
        floatingActionButton = {
            FloatingActionButton(
                onClick = displayMainScreen
            ) {
                Text("BACK")
            }
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
        ) {
            Button(
                onClick = {
                        viewModel.onEvent(GenerationsEvent.TriggerDummyTask)
                    }
            ) {
                Text("Test API connection")
            }

            Text(
                text = response.value
            )


            Text(
                text = notification.value
            )
        }
    }
}