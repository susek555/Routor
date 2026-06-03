package routor.src.screens.generations

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import routor.src.data.repositories.GenerationsRepository
import javax.inject.Inject

@HiltViewModel
class GenerationsViewModel @Inject constructor(
    private val generationsRepository: GenerationsRepository,
    @ApplicationContext private val context: Context,
) : ViewModel() {

    private val _response = MutableStateFlow("Perform request...")
    val response = _response.asStateFlow()

    fun onEvent(event: GenerationsEvent) {
        when (event) {
            GenerationsEvent.TriggerDummyTask -> {
                viewModelScope.launch {
                    _response.value = generationsRepository.triggerDummyTask().toString()
                }
            }
        }
    }
}