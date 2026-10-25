from dataclasses import dataclass


@dataclass
class VNSParams:
    """Parametry sterujące algorytmem Variable Neighborhood Search."""

    target_distance: float

    # Główne pętle
    max_iterations: int = 80
    max_k: int = 4  # Skrócona, zwarta hierarchia sąsiedztw
    num_initial_samples: int = 3  # Liczba prób inicjalizacji szkieletu bazowego

    # Gęstość punktów na etap
    max_detours_per_stage: int = 4  # Maksymalna liczba punktów pośrednich na jeden etap

    # Strefy ochronne i zasięgi
    perturbation_radius_meters: float = 350.0
    checkpoint_shift_radius_meters: float = 200.0  # Promień korekty checkpointu (k=4)
    approach_lock_radius_meters: float = 180.0

    # Wagi heurystyczne ukierunkowanej losowości (Biased Randomization)
    lateral_bonus_weight: float = 2.2  # Zwiększona agresywność wypychania pętli na zewnątrz
    lateral_scale_meters: float = 500.0  # Skala odniesienia dla odchylenia bocznego (m)
    distance_fit_weight: float = 2.0  # Preferowanie węzłów redukujących deficyt
    epsilon_weight: float = 0.05
