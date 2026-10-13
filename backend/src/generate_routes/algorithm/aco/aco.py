from src.generate_routes.algorithm.aco.aco_params import ACOParams
from src.generate_routes.algorithm.aco.edge_pheromone_registry import EdgePheromoneRegistry
from src.generate_routes.algorithm.aco.evaluator import RouteEvaluator
from src.generate_routes.algorithm.aco.heuristics import BudgetManager
from src.generate_routes.algorithm.aco.stage_walker import AntState, StageWalker, WalkerParams
from src.generate_routes.data.map import Map

# Inter-stage slack damping and absolute clamping constraints
INTER_STAGE_SLACK_DAMPING = 0.4
MAX_INTER_STAGE_SLACK_METERS = 250.0

# Pheromone deposit multiplier applied to positive route fitness
PHEROMONE_DEPOSIT_MULTIPLIER = 2.0


class ACO:
    """Coordinates the Ant Colony Optimization loop over multiple stage graphs."""

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

        walker_params = WalkerParams(alpha=self.params.alpha, beta=self.params.beta)
        self.walker = StageWalker(
            pheromone_registry=self.registry,
            budget_manager=self.budget_manager,
            params=walker_params,
        )

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

            # Damp and clamp slack propagation to prevent distance monopolization in later stages
            raw_slack = effective_budget - stage_dist
            damped_slack = raw_slack * INTER_STAGE_SLACK_DAMPING
            accumulated_slack = max(
                -MAX_INTER_STAGE_SLACK_METERS,
                min(MAX_INTER_STAGE_SLACK_METERS, damped_slack),
            )

            total_dist += stage_dist
            all_edges.extend(stage_edges)
            global_coords.extend(self._extract_stage_coords(stage_idx, stage_path))

            if not full_path:
                full_path.extend(stage_path)
            else:
                full_path.extend(stage_path[1:])

        fitness = self.evaluator.evaluate(full_path, all_edges, total_dist)
        return full_path, all_edges, total_dist, fitness

    def generate_route(self) -> tuple[list[int], float]:
        """Runs the ACO optimization loop and returns the best sequence of node IDs and its fitness."""
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
                    deposit_amount = fitness * PHEROMONE_DEPOSIT_MULTIPLIER
                    for edge_key in edges:
                        edge_id = self.registry.get_edge_id(*tuple(edge_key))
                        if edge_id is not None:
                            iteration_deposit[edge_id] += deposit_amount

            # Vectorized evaporation and deposit application
            self.registry.evaporate(self.params.evaporation_rate)
            if has_valid_routes:
                self.registry.apply_deposits(iteration_deposit)

        return best_path, best_fitness
