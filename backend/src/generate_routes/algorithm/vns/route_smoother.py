import networkx as nx

from src.generate_routes.algorithm.aco.utils.common import haversine
from src.generate_routes.algorithm.evaluator import RouteEvaluator
from src.generate_routes.algorithm.vns.detour_sampler import DetourSampler
from src.generate_routes.algorithm.vns.vns_params import SmootherParams
from src.generate_routes.data.map import Map


class RouteSmoother:
    """Post-processing module removing local micro-spurs and hairpins."""

    def __init__(
        self,
        params: SmootherParams,
        evaluator: RouteEvaluator,
        sampler: DetourSampler,
        reference_graph: Map,
        target_distance: float,
    ) -> None:
        self.params = params
        self.evaluator = evaluator
        self.sampler = sampler
        self.reference_graph = reference_graph
        self.target_distance = target_distance

    def calculate_path_distance(self, path: list[int]) -> float:
        """Calculates total path distance using cached edge lengths."""
        if not path or len(path) < 2:  # noqa: PLR2004
            return 0.0
        return sum(
            self.evaluator.edge_info_cache.get((u, v), ([], self.params.default_fallback_edge_length))[1]
            for u, v in zip(path[:-1], path[1:], strict=False)
        )

    def smooth(self, full_path: list[int]) -> tuple[list[int], float]:
        """Removes local micro-spurs with safety guards against collapsing the loop."""
        if not full_path or len(full_path) < self.params.min_nodes_to_smooth:
            return full_path, self.calculate_path_distance(full_path)

        smoothed: list[int] = []
        i = 0
        n = len(full_path)
        original_dist = self.calculate_path_distance(full_path)

        while i < n:
            smoothed.append(full_path[i])
            curr_coord = self.sampler.get_coord(full_path[i], self.reference_graph)

            shortcut_found = False
            max_lookahead = (
                min(i + self.params.max_lookahead_nodes, n - 2)
                if i < self.params.early_path_index_threshold
                else min(i + self.params.max_lookahead_nodes, n - 1)
            )

            for j in range(max_lookahead, i + self.params.min_shortcut_hop_diff, -1):
                if i < self.params.protected_start_index_limit and j > (n - self.params.protected_finish_offset_nodes):
                    continue

                target_coord = self.sampler.get_coord(full_path[j], self.reference_graph)

                if haversine(curr_coord, target_coord) < self.params.micro_spur_proximity_meters:
                    try:
                        shortcut = nx.shortest_path(
                            self.reference_graph,
                            source=full_path[i],
                            target=full_path[j],
                            weight="length",
                        )
                        if len(shortcut) < (j - i):
                            smoothed.extend(shortcut[1:])
                            i = j
                            shortcut_found = True
                            break
                    except (nx.NetworkXNoPath, nx.NodeNotFound):
                        continue

            if not shortcut_found:
                i += 1

        smoothed_dist = self.calculate_path_distance(smoothed)

        min_allowed_distance = self.params.min_distance_retention_ratio * self.target_distance
        if smoothed_dist < min_allowed_distance or len(smoothed) < self.params.min_smoothed_path_nodes:
            return full_path, original_dist

        return smoothed, smoothed_dist
