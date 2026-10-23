import math

from src.generate_routes.algorithm.aco.utils.common import (
    get_heading_rad,
    get_min_edge_length,
    get_node_coords,
    haversine,
)
from src.generate_routes.algorithm.aco.utils.evaluator import EvaluationBreakdown, EvaluatorParams
from src.generate_routes.data.map import Map


class RouteEvaluator:
    """Evaluates the global fitness of a candidate loop with spatial overlap detection."""

    def __init__(
        self,
        stage_graphs: list[Map],
        target_distance: float,
        params: EvaluatorParams,
    ):
        self.stage_graphs = stage_graphs
        self.target_distance = max(target_distance, 1.0)
        self.params = params

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
        if edge_len <= self.params.edge_sample_step_meters:
            return [((c_u[0] + c_v[0]) / 2.0, (c_u[1] + c_v[1]) / 2.0)]

        num_samples = max(2, int(edge_len / self.params.edge_sample_step_meters))
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
        return haversine(point, start_coord) <= self.params.start_finish_exclusion_radius_meters

    def _is_edge_in_exclusion_zone(
        self,
        samples: list[tuple[float, float]],
        start_coord: tuple[float, float],
    ) -> bool:
        """An edge is considered protected if any of its samples lies within the start/finish zone."""
        return any(self._is_near_start_finish(pt, start_coord) for pt in samples)

    def _is_perpendicular_corridor(
        self,
        sample_pt: tuple[float, float],
        prev_pt: tuple[float, float],
        curr_heading: float,
    ) -> bool:
        """Checks if the vector connecting both points is perpendicular to the heading."""
        connector_heading = get_heading_rad(prev_pt, sample_pt)
        angle_to_connector = abs(curr_heading - connector_heading)
        if angle_to_connector > math.pi:
            angle_to_connector = 2.0 * math.pi - angle_to_connector

        cross_angle = abs(angle_to_connector - (math.pi / 2.0))
        return cross_angle < self.params.max_perpendicular_deviation_rad

    def _check_sample_conflict(
        self,
        sample_pt: tuple[float, float],
        curr_heading: float,
        history: list[tuple[tuple[float, float], float, float, bool]],
        curr_dist: float,
        start_coord: tuple[float, float],
    ) -> float | None:
        """Checks spatial overlap against history ONLY for genuine anti-parallel reverse corridors."""
        # 1. Current point inside protected zone -> no penalty
        if self._is_near_start_finish(sample_pt, start_coord):
            return None

        lat_m, lon_m = sample_pt
        for (prev_lat, prev_lon), prev_heading, prev_cum_dist, prev_in_zone in history:
            # 2. If the historical point was in the start/finish zone -> it cannot generate a conflict
            if prev_in_zone:
                continue

            # 3. Guard against sharp turns and tight intersections
            if (curr_dist - prev_cum_dist) < self.params.min_path_separation_meters:
                continue

            if (
                abs(lat_m - prev_lat) < self.params.bounding_box.DEG_LAT
                and abs(lon_m - prev_lon) < self.params.bounding_box.DEG_LON
            ):
                if haversine(sample_pt, (prev_lat, prev_lon)) < self.params.default_corridor_threshold_meters:
                    delta_heading = abs(curr_heading - prev_heading)
                    if delta_heading > math.pi:
                        delta_heading = 2.0 * math.pi - delta_heading

                    # Anti-parallel movement
                    if delta_heading >= self.params.antiparallel_min_rad:
                        if self._is_perpendicular_corridor(sample_pt, (prev_lat, prev_lon), curr_heading):
                            return self.params.opposite_corridor_penalty_multiplier
        return None

    def _resolve_start_coord(self, full_path: list[int]) -> tuple[float, float]:
        """Resolves the start coordinate from cache or falls back to the first sample of the first edge."""
        start_coord = self.node_coord_cache.get(full_path[0])
        if start_coord:
            return start_coord

        first_samples, _ = self.edge_info_cache.get((full_path[0], full_path[1]), ([(0.0, 0.0)], 1.0))
        return first_samples[0]

    def _find_parallel_penalty(
        self,
        samples: list[tuple[float, float]],
        curr_heading: float,
        history: list[tuple[tuple[float, float], float, float, bool]],
        current_cumulative_dist: float,
        start_coord: tuple[float, float],
    ) -> float | None:
        """Returns the penalty multiplier on the first detected conflict within edge samples."""
        for pt in samples:
            penalty_mult = self._check_sample_conflict(pt, curr_heading, history, current_cumulative_dist, start_coord)
            if penalty_mult is not None:
                return penalty_mult
        return None

    def calculate_overlap_details(self, full_path: list[int]) -> tuple[float, float]:
        """Calculates out-and-back and wide corridor overlap penalties using discretized samples."""
        if len(full_path) < self.params.min_path_nodes_to_overlap:
            return 0.0, 0.0

        # Actual starting point resolved from the route's initial node
        start_coord = self._resolve_start_coord(full_path)

        out_and_back_meters = 0.0
        parallel_overlap_meters = 0.0

        visited_edges: set[frozenset[int]] = set()
        # History: (coordinates, heading, cumulative_distance, is_in_start_finish_zone)
        history: list[tuple[tuple[float, float], float, float, bool]] = []
        current_cumulative_dist = 0.0

        for u, v in zip(full_path, full_path[1:], strict=False):
            if u == v:
                continue

            edge_key = frozenset((u, v))
            samples, edge_len = self.edge_info_cache.get((u, v), ([(0.0, 0.0)], 1.0))

            c_u = self.node_coord_cache.get(u, (0.0, 0.0))
            c_v = self.node_coord_cache.get(v, (0.0, 0.0))
            curr_heading = get_heading_rad(c_u, c_v)

            is_edge_protected = self._is_edge_in_exclusion_zone(samples, start_coord)

            # Penalize only if the edge is outside the protected start/finish zone
            if not is_edge_protected:
                # 1. Absolute topological repetition (Out-and-back)
                if edge_key in visited_edges:
                    out_and_back_meters += edge_len * self.params.out_and_back_penalty_multiplier
                else:
                    penalty_mult = self._find_parallel_penalty(
                        samples, curr_heading, history, current_cumulative_dist, start_coord
                    )
                    if penalty_mult is not None:
                        parallel_overlap_meters += edge_len * penalty_mult

            visited_edges.add(edge_key)
            for pt in samples:
                in_zone = self._is_near_start_finish(pt, start_coord)
                history.append((pt, curr_heading, current_cumulative_dist, in_zone))

            current_cumulative_dist += edge_len

        return out_and_back_meters, parallel_overlap_meters

    def _calculate_marginal_distance_penalty(self, raw_diff_ratio: float) -> float:
        """Calculates bracketed distance penalty with tolerance window."""
        if raw_diff_ratio <= self.params.distance_tolerance_threshold:
            return raw_diff_ratio * self.params.under_threshold_weight

        base_bracket = self.params.distance_tolerance_threshold * self.params.under_threshold_weight
        excess = raw_diff_ratio - self.params.distance_tolerance_threshold
        return base_bracket + (excess * self.params.over_threshold_weight)

    def _calculate_marginal_overlap_penalty(self, raw_overlap_ratio: float) -> float:
        """Calculates bracketed overlap penalty forgiving minor network intersections."""
        if raw_overlap_ratio <= self.params.overlap_tolerance_ratio:
            return raw_overlap_ratio * self.params.overlap_under_threshold_weight

        base_bracket = self.params.overlap_tolerance_ratio * self.params.overlap_under_threshold_weight
        excess = raw_overlap_ratio - self.params.overlap_tolerance_ratio
        return base_bracket + (excess * self.params.overlap_over_threshold_weight)

    def evaluate_with_breakdown(
        self,
        full_path: list[int],
        total_distance: float,
    ) -> EvaluationBreakdown:
        """Returns a detailed breakdown of the fitness evaluation for a candidate route."""
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
        dist_penalty_term = self.params.distance_penalty_weight * effective_dist_penalty

        out_and_back, parallel = self.calculate_overlap_details(full_path)
        total_overlap = out_and_back + parallel
        raw_overlap_ratio = total_overlap / self.target_distance
        effective_overlap_penalty = self._calculate_marginal_overlap_penalty(raw_overlap_ratio)
        overlap_penalty_term = self.params.overlap_penalty_weight * effective_overlap_penalty

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
        total_distance: float = 0.0,
    ) -> float:
        """Calculates normalized global fitness score."""
        return self.evaluate_with_breakdown(full_path, total_distance).fitness
