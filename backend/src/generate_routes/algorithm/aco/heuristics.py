from src.generate_routes.algorithm.aco.utils import (
    get_min_edge_length,
    get_node_coords,
    haversine,
)
from src.generate_routes.data.map import Map


class BudgetManager:
    """Manages stage budget allocations, inter-stage slack, and transition heuristics."""
    RATIO_TO_DETOUR_THRESHOLD = 1.2  # R > 1.2 indicates a significant budget surplus

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

    def _calculate_base_budgets() -> list[float]: ...

    def _calculate_base_budgets(self) -> list[float]:
        """Divides target_distance proportionally to straight-line checkpoint distances."""
        stage_distances: list[float] = []

        for i in range(self.num_stages):
            start_node = self.checkpoints[i]
            next_node = self.checkpoints[(i + 1) % self.num_stages]
            graph = self.stage_graphs[i]

            coord_start = get_node_coords(graph, start_node)
            coord_next = get_node_coords(graph, next_node)
            stage_distances.append(max(haversine(coord_start, coord_next), 1.0))

        total_euclidean = sum(stage_distances)
        return [self.target_distance * (dist / total_euclidean) for dist in stage_distances]

    def get_effective_stage_budget(self, stage_idx: int, accumulated_slack: float) -> float:
        """Returns the base budget for stage_idx adjusted by accumulated surplus/deficit."""
        return self.base_budgets[stage_idx] + accumulated_slack

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
        remaining_direct = max(haversine(coord_curr, coord_dest), 1.0)
        return remaining_budget / remaining_direct

    def calculate_eta(
        self,
        stage_idx: int,
        u: int,
        v: int,
        budget_ratio_r: float,
    ) -> float:
        """Computes transition attractiveness eta based on geometry and R."""
        graph = self.stage_graphs[stage_idx]
        dest_node = self.checkpoints[(stage_idx + 1) % self.num_stages]
        edge_len = get_min_edge_length(graph, u, v)

        coord_u = get_node_coords(graph, u)
        coord_v = get_node_coords(graph, v)
        coord_dest = get_node_coords(graph, dest_node)

        dist_u_dest = haversine(coord_u, coord_dest)
        dist_v_dest = haversine(coord_v, coord_dest)
        progress_meters = dist_u_dest - dist_v_dest

        if budget_ratio_r <= 1.0:
            if progress_meters > 0:
                return (progress_meters + 10.0) / (edge_len + 1.0)
            return 1.0 / (edge_len + dist_v_dest + 1.0)
        elif budget_ratio_r > self.RATIO_TO_DETOUR_THRESHOLD:
            return float(edge_len) / (dist_v_dest + 1.0)
        else:
            return 1.0 / (edge_len + 1.0)
