import logging
import math
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BudgetParams:
    """Configurable heuristics and threshold parameters for stage budget allocation."""

    # Slack damping and clamping constants
    slack_damping_factor: float = 0.5
    slack_clamp_ratio: float = 0.25

    # Budget surplus threshold for detour exploration
    ratio_to_detour_threshold: float = 1.2

    # Progress and stability offsets
    deficit_progress_boost: float = 5.0
    epsilon_offset: float = 1.0

    # Meandering and detour saturation constants
    detour_length_scale: float = 50.0
    max_detour_bonus: float = 2.5

    # Alignment directional weights
    forward_alignment_weight: float = 1.2
    backward_alignment_weight: float = 0.6

    # Angular turn thresholds and penalty weights
    shallow_turn_max_rad: float = math.radians(45.0)  # Gentle curves / straight lines
    right_angle_turn_max_rad: float = math.radians(105.0)  # Standard grid street corners
    right_angle_turn_weight: float = 0.60  # Suppresses unnecessary grid turns
    sharp_turn_weight: float = 0.20  # Heavily penalizes hairpins and sharp zig-zags
