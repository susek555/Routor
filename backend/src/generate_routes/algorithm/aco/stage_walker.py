import networkx as nx
import numpy as np
from src.generate_routes.algorithm.aco.edge_pheromone_registry import EdgePheromoneRegistry
from src.generate_routes.algorithm.aco.heuristics import BudgetManager
from src.generate_routes.algorithm.aco.utils import get_min_edge_length
from src.generate_routes.data.map import Map


class StageWalker:
    """Simulates an ant traversing a single stage corridor between two checkpoints."""

    def __init__(
        self,
        pheromone_registry: EdgePheromoneRegistry,
        budget_manager: BudgetManager,
        alpha: float,
        beta: float,
    ):
        self.registry = pheromone_registry
        self.budget_manager = budget_manager
        self.alpha = alpha
        self.beta = beta

    def _dijkstra_fallback(
        self,
        graph: Map,
        current: int,
        dest: int,
        visited_edges: set[frozenset[int]],
    ) -> list[int]:
        """Recovers when ant is trapped by dead-ends or taboo constraints."""

        def penalized_weight(u: int, v: int, _: dict) -> float:
            base_len = get_min_edge_length(graph, u, v)
            return base_len * 50.0 if frozenset((u, v)) in visited_edges else base_len

        try:
            path = nx.shortest_path(graph, source=current, target=dest, weight=penalized_weight)
            return path[1:]
        except nx.NetworkXNoPath:
            return []

    def walk_stage(
        self,
        stage_idx: int,
        start_node: int,
        dest_node: int,
        effective_budget: float,
    ) -> tuple[list[int], list[frozenset[int]], float]:
        """Traverses a single stage from start_node to dest_node.

        Returns:
            path: list of visited node IDs.
            edges: list of traversed undirected edge keys in order.
            total_dist: accumulated distance in meters for this stage.
        """
        graph = self.budget_manager.stage_graphs[stage_idx]
        current = start_node
        path = [current]
        stage_edges: list[frozenset[int]] = []
        visited_stage_edges: set[frozenset[int]] = set()
        stage_dist = 0.0

        max_steps = max(len(graph.nodes) * 2, 50)
        steps = 0

        while current != dest_node and steps < max_steps:
            steps += 1
            neighbors = list(graph.successors(current))
            r = self.budget_manager.calculate_r(
                stage_idx=stage_idx,
                current_node=current,
                effective_budget=effective_budget,
                dist_done_in_stage=stage_dist,
            )

            # Filter valid candidate nodes
            valid_moves = []
            for v in neighbors:
                edge_key = frozenset((current, v))
                # Prevent immediate u-turn (u -> v -> u)
                if len(path) > 1 and v == path[-2]:
                    continue
                # Stage-level edge taboo
                if edge_key in visited_stage_edges:
                    continue
                valid_moves.append(v)

            # Dead-end recovery via Dijkstra fallback
            if not valid_moves:
                fallback_path = self._dijkstra_fallback(graph, current, dest_node, visited_stage_edges)
                if not fallback_path:
                    break
                for next_node in fallback_path:
                    edge_key = frozenset((current, next_node))
                    e_len = get_min_edge_length(graph, current, next_node)
                    stage_dist += e_len
                    path.append(next_node)
                    stage_edges.append(edge_key)
                    visited_stage_edges.add(edge_key)
                    current = next_node
                break

            # Calculate transition probabilities
            probs = []
            for v in valid_moves:
                tau = self.registry.get_pheromone(current, v) ** self.alpha
                eta = self.budget_manager.calculate_eta(stage_idx, current, v, r) ** self.beta
                probs.append(max(tau * eta, 1e-9))

            total_p = sum(probs)
            norm_probs = [p / total_p for p in probs]
            chosen_idx = np.random.choice(len(valid_moves), p=norm_probs)
            next_node = valid_moves[chosen_idx]

            edge_key = frozenset((current, next_node))
            e_len = get_min_edge_length(graph, current, next_node)
            stage_dist += e_len
            path.append(next_node)
            stage_edges.append(edge_key)
            visited_stage_edges.add(edge_key)
            current = next_node

        return path, stage_edges, stage_dist
