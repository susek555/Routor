import logging

from src.generate_routes.algorithm.aco.evaluator import RouteEvaluator
from src.generate_routes.algorithm.aco.utils.evaluator import EvaluationBreakdown
from src.generate_routes.algorithm.vns.detour_sampler import DetourSampler
from src.generate_routes.algorithm.vns.neighborhoods import NeighborhoodOperator
from src.generate_routes.algorithm.vns.route_smoother import RouteSmoother
from src.generate_routes.algorithm.vns.stage_connector import StageConnector
from src.generate_routes.algorithm.vns.vns_params import VNSParams
from src.generate_routes.data.map import Map

logger = logging.getLogger(__name__)


class VNSLoopGenerator:
    """Coordinates Variable Neighborhood Search over segmented stage graphs."""

    def __init__(
        self,
        params: VNSParams,
        checkpoints: list[int],
        stage_graphs: list[Map],
        evaluator: RouteEvaluator,
    ) -> None:
        self.params = params
        self.checkpoints = list(checkpoints)
        self.stage_graphs = stage_graphs
        self.evaluator = evaluator
        self.num_stages = len(checkpoints)

        # Coordinate cache shared with evaluator
        self.node_coord_cache: dict[int, tuple[float, float]] = dict(self.evaluator.node_coord_cache)

        # Sub-modules initialization with granular parameter objects
        self.connector = StageConnector(
            stage_graphs=self.stage_graphs,
            evaluator=self.evaluator,
        )
        self.sampler = DetourSampler(
            params=self.params.sampler_params,
            node_coord_cache=self.node_coord_cache,
        )
        self.neighborhoods = NeighborhoodOperator(
            params=self.params.neighborhood_params,
            sampler=self.sampler,
            stage_graphs=self.stage_graphs,
            checkpoints=self.checkpoints,
            target_distance=self.params.target_distance,
        )
        ref_graph = getattr(self.evaluator, "graph", self.stage_graphs[0])
        self.smoother = RouteSmoother(
            params=self.params.smoother_params,
            evaluator=self.evaluator,
            sampler=self.sampler,
            reference_graph=ref_graph,
            target_distance=self.params.target_distance,
        )

    def _sample_initial_solutions(
        self,
        baseline_wps: list[list[int]],
        best_dist: float,
        best_fitness: float,
    ) -> tuple[list[list[int]], list[int], float, float]:
        """Explores initial detours across stages to seed baseline solution."""
        current_wps = [list(stage) for stage in baseline_wps]
        best_path: list[int] = []

        for _ in range(self.params.num_initial_samples - 1):
            sample_wps = [list(stage) for stage in current_wps]
            for s_idx in range(self.num_stages):
                s_nodes = self.neighborhoods._stage_nodes_cache[s_idx]
                g_s = self.stage_graphs[s_idx]
                s_existing = set(sample_wps[s_idx])
                s_allowed = [
                    n
                    for n in s_nodes
                    if not self.sampler.is_in_terminal_zone(n, sample_wps[s_idx][0], sample_wps[s_idx][-1], g_s)
                    and n not in s_existing
                ]
                if s_allowed:
                    cand = self.sampler.select_biased_candidate(
                        s_allowed,
                        sample_wps[s_idx][0],
                        sample_wps[s_idx][-1],
                        g_s,
                        (self.params.target_distance - best_dist) / self.num_stages,
                    )
                    sample_wps[s_idx].insert(1, cand)

            s_path, s_dist, s_fitness = self.connector.evaluate_candidate_stages(sample_wps)
            if s_path and s_fitness > best_fitness:
                best_fitness = s_fitness
                best_path = s_path
                best_dist = s_dist
                current_wps = [list(s) for s in sample_wps]

        return current_wps, best_path, best_dist, best_fitness

    def generate_route(self) -> tuple[list[int], float]:
        """Executes the main VNS exploration loop, shaking, and post-smoothing."""
        # 1. Base skeleton initialization
        current_stage_wps: list[list[int]] = [
            [self.checkpoints[i], self.checkpoints[(i + 1) % self.num_stages]] for i in range(self.num_stages)
        ]

        best_path, best_dist, best_fitness = self.connector.evaluate_candidate_stages(current_stage_wps)

        # 2. Initial sampling phase
        current_stage_wps, init_path, init_dist, init_fitness = self._sample_initial_solutions(
            current_stage_wps, best_dist, best_fitness
        )
        if init_path:
            best_path, best_dist, best_fitness = init_path, init_dist, init_fitness

        if not best_path:
            return [], -1.0

        current_dist = best_dist

        # 3. Main VNS exploration loop
        k = 1
        iteration = 0
        stagnation_counter = 0
        max_k = self.params.neighborhood_params.max_k

        while iteration < self.params.max_iterations:
            iteration += 1

            # Early stopping on target fitness
            if best_fitness >= self.params.target_fitness:
                logger.info(f"Target fitness reached ({best_fitness:.4f}) at iteration {iteration}. Halting.")
                break

            cand_wps = self.neighborhoods.shake(current_stage_wps, k, current_dist)
            cand_path, cand_dist, cand_fitness = self.connector.evaluate_candidate_stages(cand_wps)

            if not cand_path:
                k = (k % max_k) + 1
                stagnation_counter += 1
                if stagnation_counter >= self.params.max_stagnation_iterations:
                    break
                continue

            # Neighborhood acceptance step
            if cand_fitness > best_fitness:
                self.neighborhoods.record_improvement(k)
                best_fitness = cand_fitness
                best_path = cand_path
                best_dist = cand_dist

                current_stage_wps = [list(s) for s in cand_wps]
                current_dist = cand_dist

                k = 1
                stagnation_counter = 0
            else:
                k = (k % max_k) + 1
                stagnation_counter += 1

            if stagnation_counter >= self.params.max_stagnation_iterations:
                logger.info(
                    f"Stagnation triggered ({stagnation_counter} iterations without improvement). Stopping VNS."
                )
                break

        self.neighborhoods.log_operator_stats()

        # 4. Post-processing: Route smoothing and spur removal
        if best_path:
            best_path, best_dist = self.smoother.smooth(best_path)
            best_fitness = self.evaluator.evaluate(best_path, total_distance=best_dist)

            breakdown: EvaluationBreakdown = self.evaluator.evaluate_with_breakdown(best_path, best_dist)
            breakdown.log_summary("Best Found VNS Loop (Smoothed)")

        return best_path, best_fitness
