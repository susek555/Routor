import logging
import math
from dataclasses import dataclass

import networkx as nx

from src.generate_routes.algorithm.aco.utils import (
    get_min_edge_length,
    get_node_coords,
    haversine,
)

type Map = nx.MultiDiGraph

logger = logging.getLogger(__name__)

# Fast bounding-box angular thresholds
# Toggle between ~50m and ~25m and ~60m and ~80m depending on experimentation needs:
# DEG_LAT = 0.00045
# DEG_LON = 0.00072
# DEG_LAT = 0.000225
# DEG_LON = 0.00036
# DEG_LAT = 0.00055
# DEG_LON = 0.00090
DEG_LAT = 0.00073
DEG_LON = 0.00120


# Minimum nodes required to evaluate path segments
MIN_PATH_NODES_FOR_OVERLAP = 3

# Minimum along-path distance (in meters) before checking corridor overlaps.
MIN_PATH_SEPARATION_METERS = 90.0

# Edge interpolation distance step for long edge sampling
EDGE_SAMPLE_STEP_METERS = 18.0

# Directional conflict angular thresholds (in radians)
ANTIPARALLEL_MIN_RAD = math.radians(140.0)

# Maximum angular tolerance from a perpendicular connecting vector (+/- 55 deg)
MAX_PERPENDICULAR_DEVIATION_RAD = math.radians(55.0)

# Penalty multipliers
OUT_AND_BACK_PENALTY_MULTIPLIER = 3.0
OPPOSITE_CORRIDOR_PENALTY_MULTIPLIER = 2.5

# Distance tolerance bracket constants
DISTANCE_TOLERANCE_THRESHOLD = 0.20
UNDER_THRESHOLD_WEIGHT = 0.10
OVER_THRESHOLD_WEIGHT = 1.00

# Overlap tolerance bracket constants
OVERLAP_TOLERANCE_RATIO = 0.04
OVERLAP_UNDER_THRESHOLD_WEIGHT = 0.10
DEFAULT_FITNESS_BETA = 5.0

# Spatial corridor buffer threshold
DEFAULT_CORRIDOR_THRESHOLD_METERS = 80.0

# Protected loop-closing zone around the start/finish node
START_FINISH_EXCLUSION_RADIUS_METERS = 150.0


def _get_heading_rad(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    """Calculates directional heading angle in radians from point 1 to point 2."""
    lat1, lon1 = p1
    lat2, lon2 = p2
    return math.atan2(lat2 - lat1, lon2 - lon1)


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


class RouteEvaluator:
    """Evaluates the global fitness of a candidate loop with spatial overlap detection."""

    def __init__(
        self,
        stage_graphs: list[Map],
        target_distance: float,
        fitness_alpha: float = 2.0,
        fitness_beta: float = DEFAULT_FITNESS_BETA,
        corridor_threshold_meters: float = DEFAULT_CORRIDOR_THRESHOLD_METERS,
        distance_tolerance_ratio: float = DISTANCE_TOLERANCE_THRESHOLD,
    ):
        self.stage_graphs = stage_graphs
        self.target_distance = max(target_distance, 1.0)
        self.alpha = fitness_alpha
        self.beta = fitness_beta
        self.corridor_threshold = corridor_threshold_meters
        self.dist_tolerance_ratio = distance_tolerance_ratio
        self.overlap_tolerance_ratio = OVERLAP_TOLERANCE_RATIO

        self.edge_info_cache: dict[tuple[int, int], tuple[list[tuple[float, float]], float]] = {}
        self.node_coord_cache: dict[int, tuple[float, float]] = {}
        self._build_edge_cache()

    def _interpolate_edge_points(
        self,
        c_u: tuple[float, float],
        c_v: tuple[float, float],
        edge_len: float,
    ) -> list[tuple[float, float]]:
        """Generates equidistant sample points along an edge to prevent missing long segments."""
        if edge_len <= EDGE_SAMPLE_STEP_METERS:
            return [((c_u[0] + c_v[0]) / 2.0, (c_u[1] + c_v[1]) / 2.0)]

        num_samples = max(2, int(edge_len / EDGE_SAMPLE_STEP_METERS))
        points: list[tuple[float, float]] = []
        for i in range(1, num_samples):
            fraction = i / float(num_samples)
            lat = c_u[0] + fraction * (c_v[0] - c_u[0])
            lon = c_u[1] + fraction * (c_v[1] - c_u[1])
            points.append((lat, lon))
        return points

    def _build_edge_cache(self) -> None:
        """Precomputes sample points and lengths for all edges across stage graphs."""
        for graph in self.stage_graphs:
            for node in graph.nodes():
                if node not in self.node_coord_cache:
                    self.node_coord_cache[node] = get_node_coords(graph, node)

            for u, v in graph.edges():
                if (u, v) in self.edge_info_cache:
                    continue
                edge_len = get_min_edge_length(graph, u, v)

                c_u = self.node_coord_cache[u]
                c_v = self.node_coord_cache[v]
                samples = self._interpolate_edge_points(c_u, c_v, edge_len)

                self.edge_info_cache[(u, v)] = (samples, edge_len)
                self.edge_info_cache[(v, u)] = (samples, edge_len)

    def _is_near_start_finish(
        self,
        point: tuple[float, float],
        start_coord: tuple[float, float],
    ) -> bool:
        """Checks if a point is located within the loop closing zone."""
        return haversine(point, start_coord) <= START_FINISH_EXCLUSION_RADIUS_METERS

    def _is_edge_in_exclusion_zone(
        self,
        samples: list[tuple[float, float]],
        start_coord: tuple[float, float],
    ) -> bool:
        """Krawędź uważa się za chronioną, jeśli jakakolwiek jej próbka leży w strefie start/meta."""
        return any(self._is_near_start_finish(pt, start_coord) for pt in samples)

    def _is_perpendicular_corridor(
        self,
        sample_pt: tuple[float, float],
        prev_pt: tuple[float, float],
        curr_heading: float,
    ) -> bool:
        """Checks if the vector connecting both points is perpendicular to the heading."""
        connector_heading = _get_heading_rad(prev_pt, sample_pt)
        angle_to_connector = abs(curr_heading - connector_heading)
        if angle_to_connector > math.pi:
            angle_to_connector = 2.0 * math.pi - angle_to_connector

        cross_angle = abs(angle_to_connector - (math.pi / 2.0))
        return cross_angle < MAX_PERPENDICULAR_DEVIATION_RAD

    def _check_sample_conflict(
        self,
        sample_pt: tuple[float, float],
        curr_heading: float,
        history: list[tuple[tuple[float, float], float, float, bool]],
        curr_dist: float,
        start_coord: tuple[float, float],
    ) -> float | None:
        """Checks spatial overlap against history ONLY for genuine anti-parallel reverse corridors."""
        # 1. Bieżący punkt w strefie ochronnej -> brak kary
        if self._is_near_start_finish(sample_pt, start_coord):
            return None

        lat_m, lon_m = sample_pt
        for (prev_lat, prev_lon), prev_heading, prev_cum_dist, prev_in_zone in history:
            # 2. Jeśli punkt z historii leżał w strefie start/meta -> nie może generować konfliktu
            if prev_in_zone:
                continue

            # 3. Zabezpieczenie przed ostrymi skrętami i skrzyżowaniami
            if (curr_dist - prev_cum_dist) < MIN_PATH_SEPARATION_METERS:
                continue

            if abs(lat_m - prev_lat) < DEG_LAT and abs(lon_m - prev_lon) < DEG_LON:
                if haversine(sample_pt, (prev_lat, prev_lon)) < self.corridor_threshold:
                    delta_heading = abs(curr_heading - prev_heading)
                    if delta_heading > math.pi:
                        delta_heading = 2.0 * math.pi - delta_heading

                    # Anti-parallel movement (>= 140 deg)
                    if delta_heading >= ANTIPARALLEL_MIN_RAD:
                        if self._is_perpendicular_corridor(sample_pt, (prev_lat, prev_lon), curr_heading):
                            return OPPOSITE_CORRIDOR_PENALTY_MULTIPLIER
        return None

    def calculate_overlap_details(self, full_path: list[int]) -> tuple[float, float]:
        """Calculates out-and-back and wide corridor overlap penalties using discretized samples."""
        if len(full_path) < MIN_PATH_NODES_FOR_OVERLAP:
            return 0.0, 0.0

        # Rzeczywisty punkt startowy brany z węzła początkowego trasy
        start_node = full_path[0]
        start_coord = self.node_coord_cache.get(start_node)
        if not start_coord:
            first_samples, _ = self.edge_info_cache.get((full_path[0], full_path[1]), ([(0.0, 0.0)], 1.0))
            start_coord = first_samples[0]

        out_and_back_meters = 0.0
        parallel_overlap_meters = 0.0

        visited_edges: set[frozenset[int]] = set()
        # Historia: (współrzędne, azymut, kumulatywny_dystans, czy_w_strefie_start_meta)
        history: list[tuple[tuple[float, float], float, float, bool]] = []
        current_cumulative_dist = 0.0

        for i in range(len(full_path) - 1):
            u, v = full_path[i], full_path[i + 1]
            if u == v:
                continue

            edge_key = frozenset((u, v))
            samples, edge_len = self.edge_info_cache.get((u, v), ([(0.0, 0.0)], 1.0))

            c_u = self.node_coord_cache.get(u, (0.0, 0.0))
            c_v = self.node_coord_cache.get(v, (0.0, 0.0))
            curr_heading = _get_heading_rad(c_u, c_v)

            is_edge_protected = self._is_edge_in_exclusion_zone(samples, start_coord)

            # 1. Bezwzględne powtórzenie topologiczne (Out-and-back)
            if edge_key in visited_edges:
                # NALICZAJ TYLKO JEŚLI KRAWĘDŹ JEST POZA STREFĄ START/META
                if not is_edge_protected:
                    out_and_back_meters += edge_len * OUT_AND_BACK_PENALTY_MULTIPLIER
            else:
                # 2. Korytarz przeciwbieżny
                if not is_edge_protected:
                    for pt in samples:
                        penalty_mult = self._check_sample_conflict(
                            pt, curr_heading, history, current_cumulative_dist, start_coord
                        )
                        if penalty_mult is not None:
                            parallel_overlap_meters += edge_len * penalty_mult
                            break

            visited_edges.add(edge_key)
            for pt in samples:
                in_zone = self._is_near_start_finish(pt, start_coord)
                history.append((pt, curr_heading, current_cumulative_dist, in_zone))

            current_cumulative_dist += edge_len

        return out_and_back_meters, parallel_overlap_meters

    def _calculate_marginal_distance_penalty(self, raw_diff_ratio: float) -> float:
        """Calculates bracketed distance penalty with tolerance window."""
        if raw_diff_ratio <= self.dist_tolerance_ratio:
            return raw_diff_ratio * UNDER_THRESHOLD_WEIGHT

        base_bracket = self.dist_tolerance_ratio * UNDER_THRESHOLD_WEIGHT
        excess = raw_diff_ratio - self.dist_tolerance_ratio
        return base_bracket + (excess * OVER_THRESHOLD_WEIGHT)

    def _calculate_marginal_overlap_penalty(self, raw_overlap_ratio: float) -> float:
        """Calculates bracketed overlap penalty forgiving minor network intersections."""
        if raw_overlap_ratio <= self.overlap_tolerance_ratio:
            return raw_overlap_ratio * OVERLAP_UNDER_THRESHOLD_WEIGHT

        base_bracket = self.overlap_tolerance_ratio * OVERLAP_UNDER_THRESHOLD_WEIGHT
        excess = raw_overlap_ratio - self.overlap_tolerance_ratio
        return base_bracket + excess

    def evaluate_with_breakdown(
        self,
        full_path: list[int],
        total_distance: float,
    ) -> EvaluationBreakdown:
        """Returns comprehensive diagnostic metrics of the fitness calculation."""
        if not full_path or full_path[0] != full_path[-1]:
            return EvaluationBreakdown(
                total_distance=total_distance,
                target_distance=self.target_distance,
                dist_error_ratio=1.0,
                dist_penalty_term=0.0,
                out_and_back_meters=0.0,
                parallel_overlap_meters=0.0,
                total_overlap_meters=0.0,
                overlap_penalty_term=0.0,
                denominator=float("inf"),
                fitness=0.0,
            )

        raw_diff_ratio = abs(total_distance - self.target_distance) / self.target_distance
        effective_dist_penalty = self._calculate_marginal_distance_penalty(raw_diff_ratio)
        dist_penalty_term = self.alpha * effective_dist_penalty

        out_and_back, parallel = self.calculate_overlap_details(full_path)
        total_overlap = out_and_back + parallel
        raw_overlap_ratio = total_overlap / self.target_distance
        effective_overlap_penalty = self._calculate_marginal_overlap_penalty(raw_overlap_ratio)
        overlap_penalty_term = self.beta * effective_overlap_penalty

        denominator = 1.0 + dist_penalty_term + overlap_penalty_term
        fitness = float(1.0 / denominator)

        return EvaluationBreakdown(
            total_distance=total_distance,
            target_distance=self.target_distance,
            dist_error_ratio=raw_diff_ratio,
            dist_penalty_term=dist_penalty_term,
            out_and_back_meters=out_and_back,
            parallel_overlap_meters=parallel,
            total_overlap_meters=total_overlap,
            overlap_penalty_term=overlap_penalty_term,
            denominator=denominator,
            fitness=fitness,
        )

    def evaluate(
        self,
        full_path: list[int],
        traversed_edges: list[frozenset[int]] | None = None,
        total_distance: float = 0.0,
    ) -> float:
        """Calculates normalized global fitness score."""
        return self.evaluate_with_breakdown(full_path, total_distance).fitness
