import logging
import math
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


@dataclass
class BoundingBox:
    DEG_LAT: float
    DEG_LON: float


class BoundingBoxEnum(Enum):
    M_25 = BoundingBox(DEG_LAT=0.000225, DEG_LON=0.00036)
    M_50 = BoundingBox(DEG_LAT=0.00045, DEG_LON=0.00072)
    M_60 = BoundingBox(DEG_LAT=0.00055, DEG_LON=0.00085)
    M_80 = BoundingBox(DEG_LAT=0.00073, DEG_LON=0.00120)


@dataclass
class EvaluatorParams:
    distance_penalty_weight: float
    overlap_penalty_weight: float

    # Bounding box for spatial overlap detection
    bounding_box: BoundingBox = field(default_factory=lambda: BoundingBoxEnum.M_80.value)

    # Minimum nodes required to evaluate path segments
    min_path_nodes_to_overlap = 3

    # Minimum along-path distance (in meters) before checking corridor overlaps.
    min_path_separation_meters = 90.0

    # Edge interpolation distance step for long edge sampling
    edge_sample_step_meters = 18.0

    # Directional conflict angular thresholds (in radians)
    antiparallel_min_rad = math.radians(140.0)

    # Maximum angular tolerance from a perpendicular connecting vector (+/- 55 deg)
    max_perpendicular_deviation_rad = math.radians(55.0)

    # Penalty multipliers
    out_and_back_penalty_multiplier = 3.0
    opposite_corridor_penalty_multiplier = 2.5

    # Distance tolerance bracket constants
    distance_tolerance_threshold = 0.20
    under_threshold_weight = 0.10
    over_threshold_weight = 1.00

    # Overlap tolerance bracket constants
    overlap_tolerance_ratio = 0.04
    overlap_under_threshold_weight = 0.10
    overlap_over_threshold_weight = 1.00

    # Spatial corridor buffer threshold
    default_corridor_threshold_meters = 80.0

    # Protected loop-closing zone around the start/finish node
    start_finish_exclusion_radius_meters = 150.0


@dataclass
class EvaluationBreakdown:
    """Detailed diagnostics of the objective function components."""

    total_distance: float
    target_distance: float
    dist_error_ratio: float
    dist_penalty_term: float
    out_and_back_meters: float
    parallel_overlap_meters: float
    total_overlap_meters: float
    overlap_penalty_term: float
    denominator: float
    fitness: float

    def log_summary(self, route_label: str = "Candidate Route") -> None:
        """Prints a structured diagnostic breakdown."""
        logger.info(
            f"\n--- [{route_label}] Fitness Breakdown ---\n"
            f"Distance: {self.total_distance:.1f}m / {self.target_distance:.1f}m "
            f"(diff: {self.dist_error_ratio * 100:.2f}%)\n"
            f"Out-and-back repeats: {self.out_and_back_meters:.1f}m\n"
            f"Parallel corridor overlaps: {self.parallel_overlap_meters:.1f}m\n"
            f"Total penalized overlap: {self.total_overlap_meters:.1f}m\n"
            f"-> Dist Penalty Term (alpha): {self.dist_penalty_term:.4f}\n"
            f"-> Overlap Penalty Term (beta): {self.overlap_penalty_term:.4f}\n"
            f"-> Denominator: {self.denominator:.4f}\n"
            f"-> Resulting Fitness: {self.fitness:.4f} ({self.fitness * 100:.2f}%)\n"
            f"----------------------------------------"
        )
