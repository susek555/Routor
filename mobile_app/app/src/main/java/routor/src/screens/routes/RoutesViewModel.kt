package routor.src.screens.routes

import androidx.lifecycle.ViewModel
import dagger.hilt.android.lifecycle.HiltViewModel
import routor.src.data.repositories.RouteRepository
import javax.inject.Inject

@HiltViewModel
class RoutesViewModel @Inject constructor(
    routesRepository: RouteRepository
)  : ViewModel() {

    val routes = routesRepository.getAllRoutes()
}