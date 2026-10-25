from dataclasses import dataclass, field

from src.generate_routes.algorithm.evaluator_params import BoundingBox, BoundingBoxEnum


@dataclass(frozen=True)
class WalkerParams:
    """Hyperparameters configuring ant traversal, corridor sensitivities, and limits."""

    alpha: float
    beta: float

    # Bounding-box threshold for coarse proximity checks (~60m default)
    bounding_box: BoundingBox = field(default_factory=lambda: BoundingBoxEnum.M_60.value)

    # Spatial corridor distance boundaries
    hard_proximity_dist_meters: float = 25.0
    soft_proximity_dist_meters: float = 40.0

    # Approach zone around stage checkpoints
    approach_zone_radius_meters: float = 100.0

    # Penalties and probability floors
    soft_corridor_eta_penalty: float = 0.25
    min_probability_epsilon: float = 1e-9

    # Step limit scaling
    step_limit_node_multiplier: int = 2
    min_step_limit_floor: int = 80

    # Trajectory history offsets
    min_history_for_proximity: int = 3
    history_recency_exclusion_offset: int = 3
