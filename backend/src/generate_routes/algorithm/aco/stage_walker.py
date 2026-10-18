from dataclasses import dataclass, field

import networkx as nx
import numpy as np

from src.generate_routes.algorithm.aco.edge_pheromone_registry import EdgePheromoneRegistry
from src.generate_routes.algorithm.aco.heuristics import BudgetManager
from src.generate_routes.algorithm.aco.utils import get_min_edge_length, get_node_coords, haversine

type Map = nx.MultiDiGraph

# Bounding-box angular thresholds for Poland's coordinates (~60m wide boundary)
DEG_LAT_60M = 0.00055
DEG_LON_60M = 0.00085

# Step limits
STEP_LIMIT_NODE_MULTIPLIER = 2
MIN_STEP_LIMIT_FLOOR = 80

# Trajectory history offsets
MIN_HISTORY_FOR_PROXIMITY = 3
HISTORY_RECENCY_EXCLUSION_OFFSET = 3

# Spatial corridor thresholds
HARD_CORRIDOR_DIST_METERS = 25.0
SOFT_CORRIDOR_DIST_METERS = 40.0

# Approach zone to checkpoints
APPROACH_ZONE_RADIUS_METERS = 100.0

# Probabilistic penalties
SOFT_CORRIDOR_ETA_PENALTY = 0.25
MIN_PROBABILITY_EPSILON = 1e-9


@dataclass
class WalkerParams:
    """Hyperparameters configuring walker behavior and sensitivities."""

    alpha: float
    beta: float
    hard_proximity_dist: float = HARD_CORRIDOR_DIST_METERS
    soft_proximity_dist: float = SOFT_CORRIDOR_DIST_METERS


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
    ):
        self.registry = pheromone_registry
        self.budget_manager = budget_manager
        self.params = params

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
        if len(past_coords) <= MIN_HISTORY_FOR_PROXIMITY:
            return False

        lat_v, lon_v = coord_v
        history_slice = past_coords[:-HISTORY_RECENCY_EXCLUSION_OFFSET]
        for lat_p, lon_p in history_slice:
            if abs(lat_v - lat_p) < DEG_LAT_60M and abs(lon_v - lon_p) < DEG_LON_60M:
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
        return not self._check_corridor_overlap(coord_v, state.past_coords, self.params.hard_proximity_dist)

    def _filter_valid_moves(
        self,
        graph: Map,
        state: AntState,
        node_coords: dict[int, tuple[float, float]],
    ) -> list[int]:
        """Collects legal successor moves and enforces approach when near destination."""
        valid_moves = [v for v in graph.successors(state.current) if self._is_legal_move(v, state, node_coords[v])]

        dist_to_dest = haversine(node_coords[state.current], node_coords[state.dest])
        if dist_to_dest < APPROACH_ZONE_RADIUS_METERS:
            progress_moves = [
                v for v in valid_moves if haversine(node_coords[v], node_coords[state.dest]) < dist_to_dest
            ]
            if progress_moves:
                return progress_moves

        return valid_moves

    def _handle_dead_end_rollback(self, graph: Map, state: AntState) -> bool:
        """Backtracks from dead ends or runs emergency Dijkstra."""
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
            state.path.append(nxt)
            state.stage_edges.append(frozenset((state.current, nxt)))
            e_len = get_min_edge_length(graph, state.current, nxt)
            state.distance += e_len
            state.edge_lengths.append(e_len)
            state.current = nxt

        return True

    def _select_next_node(
        self,
        stage_idx: int,
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

            coords_v = get_node_coords(self.budget_manager.stage_graphs[stage_idx], v)
            # Soft taboo: penalty for running alongside recent parallel corridors (25m - 60m)
            if self._check_corridor_overlap(coords_v, state.past_coords, self.params.soft_proximity_dist):
                eta *= SOFT_CORRIDOR_ETA_PENALTY

            probs.append(max(tau * eta, MIN_PROBABILITY_EPSILON))

        total_p = sum(probs)
        norm_probs = [p / total_p for p in probs]
        chosen_idx = int(np.random.choice(len(valid_moves), p=norm_probs))
        return valid_moves[chosen_idx]

    def _advance_ant(
        self,
        graph: Map,
        next_node: int,
        state: AntState,
        coord_next: tuple[float, float],
    ) -> None:
        """Advances ant state forward to the next chosen node."""
        edge_key = frozenset((state.current, next_node))
        e_len = get_min_edge_length(graph, state.current, next_node)

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
        node_coords = {n: get_node_coords(graph, n) for n in graph.nodes()}

        max_steps = max(len(graph.nodes) * STEP_LIMIT_NODE_MULTIPLIER, MIN_STEP_LIMIT_FLOOR)
        steps = 0

        while state.current != state.dest and steps < max_steps:
            steps += 1

            r = self.budget_manager.calculate_r(
                stage_idx=stage_idx,
                current_node=state.current,
                effective_budget=effective_budget,
                dist_done_in_stage=state.distance,
            )

            valid_moves = self._filter_valid_moves(graph, state, node_coords)

            if not valid_moves:
                if self._handle_dead_end_rollback(graph, state):
                    break
                continue

            next_node = self._select_next_node(stage_idx, valid_moves, state, r)
            self._advance_ant(graph, next_node, state, node_coords[next_node])

        return state.path, state.stage_edges, state.distance
