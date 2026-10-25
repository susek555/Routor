from dataclasses import dataclass, field

import networkx as nx
import numpy as np

from src.generate_routes.algorithm.aco.edge_pheromone_registry import EdgePheromoneRegistry
from src.generate_routes.algorithm.aco.heuristics import BudgetManager
from src.generate_routes.algorithm.aco.utils.stage_walker import WalkerParams
from src.generate_routes.algorithm.common_utils import (
    get_min_edge_length,
    get_node_coords,
    haversine,
)
from src.generate_routes.data.map import Map


@dataclass
class AntState:
    """Internal mutable backtracking stacks and history for a traversing ant."""

    current: int
    dest: int
    path: list[int] = field(default_factory=list)
    stage_edges: list[frozenset[int]] = field(default_factory=list)
    edge_lengths: list[float] = field(default_factory=list)
    visited_edges: set[frozenset[int]] = field(default_factory=set)
    dead_end_nodes: set[int] = field(default_factory=set)
    past_coords: list[tuple[float, float]] = field(default_factory=list)
    distance: float = 0.0


class StageWalker:
    """Simulates an ant traversing a single stage corridor between two checkpoints."""

    def __init__(
        self,
        pheromone_registry: EdgePheromoneRegistry,
        budget_manager: BudgetManager,
        params: WalkerParams,
    ) -> None:
        self.registry = pheromone_registry
        self.budget_manager = budget_manager
        self.params = params

        self.node_coord_cache: dict[int, tuple[float, float]] = {}
        self.edge_len_cache: dict[tuple[int, int], float] = {}

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

    def _emergency_dijkstra(self, graph: Map, current: int, dest: int) -> list[int]:
        """Ultimate fallback only if topological connectivity is completely lost."""
        try:
            path = nx.shortest_path(graph, source=current, target=dest, weight="length")
            return path[1:]
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

    def _check_corridor_overlap(
        self,
        coord_v: tuple[float, float],
        past_coords: list[tuple[float, float]],
        threshold_dist: float,
    ) -> bool:
        """Checks if coordinate v is within threshold_dist of past trajectory."""
        if len(past_coords) <= self.params.min_history_for_proximity:
            return False

        lat_v, lon_v = coord_v
        history_slice = past_coords[: -self.params.history_recency_exclusion_offset]

        for lat_p, lon_p in history_slice:
            if (
                abs(lat_v - lat_p) < self.params.bounding_box.DEG_LAT
                and abs(lon_v - lon_p) < self.params.bounding_box.DEG_LON
            ):
                if haversine((lat_v, lon_v), (lat_p, lon_p)) < threshold_dist:
                    return True
        return False

    def _is_legal_move(
        self,
        candidate: int,
        state: AntState,
        coord_v: tuple[float, float],
    ) -> bool:
        """Evaluates whether moving to candidate is allowed (hard taboo constraints)."""
        if candidate == state.current or candidate in state.dead_end_nodes:
            return False
        if len(state.path) > 1 and candidate == state.path[-2]:
            return False
        if frozenset((state.current, candidate)) in state.visited_edges:
            return False

        return not self._check_corridor_overlap(coord_v, state.past_coords, self.params.hard_proximity_dist_meters)

    def _filter_valid_moves(self, graph: Map, state: AntState) -> list[int]:
        """Collects legal successor moves and enforces approach criteria."""
        valid_moves = [
            v for v in graph.successors(state.current) if self._is_legal_move(v, state, self._get_coord(graph, v))
        ]
        if not valid_moves:
            return []

        coord_curr = self._get_coord(graph, state.current)
        coord_dest = self._get_coord(graph, state.dest)
        dist_to_dest = haversine(coord_curr, coord_dest)

        if dist_to_dest < self.params.approach_zone_radius_meters:
            progress_moves = [v for v in valid_moves if haversine(self._get_coord(graph, v), coord_dest) < dist_to_dest]
            if progress_moves:
                return progress_moves

        return valid_moves

    def _handle_dead_end_rollback(self, graph: Map, state: AntState) -> bool:
        """Backtracks from dead ends or runs emergency Dijkstra if backtrack is exhausted."""
        state.dead_end_nodes.add(state.current)

        if len(state.path) > 1:
            state.path.pop()
            if state.stage_edges:
                state.stage_edges.pop()
            if state.edge_lengths:
                state.distance -= state.edge_lengths.pop()
            if state.past_coords:
                state.past_coords.pop()

            state.current = state.path[-1]
            return False

        fallback = self._emergency_dijkstra(graph, state.current, state.dest)
        for nxt in fallback:
            e_len = self._get_edge_length(graph, state.current, nxt)
            edge_key = frozenset((state.current, nxt))

            state.path.append(nxt)
            state.stage_edges.append(edge_key)
            state.edge_lengths.append(e_len)
            state.distance += e_len
            state.current = nxt

        return True

    def _select_next_node(
        self,
        stage_idx: int,
        graph: Map,
        valid_moves: list[int],
        state: AntState,
        budget_ratio_r: float,
    ) -> int:
        """Selects next node via ACO roulette wheel applying smooth turn and soft corridor penalties."""
        probs: list[float] = []
        prev_node = state.path[-2] if len(state.path) > 1 else None

        for v in valid_moves:
            tau = self.registry.get_pheromone(state.current, v) ** self.params.alpha
            eta = (
                self.budget_manager.calculate_eta(stage_idx, state.current, v, budget_ratio_r, prev_node)
                ** self.params.beta
            )

            coords_v = self._get_coord(graph, v)
            if self._check_corridor_overlap(coords_v, state.past_coords, self.params.soft_proximity_dist_meters):
                eta *= self.params.soft_corridor_eta_penalty

            probs.append(max(tau * eta, self.params.min_probability_epsilon))

        total_p = sum(probs)
        norm_probs = [p / total_p for p in probs]
        chosen_idx = int(np.random.choice(len(valid_moves), p=norm_probs))
        return valid_moves[chosen_idx]

    def _advance_ant(self, graph: Map, next_node: int, state: AntState) -> None:
        """Advances ant state forward to the next chosen node."""
        edge_key = frozenset((state.current, next_node))
        e_len = self._get_edge_length(graph, state.current, next_node)
        coord_next = self._get_coord(graph, next_node)

        state.path.append(next_node)
        state.stage_edges.append(edge_key)
        state.edge_lengths.append(e_len)
        state.distance += e_len
        state.visited_edges.add(edge_key)
        state.past_coords.append(coord_next)
        state.current = next_node

    def walk_stage(
        self,
        stage_idx: int,
        effective_budget: float,
        state: AntState,
    ) -> tuple[list[int], list[frozenset[int]], float]:
        """Executes ant traversal through a single stage using heuristics and backtracking."""
        graph = self.budget_manager.stage_graphs[stage_idx]
        max_steps = max(
            len(graph.nodes) * self.params.step_limit_node_multiplier,
            self.params.min_step_limit_floor,
        )
        steps = 0

        while state.current != state.dest and steps < max_steps:
            steps += 1

            r = self.budget_manager.calculate_r(
                stage_idx=stage_idx,
                current_node=state.current,
                effective_budget=effective_budget,
                dist_done_in_stage=state.distance,
            )

            valid_moves = self._filter_valid_moves(graph, state)

            if not valid_moves:
                if self._handle_dead_end_rollback(graph, state):
                    break
                continue

            next_node = self._select_next_node(stage_idx, graph, valid_moves, state, r)
            self._advance_ant(graph, next_node, state)

        return state.path, state.stage_edges, state.distance
