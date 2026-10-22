from dataclasses import dataclass, field

from src.generate_routes.algorithm.aco.utils.evaluator import EvaluatorParams

DEFAULT_FITNESS_DISTANCE_PENALTY = 2.0
DEFAULT_FITNESS_OVERLAP_PENALTY = 3.0


@dataclass
class ACOParams:
    """Configuration parameters for the Ant Colony Optimization route generator."""

    num_ants: int = 15
    num_iterations: int = 10
    alpha: float = 1.0  # Pheromone weight (tau^alpha)
    beta: float = 2.0  # Heuristic weight (eta^beta)
    evaporation_rate: float = 0.15  # Pheromone evaporation rate (rho)
    initial_pheromone: float = 1.0  # Initial pheromone value (tau_0)
    target_distance: float = 0  # Target route length in meters (L_target)
    fitness_distance_penalty: float = DEFAULT_FITNESS_DISTANCE_PENALTY  # Penalty weight for distance deviation
    fitness_overlap_penalty: float = DEFAULT_FITNESS_OVERLAP_PENALTY  # Penalty weight for inter-stage edge overlap
    evaluator_params: EvaluatorParams = field(
        default_factory=lambda: EvaluatorParams(
            distance_penalty_weight=DEFAULT_FITNESS_DISTANCE_PENALTY,
            overlap_penalty_weight=DEFAULT_FITNESS_OVERLAP_PENALTY,
        )
    )
