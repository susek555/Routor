from dataclasses import dataclass

from src.generate_routes.algorithm.aco.aco_params import ACOParams
from src.generate_routes.algorithm.aco.edge_pheromone_registry import EdgePheromoneRegistry
from src.generate_routes.algorithm.aco.evaluator import RouteEvaluator
from src.generate_routes.algorithm.aco.heuristics import BudgetManager
from src.generate_routes.algorithm.aco.stage_walker import StageWalker
from src.generate_routes.data.map import Map


@dataclass
class ACO:
    params: ACOParams
    checkpoints: list[int]
    stage_graphs: list[Map]

    def __init__(self, params: ACOParams, checkpoints: list[int], stage_graphs: list[Map]):
        self.params = params
        self.checkpoints = checkpoints
        self.stage_graphs = stage_graphs

        # Initialize modular subsystems
        self.registry = EdgePheromoneRegistry(
            stage_graphs=self.stage_graphs,
            initial_pheromone=self.params.initial_pheromone,
        )
        self.budget_manager = BudgetManager(
            stage_graphs=self.stage_graphs,
            checkpoints=self.checkpoints,
            target_distance=self.params.target_distance,
        )
        self.evaluator = RouteEvaluator(
            stage_graphs=self.stage_graphs,
            target_distance=self.params.target_distance,
            fitness_alpha=self.params.fitness_alpha,
            fitness_beta=self.params.fitness_beta,
        )
        self.walker = StageWalker(
            pheromone_registry=self.registry,
            budget_manager=self.budget_manager,
            alpha=self.params.alpha,
            beta=self.params.beta,
        )

    def _simulate_single_ant(self) -> tuple[list[int], list[frozenset[int]], float, float]:
        """Simulates one ant completing the entire multi-stage loop."""
        num_stages = len(self.checkpoints)
        full_path: list[int] = []
        all_edges: list[frozenset[int]] = []
        total_dist = 0.0
        accumulated_slack = 0.0

        for stage_idx in range(num_stages):
            start_node = self.checkpoints[stage_idx]
            dest_node = self.checkpoints[(stage_idx + 1) % num_stages]
            effective_budget = self.budget_manager.get_effective_stage_budget(
                stage_idx=stage_idx,
                accumulated_slack=accumulated_slack,
            )

            stage_path, stage_edges, stage_dist = self.walker.walk_stage(
                stage_idx=stage_idx,
                start_node=start_node,
                dest_node=dest_node,
                effective_budget=effective_budget,
            )

            # Update inter-stage budget slack and global progress
            accumulated_slack = effective_budget - stage_dist
            total_dist += stage_dist
            all_edges.extend(stage_edges)

            if not full_path:
                full_path.extend(stage_path)
            else:
                # Avoid duplicating connecting checkpoint node
                full_path.extend(stage_path[1:])

        fitness = self.evaluator.evaluate(full_path, all_edges, total_dist)
        return full_path, all_edges, total_dist, fitness

    def generate_route(self) -> list[int]:
        """Runs the ACO optimization loop and returns the best sequence of node IDs."""
        best_path: list[int] = []
        best_fitness = -1.0

        for _ in range(self.params.num_iterations):
            iteration_deposit = self.registry.create_empty_deposit_buffer()
            has_valid_routes = False

            for _ in range(self.params.num_ants):
                path, edges, _, fitness = self._simulate_single_ant()

                if fitness > best_fitness:
                    best_fitness = fitness
                    best_path = path

                # Deposit pheromones proportionally to route quality
                if fitness > 0.0:
                    has_valid_routes = True
                    deposit_amount = fitness * 2.0
                    for edge_key in edges:
                        edge_id = self.registry.get_edge_id(*tuple(edge_key))
                        iteration_deposit[edge_id] += deposit_amount

            # Vectorized evaporation and deposit application
            self.registry.evaporate(self.params.evaporation_rate)
            if has_valid_routes:
                self.registry.apply_deposits(iteration_deposit)

        return best_path
