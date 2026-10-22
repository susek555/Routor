import math

from src.generate_routes.algorithm.aco.utils.common import (
    get_min_edge_length,
    get_node_coords,
    haversine,
)
from src.generate_routes.data.map import Map

# Slack damping and clamping constants
SLACK_DAMPING_FACTOR = 0.5
SLACK_CLAMP_RATIO = 0.25

# Budget surplus threshold for detour exploration
RATIO_TO_DETOUR_THRESHOLD = 1.2

# Progress and stability offsets
DEFICIT_PROGRESS_BOOST = 5.0
EPSILON_OFFSET = 1.0

# Meandering and detour saturation constants
DETOUR_LENGTH_SCALE = 50.0
MAX_DETOUR_BONUS = 2.5

# Alignment directional weights
FORWARD_ALIGNMENT_WEIGHT = 1.2
BACKWARD_ALIGNMENT_WEIGHT = 0.6

# Angular turn thresholds and penalty multipliers
SHALLOW_TURN_MAX_RAD = math.radians(45.0)  # Up to 45 deg: straight or gentle curve
RIGHT_ANGLE_TURN_MAX_RAD = math.radians(105.0)  # Up to 105 deg: street corners
RIGHT_ANGLE_TURN_WEIGHT = 0.60  # Suppresses unnecessary grid turns
SHARP_TURN_WEIGHT = 0.20  # Heavily penalizes hairpins and zig-zags


class BudgetManager:
    """Manages stage budget allocations, inter-stage slack, and transition heuristics."""

    def __init__(
        self,
        stage_graphs: list[Map],
        checkpoints: list[int],
        target_distance: float,
    ):
        self.stage_graphs = stage_graphs
        self.checkpoints = checkpoints
        self.target_distance = target_distance
        self.num_stages = len(checkpoints)

        self.base_budgets = self._calculate_base_budgets()

    def _calculate_base_budgets(self) -> list[float]:
        """Divides target_distance proportionally to straight-line checkpoint distances."""
        stage_distances: list[float] = []

        for i in range(self.num_stages):
            start_node = self.checkpoints[i]
            next_node = self.checkpoints[(i + 1) % self.num_stages]
            graph = self.stage_graphs[i]

            coord_start = get_node_coords(graph, start_node)
            coord_next = get_node_coords(graph, next_node)
            stage_distances.append(max(haversine(coord_start, coord_next), EPSILON_OFFSET))

        total_euclidean = sum(stage_distances)
        return [self.target_distance * (dist / total_euclidean) for dist in stage_distances]

    def get_effective_stage_budget(self, stage_idx: int, accumulated_slack: float) -> float:
        """Returns clamped stage budget to prevent one stage from monopolizing distance."""
        base = self.base_budgets[stage_idx]
        max_slack = SLACK_CLAMP_RATIO * base
        clamped_slack = max(-max_slack, min(max_slack, accumulated_slack * SLACK_DAMPING_FACTOR))
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

        coord_curr = get_node_coords(graph, current_node)
        coord_dest = get_node_coords(graph, dest_node)

        remaining_budget = effective_budget - dist_done_in_stage
        remaining_direct = max(haversine(coord_curr, coord_dest), EPSILON_OFFSET)
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

        p_lat, p_lon = get_node_coords(graph, prev_node)
        u_lat, u_lon = get_node_coords(graph, u)
        v_lat, v_lon = get_node_coords(graph, v)

        # Incoming and outgoing heading angles
        in_heading = math.atan2(u_lat - p_lat, u_lon - p_lon)
        out_heading = math.atan2(v_lat - u_lat, v_lon - u_lon)

        delta_angle = abs(out_heading - in_heading)
        if delta_angle > math.pi:
            delta_angle = 2 * math.pi - delta_angle

        if delta_angle <= SHALLOW_TURN_MAX_RAD:
            return 1.0
        if delta_angle <= RIGHT_ANGLE_TURN_MAX_RAD:
            return RIGHT_ANGLE_TURN_WEIGHT
        return SHARP_TURN_WEIGHT

    def calculate_eta(
        self,
        stage_idx: int,
        u: int,
        v: int,
        budget_ratio_r: float,
        prev_node: int | None = None,
    ) -> float:
        """Computes transition attractiveness eta with meandering and turn continuity penalties."""
        graph = self.stage_graphs[stage_idx]
        dest_node = self.checkpoints[(stage_idx + 1) % self.num_stages]
        edge_len = get_min_edge_length(graph, u, v)

        coord_u = get_node_coords(graph, u)
        coord_v = get_node_coords(graph, v)
        coord_dest = get_node_coords(graph, dest_node)

        dist_u_dest = haversine(coord_u, coord_dest)
        dist_v_dest = haversine(coord_v, coord_dest)
        progress_meters = dist_u_dest - dist_v_dest

        turn_factor = self._calculate_turn_penalty(prev_node, u, v, graph)

        # 1. Deficit or final phase: head towards destination
        if budget_ratio_r <= RATIO_TO_DETOUR_THRESHOLD:
            if progress_meters > 0:
                base_eta = (progress_meters + DEFICIT_PROGRESS_BOOST) / (edge_len + EPSILON_OFFSET)
            else:
                base_eta = 1.0 / (edge_len + dist_v_dest + EPSILON_OFFSET)
            return base_eta * turn_factor

        # 2. Budget surplus: controlled detours, penalized sharp turns
        detour_bonus = min(edge_len / DETOUR_LENGTH_SCALE, MAX_DETOUR_BONUS)
        base_attractiveness = 1.0 / (edge_len + EPSILON_OFFSET)
        alignment = FORWARD_ALIGNMENT_WEIGHT if progress_meters > 0 else BACKWARD_ALIGNMENT_WEIGHT

        return base_attractiveness * detour_bonus * alignment * turn_factor
