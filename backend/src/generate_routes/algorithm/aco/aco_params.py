from dataclasses import dataclass


@dataclass
class ACOParams:
    """Configuration parameters for the Ant Colony Optimization route generator."""

    num_ants: int = 30
    num_iterations: int = 40
    alpha: float = 1.0  # Pheromone weight (tau^alpha)
    beta: float = 2.0  # Heuristic weight (eta^beta)
    evaporation_rate: float = 0.1  # Pheromone evaporation rate (rho)
    initial_pheromone: float = 1.0  # Initial pheromone value (tau_0)
    target_distance: float = 0  # Target route length in meters (L_target)
    fitness_alpha: float = 2.0  # Penalty weight for distance deviation
    fitness_beta: float = 300.0  # Penalty weight for inter-stage edge overlap
