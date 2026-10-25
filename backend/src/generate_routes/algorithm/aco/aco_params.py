from dataclasses import dataclass, field

from src.generate_routes.algorithm.aco.utils.heuristics import BudgetParams
from src.generate_routes.algorithm.aco.utils.stage_walker import WalkerParams
from src.generate_routes.algorithm.evaluator_params import EvaluatorParams

DEFAULT_FITNESS_DISTANCE_PENALTY = 2.0
DEFAULT_FITNESS_OVERLAP_PENALTY = 3.0

DEFAULT_ALPHA = 1.0
DEFAULT_BETA = 2.0


@dataclass
class ACOParams:
    """Configuration parameters for the Ant Colony Optimization route generator."""

    num_ants: int = 15
    num_iterations: int = 10
    alpha: float = DEFAULT_ALPHA  # Pheromone weight (tau^alpha)
    beta: float = DEFAULT_BETA  # Heuristic weight (eta^beta)
    evaporation_rate: float = 0.15  # Pheromone evaporation rate (rho)
    initial_pheromone: float = 1.0  # Initial pheromone value (tau_0)
    target_distance: float = 0  # Target route length in meters (L_target)
    fitness_distance_penalty: float = DEFAULT_FITNESS_DISTANCE_PENALTY  # Penalty weight for distance deviation
    fitness_overlap_penalty: float = DEFAULT_FITNESS_OVERLAP_PENALTY  # Penalty weight for inter-stage edge overlap
    pheromone_deposit_multiplier: float = 2.0  # Pheromone deposit multiplier applied to positive route fitness
    warm_start_seed_multiplier: float = 1.5  # Initial baseline shortest path pheromone multiplier
    # Inter-stage slack damping and absolute clamping constraints
    inter_stage_slack_damping: float = 0.4
    max_inter_stage_slack_meters: float = 250.0
    evaluator_params: EvaluatorParams = field(
        default_factory=lambda: EvaluatorParams(
            distance_penalty_weight=DEFAULT_FITNESS_DISTANCE_PENALTY,
            overlap_penalty_weight=DEFAULT_FITNESS_OVERLAP_PENALTY,
        )
    )
    heuristics_params: BudgetParams = field(default_factory=BudgetParams)
    walker_params: WalkerParams = field(default_factory=lambda: WalkerParams(alpha=DEFAULT_ALPHA, beta=DEFAULT_BETA))
