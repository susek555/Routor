import networkx as nx

from src.generate_routes.algorithm.aco.aco_params import ACOParams
from src.generate_routes.algorithm.aco.edge_pheromone_registry import EdgePheromoneRegistry
from src.generate_routes.algorithm.aco.evaluator import RouteEvaluator
from src.generate_routes.algorithm.aco.heuristics import BudgetManager
from src.generate_routes.algorithm.aco.stage_walker import AntState, StageWalker
from src.generate_routes.algorithm.aco.utils.evaluator import EvaluationBreakdown
from src.generate_routes.data.map import Map


class ACO:
    """Coordinates the Ant Colony Optimization loop over multiple stage graphs."""

    def __init__(self, params: ACOParams, checkpoints: list[int], stage_graphs: list[Map]):
        self.params = params
        self.checkpoints = checkpoints
        self.stage_graphs = stage_graphs

        self.registry = EdgePheromoneRegistry(
            stage_graphs=self.stage_graphs,
            initial_pheromone=self.params.initial_pheromone,
        )
        self.budget_manager = BudgetManager(
            stage_graphs=self.stage_graphs,
            checkpoints=self.checkpoints,
            target_distance=self.params.target_distance,
            params=self.params.heuristics_params,
        )
        self.evaluator = RouteEvaluator(
            stage_graphs=self.stage_graphs,
            target_distance=self.params.target_distance,
            params=self.params.evaluator_params,
        )
        self.walker = StageWalker(
            pheromone_registry=self.registry,
            budget_manager=self.budget_manager,
            params=self.params.walker_params,
        )

    def _build_dijkstra_skeleton(self) -> tuple[list[int], float]:
        """Builds a closed baseline loop connecting checkpoints via shortest paths."""
        num_stages = len(self.checkpoints)
        skeleton_path: list[int] = []
        skeleton_distance = 0.0

        for i in range(num_stages):
            start = self.checkpoints[i]
            dest = self.checkpoints[(i + 1) % num_stages]
            graph = self.stage_graphs[i]

            try:
                stage_segment = nx.shortest_path(graph, source=start, target=dest, weight="length")
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                continue

            for u, v in zip(stage_segment[:-1], stage_segment[1:], strict=False):
                edge_data = graph.get_edge_data(u, v, default={})
                edge_len = min((d.get("length", 1.0) for d in edge_data.values()), default=1.0)
                skeleton_distance += edge_len

            if not skeleton_path:
                skeleton_path.extend(stage_segment)
            else:
                skeleton_path.extend(stage_segment[1:])

        return skeleton_path, skeleton_distance

    def _extract_stage_coords(
        self,
        stage_idx: int,
        stage_path: list[int],
    ) -> list[tuple[float, float]]:
        """Extracts latitude/longitude pairs for nodes traversed during a stage."""
        graph = self.stage_graphs[stage_idx]
        extracted_coords: list[tuple[float, float]] = []

        for node in stage_path:
            node_data = graph.nodes[node]
            lat = node_data.get("y", node_data.get("lat"))
            lon = node_data.get("x", node_data.get("lon"))
            if lat is not None and lon is not None:
                extracted_coords.append((lat, lon))

        return extracted_coords

    def _simulate_single_ant(self) -> tuple[list[int], list[frozenset[int]], float, float]:
        """Simulates traversal of one ant through all sequential checkpoint stages."""
        num_stages = len(self.checkpoints)
        full_path: list[int] = []
        all_edges: list[frozenset[int]] = []
        global_coords: list[tuple[float, float]] = []
        total_dist = 0.0
        accumulated_slack = 0.0

        for stage_idx in range(num_stages):
            start_node = self.checkpoints[stage_idx]
            dest_node = self.checkpoints[(stage_idx + 1) % num_stages]

            effective_budget = self.budget_manager.get_effective_stage_budget(
                stage_idx=stage_idx,
                accumulated_slack=accumulated_slack,
            )

            state = AntState(
                current=start_node,
                dest=dest_node,
                path=[start_node],
                past_coords=list(global_coords),
            )

            stage_path, stage_edges, stage_dist = self.walker.walk_stage(
                stage_idx=stage_idx,
                effective_budget=effective_budget,
                state=state,
            )

            raw_slack = effective_budget - stage_dist
            damped_slack = raw_slack * self.params.inter_stage_slack_damping
            accumulated_slack = max(
                -self.params.max_inter_stage_slack_meters,
                min(self.params.max_inter_stage_slack_meters, damped_slack),
            )

            total_dist += stage_dist
            all_edges.extend(stage_edges)
            global_coords.extend(self._extract_stage_coords(stage_idx, stage_path))

            if not full_path:
                full_path.extend(stage_path)
            else:
                full_path.extend(stage_path[1:])

        fitness = self.evaluator.evaluate(full_path, total_dist)
        return full_path, all_edges, total_dist, fitness

    def generate_route(self) -> tuple[list[int], float]:
        """Runs the ACO optimization loop with warm-start Dijkstra seeding."""
        # 1. Warm start: extract baseline skeleton and seed baseline pheromones
        skeleton_path, skeleton_dist = self._build_dijkstra_skeleton()
        best_path: list[int] = skeleton_path
        best_total_dist = skeleton_dist
        best_fitness = self.evaluator.evaluate(skeleton_path, total_distance=skeleton_dist) if skeleton_path else -1.0

        if skeleton_path:
            self.registry.seed_path_pheromones(skeleton_path, boost_factor=self.params.warm_start_seed_multiplier)

        # 2. Main ACO exploration loop (can now run with fewer iterations, e.g. 15-20)
        for _ in range(self.params.num_iterations):
            iteration_deposit = self.registry.create_empty_deposit_buffer()
            has_valid_routes = False

            for _ in range(self.params.num_ants):
                path, edges, dist, fitness = self._simulate_single_ant()

                if fitness > best_fitness:
                    best_fitness = fitness
                    best_path = path
                    best_total_dist = dist

                if fitness > 0.0:
                    has_valid_routes = True
                    deposit_amount = fitness * self.params.pheromone_deposit_multiplier
                    for edge_key in edges:
                        edge_id = self.registry.get_edge_id(*tuple(edge_key))
                        if edge_id is not None:
                            iteration_deposit[edge_id] += deposit_amount

            self.registry.evaporate(self.params.evaporation_rate)
            if has_valid_routes:
                self.registry.apply_deposits(iteration_deposit)

        if best_path:
            breakdown: EvaluationBreakdown = self.evaluator.evaluate_with_breakdown(best_path, best_total_dist)
            breakdown.log_summary("Best Found Ant Loop")

        return best_path, best_fitness
