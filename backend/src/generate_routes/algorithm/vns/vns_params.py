from dataclasses import dataclass, field


@dataclass(frozen=True)
class SamplerParams:
    """Configurable weights and geometric thresholds for candidate detour sampling."""

    approach_lock_radius_meters: float = 180.0
    lateral_bonus_weight: float = 2.2
    lateral_scale_meters: float = 500.0
    distance_fit_weight: float = 2.0
    epsilon_weight: float = 0.05
    max_sample_pool_size: int = 40
    direct_dist_epsilon: float = 1.0
    max_lateral_score: float = 3.5
    deficit_diff_scale: float = 250.0
    surplus_diff_scale: float = 150.0


@dataclass(frozen=True)
class NeighborhoodParams:
    """Hyperparameters configuring VNS neighborhood perturbations and operators."""

    max_k: int = 4
    max_detours_per_stage: int = 4
    checkpoint_shift_radius_meters: float = 200.0
    checkpoint_min_shift_distance_meters: float = 30.0


@dataclass(frozen=True)
class SmootherParams:
    """Configuration parameters for post-processing micro-spur pruning."""

    min_nodes_to_smooth: int = 10
    min_smoothed_path_nodes: int = 4
    max_lookahead_nodes: int = 8
    min_shortcut_hop_diff: int = 3
    early_path_index_threshold: int = 5
    protected_start_index_limit: int = 3
    protected_finish_offset_nodes: int = 5
    micro_spur_proximity_meters: float = 20.0
    min_distance_retention_ratio: float = 0.60
    default_fallback_edge_length: float = 1.0


@dataclass(frozen=True)
class VNSParams:
    """Configuration parameters for the Variable Neighborhood Search route generator."""

    target_distance: float
    max_iterations: int = 120
    max_stagnation_iterations: int = 15
    target_fitness: float = 0.990
    num_initial_samples: int = 3

    sampler_params: SamplerParams = field(default_factory=SamplerParams)
    neighborhood_params: NeighborhoodParams = field(default_factory=NeighborhoodParams)
    smoother_params: SmootherParams = field(default_factory=SmootherParams)
