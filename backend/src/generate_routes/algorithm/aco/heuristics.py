from src.generate_routes.algorithm.aco.utils import (
    get_min_edge_length,
    get_node_coords,
    haversine,
)
from src.generate_routes.data.map import Map

# Slack clamping and damping constants
SLACK_DAMPING_FACTOR = 0.5
SLACK_CLAMP_RATIO = 0.25

# Budget surplus threshold for detour exploration
RATIO_TO_DETOUR_THRESHOLD = 1.2

# Progress and stability offsets for deficit heuristics
DEFICIT_PROGRESS_BOOST = 5.0
EPSILON_OFFSET = 1.0

# Meandering and detour saturation constants
DETOUR_LENGTH_SCALE = 50.0
MAX_DETOUR_BONUS = 2.5

# Alignment directional weights
FORWARD_ALIGNMENT_WEIGHT = 1.2
BACKWARD_ALIGNMENT_WEIGHT = 0.6


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
        # Restrict slack influence to at most +/- 25% of this stage's base budget
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

    def calculate_eta(
        self,
        stage_idx: int,
        u: int,
        v: int,
        budget_ratio_r: float,
    ) -> float:
        """Computes transition attractiveness eta with smooth meandering distribution."""
        graph = self.stage_graphs[stage_idx]
        dest_node = self.checkpoints[(stage_idx + 1) % self.num_stages]
        edge_len = get_min_edge_length(graph, u, v)

        coord_u = get_node_coords(graph, u)
        coord_v = get_node_coords(graph, v)
        coord_dest = get_node_coords(graph, dest_node)

        dist_u_dest = haversine(coord_u, coord_dest)
        dist_v_dest = haversine(coord_v, coord_dest)
        progress_meters = dist_u_dest - dist_v_dest

        # 1. Deficit or final stage budget phase: prioritize heading directly toward destination
        if budget_ratio_r <= RATIO_TO_DETOUR_THRESHOLD:
            if progress_meters > 0:
                return (progress_meters + DEFICIT_PROGRESS_BOOST) / (edge_len + EPSILON_OFFSET)
            return 1.0 / (edge_len + dist_v_dest + EPSILON_OFFSET)

        # 2. Budget surplus: do not encourage "the longer the better" infinitely
        # Use a balanced metric: slight bonus for detours while preserving directional alignment
        detour_bonus = min(edge_len / DETOUR_LENGTH_SCALE, MAX_DETOUR_BONUS)
        base_attractiveness = 1.0 / (edge_len + EPSILON_OFFSET)

        # Preserve higher baseline priority if moving closer to the target
        alignment = FORWARD_ALIGNMENT_WEIGHT if progress_meters > 0 else BACKWARD_ALIGNMENT_WEIGHT
        return base_attractiveness * detour_bonus * alignment
