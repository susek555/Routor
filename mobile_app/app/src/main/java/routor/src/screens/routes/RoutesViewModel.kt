package routor.src.screens.routes

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import routor.src.data.repositories.RouteRepository
import routor.src.data.types.Route
import javax.inject.Inject

@HiltViewModel
class RoutesViewModel @Inject constructor(
    private val routesRepository: RouteRepository
)  : ViewModel() {

    private val _routes = MutableStateFlow<List<Route>>(emptyList())
    val routes: StateFlow<List<Route>> = _routes.asStateFlow()

    init {
        loadRoutes()
    }

    private fun loadRoutes() {
        viewModelScope.launch {
            _routes.value = routesRepository.getAllRoutes()
        }
    }
}