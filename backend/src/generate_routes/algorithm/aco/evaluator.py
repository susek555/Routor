from collections import Counter

from src.generate_routes.algorithm.aco.utils import get_min_edge_length
from src.generate_routes.data.map import Map


class RouteEvaluator:
    """Evaluates the global quality (fitness) of a candidate ant loop."""

    def __init__(
        self,
        stage_graphs: list[Map],
        target_distance: float,
        fitness_alpha: float = 2.0,
        fitness_beta: float = 3.0,
    ):
        self.stage_graphs = stage_graphs
        self.target_distance = max(target_distance, 1.0)
        self.alpha = fitness_alpha
        self.beta = fitness_beta

    def _resolve_edge_length(self, u: int, v: int) -> float:
        """Finds edge length across stage subgraphs."""
        for graph in self.stage_graphs:
            if graph.has_edge(u, v):
                return get_min_edge_length(graph, u, v)
        return 1.0

    def calculate_overlap_penalty(self, traversed_edges: list[frozenset[int]]) -> float:
        """Computes penalty for traversing the same undirected edge multiple times."""
        edge_counts = Counter(traversed_edges)
        penalty = 0.0

        for edge_key, count in edge_counts.items():
            if count > 1:
                u, v = tuple(edge_key)
                edge_len = self._resolve_edge_length(u, v)
                penalty += (count - 1) * edge_len

        return penalty

    def evaluate(
        self,
        full_path: list[int],
        traversed_edges: list[frozenset[int]],
        total_distance: float,
    ) -> float:
        """Calculates global fitness score in range (0.0, 1.0]. Returns 0.0 if loop is broken."""
        if not full_path or full_path[0] != full_path[-1]:
            return 0.0

        dist_diff_ratio = abs(total_distance - self.target_distance) / self.target_distance
        overlap_penalty = self.calculate_overlap_penalty(traversed_edges)
        overlap_ratio = overlap_penalty / self.target_distance

        fitness = 1.0 / (1.0 + self.alpha * dist_diff_ratio + self.beta * overlap_ratio)
        return float(fitness)
