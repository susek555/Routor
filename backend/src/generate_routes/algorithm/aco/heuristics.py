import math

from src.generate_routes.algorithm.aco.utils.heuristics import BudgetParams
from src.generate_routes.algorithm.common_utils import (
    get_heading_rad,
    get_min_edge_length,
    get_node_coords,
    haversine,
)
from src.generate_routes.data.map import Map


def _normalize_angle_diff(angle1: float, angle2: float) -> float:
    """Calculates the absolute minimal angular difference in [0, pi] range."""
    delta = abs(angle1 - angle2)
    return 2.0 * math.pi - delta if delta > math.pi else delta


class BudgetManager:
    """Manages stage budget allocations, inter-stage slack, and transition heuristics."""

    def __init__(
        self,
        stage_graphs: list[Map],
        checkpoints: list[int],
        target_distance: float,
        params: BudgetParams,
    ) -> None:
        self.stage_graphs = stage_graphs
        self.checkpoints = checkpoints
        self.target_distance = max(target_distance, 1.0)
        self.params = params or BudgetParams()
        self.num_stages = len(checkpoints)

        # Caches to avoid redundant networkx/geodetic lookups during ant runs
        self.node_coord_cache: dict[int, tuple[float, float]] = {}
        self.edge_len_cache: dict[tuple[int, int], float] = {}

        self.base_budgets = self._calculate_base_budgets()

    def _get_coord(self, graph: Map, node: int) -> tuple[float, float]:
        """Fetches coordinates with lazy memoization."""
        if node not in self.node_coord_cache:
            self.node_coord_cache[node] = get_node_coords(graph, node)
        return self.node_coord_cache[node]

    def _get_edge_length(self, graph: Map, u: int, v: int) -> float:
        """Fetches min edge length with lazy memoization."""
        edge_key = (u, v)
        if edge_key not in self.edge_len_cache:
            self.edge_len_cache[edge_key] = get_min_edge_length(graph, u, v)
        return self.edge_len_cache[edge_key]

    def _calculate_base_budgets(self) -> list[float]:
        """Divides target_distance proportionally to straight-line checkpoint distances."""
        stage_distances: list[float] = []

        for i in range(self.num_stages):
            start_node = self.checkpoints[i]
            next_node = self.checkpoints[(i + 1) % self.num_stages]
            graph = self.stage_graphs[i]

            coord_start = self._get_coord(graph, start_node)
            coord_next = self._get_coord(graph, next_node)
            stage_distances.append(max(haversine(coord_start, coord_next), self.params.epsilon_offset))

        total_euclidean = sum(stage_distances)
        return [self.target_distance * (dist / total_euclidean) for dist in stage_distances]

    def get_effective_stage_budget(self, stage_idx: int, accumulated_slack: float) -> float:
        """Returns clamped stage budget to prevent one stage from monopolizing distance."""
        base = self.base_budgets[stage_idx]
        max_slack = self.params.slack_clamp_ratio * base
        clamped_slack = max(-max_slack, min(max_slack, accumulated_slack * self.params.slack_damping_factor))
        return base + clamped_slack

    def calculate_r(
        self,
        stage_idx: int,
        current_node: int,
        effective_budget: float,
        dist_done_in_stage: float,
    ) -> float:
        """Calculates budget surplus/deficit ratio R."""
        graph = self.stage_graphs[stage_idx]
        dest_node = self.checkpoints[(stage_idx + 1) % self.num_stages]

        coord_curr = self._get_coord(graph, current_node)
        coord_dest = self._get_coord(graph, dest_node)

        remaining_budget = effective_budget - dist_done_in_stage
        remaining_direct = max(haversine(coord_curr, coord_dest), self.params.epsilon_offset)
        return remaining_budget / remaining_direct

    def _calculate_turn_penalty(
        self,
        prev_node: int | None,
        u: int,
        v: int,
        graph: Map,
    ) -> float:
        """Calculates smooth turn inertia factor to discourage zig-zags in street grids."""
        if prev_node is None or prev_node == u:
            return 1.0

        p_coord = self._get_coord(graph, prev_node)
        u_coord = self._get_coord(graph, u)
        v_coord = self._get_coord(graph, v)

        in_heading = get_heading_rad(p_coord, u_coord)
        out_heading = get_heading_rad(u_coord, v_coord)
        delta_angle = _normalize_angle_diff(out_heading, in_heading)

        if delta_angle <= self.params.shallow_turn_max_rad:
            return 1.0
        if delta_angle <= self.params.right_angle_turn_max_rad:
            return self.params.right_angle_turn_weight
        return self.params.sharp_turn_weight

    def _calculate_deficit_eta(self, edge_len: float, progress_meters: float, dist_v_dest: float) -> float:
        """Transition attractiveness when under budget deficit (favor direct progress)."""
        if progress_meters > 0.0:
            return (progress_meters + self.params.deficit_progress_boost) / (edge_len + self.params.epsilon_offset)
        return 1.0 / (edge_len + dist_v_dest + self.params.epsilon_offset)

    def _calculate_surplus_eta(self, edge_len: float, progress_meters: float) -> float:
        """Transition attractiveness when under budget surplus (favor exploration detours)."""
        detour_bonus = min(edge_len / self.params.detour_length_scale, self.params.max_detour_bonus)
        base_attractiveness = 1.0 / (edge_len + self.params.epsilon_offset)
        alignment = (
            self.params.forward_alignment_weight if progress_meters > 0.0 else self.params.backward_alignment_weight
        )
        return base_attractiveness * detour_bonus * alignment

    def calculate_eta(
        self,
        stage_idx: int,
        u: int,
        v: int,
        budget_ratio_r: float,
        prev_node: int | None = None,
    ) -> float:
        """Calculates eta with full diagnostic information."""
        graph = self.stage_graphs[stage_idx]
        dest_node = self.checkpoints[(stage_idx + 1) % self.num_stages]

        edge_len = self._get_edge_length(graph, u, v)
        coord_u = self._get_coord(graph, u)
        coord_v = self._get_coord(graph, v)
        coord_dest = self._get_coord(graph, dest_node)

        dist_u_dest = haversine(coord_u, coord_dest)
        dist_v_dest = haversine(coord_v, coord_dest)
        progress_meters = dist_u_dest - dist_v_dest

        turn_factor = self._calculate_turn_penalty(prev_node, u, v, graph)
        is_surplus = budget_ratio_r > self.params.ratio_to_detour_threshold

        if not is_surplus:
            base_eta = self._calculate_deficit_eta(edge_len, progress_meters, dist_v_dest)
        else:
            base_eta = self._calculate_surplus_eta(edge_len, progress_meters)

        return base_eta * turn_factor
