package routor.src.screens.generations

sealed interface GenerationsEvent {
    data object TriggerDummyTask: GenerationsEvent
}