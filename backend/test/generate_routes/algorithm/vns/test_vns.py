from unittest.mock import MagicMock

import networkx as nx
import pytest
from src.generate_routes.algorithm.evaluator import RouteEvaluator
from src.generate_routes.algorithm.evaluator_params import EvaluationBreakdown
from src.generate_routes.algorithm.vns.vns_generator import VNSLoopGenerator
from src.generate_routes.algorithm.vns.vns_params import (
    NeighborhoodParams,
    SamplerParams,
    SmootherParams,
    VNSParams,
)


@pytest.fixture
def default_vns_params():
    """Provides standard VNS configuration with low iteration ceilings for fast test runs."""
    return VNSParams(
        target_distance=1000.0,
        max_iterations=20,
        max_stagnation_iterations=5,
        target_fitness=0.98,
        num_initial_samples=2,
        sampler_params=SamplerParams(approach_lock_radius_meters=50.0),
        neighborhood_params=NeighborhoodParams(max_k=3),
        smoother_params=SmootherParams(min_nodes_to_smooth=4),
    )


@pytest.fixture
def mock_evaluator():
    """Provides a mocked RouteEvaluator with dummy coordinates and edge cache."""
    evaluator = MagicMock(spec=RouteEvaluator)
    evaluator.node_coord_cache = {
        0: (52.000, 21.000),
        1: (52.005, 21.000),
        2: (52.005, 21.005),
    }
    evaluator.edge_info_cache = {}
    evaluator.evaluate.return_value = 0.50

    mock_breakdown = MagicMock(spec=EvaluationBreakdown)
    mock_breakdown.log_summary = MagicMock()
    evaluator.evaluate_with_breakdown.return_value = mock_breakdown
    return evaluator


@pytest.fixture
def stage_graphs():
    """Builds two simple graphs representing a two-stage loop."""
    g1 = nx.MultiDiGraph()
    g1.add_nodes_from([0, 1, 10])
    g2 = nx.MultiDiGraph()
    g2.add_nodes_from([1, 0, 20])
    return [g1, g2]


class TestVNSLoopGenerator:
    def test_init_propagates_parameters_and_initializes_modules(self, default_vns_params, mock_evaluator, stage_graphs):
        """Verifies proper modular decomposition and parameter injection on initialization."""
        generator = VNSLoopGenerator(
            params=default_vns_params,
            checkpoints=[0, 1],
            stage_graphs=stage_graphs,
            evaluator=mock_evaluator,
        )

        assert generator.num_stages == 2
        assert generator.connector.num_stages == 2
        assert generator.sampler.params == default_vns_params.sampler_params
        assert generator.neighborhoods.params == default_vns_params.neighborhood_params
        assert generator.smoother.params == default_vns_params.smoother_params

    def test_sample_initial_solutions_updates_baseline_when_better(
        self, default_vns_params, mock_evaluator, stage_graphs
    ):
        """Ensures initial sampling selects detours that improve baseline fitness."""
        generator = VNSLoopGenerator(
            params=default_vns_params,
            checkpoints=[0, 1],
            stage_graphs=stage_graphs,
            evaluator=mock_evaluator,
        )

        # Mock candidate selection from sampler
        generator.sampler.select_biased_candidate = MagicMock(return_value=10)

        # Mock connector: first call returns baseline, second call (sampled) returns better fitness
        generator.connector.evaluate_candidate_stages = MagicMock(return_value=([0, 10, 1, 0], 850.0, 0.75))

        baseline_wps = [[0, 1], [1, 0]]
        wps, path, dist, fitness = generator._sample_initial_solutions(
            baseline_wps=baseline_wps,
            best_dist=600.0,
            best_fitness=0.40,
        )

        assert fitness == 0.75
        assert dist == 850.0
        assert path == [0, 10, 1, 0]

    def test_generate_route_stops_immediately_on_target_fitness(self, default_vns_params, mock_evaluator, stage_graphs):
        """Halts the optimization loop as soon as target fitness threshold is reached."""
        generator = VNSLoopGenerator(
            params=default_vns_params,
            checkpoints=[0, 1],
            stage_graphs=stage_graphs,
            evaluator=mock_evaluator,
        )

        generator.connector.evaluate_candidate_stages = MagicMock(return_value=([0, 1, 0], 1000.0, 0.99))
        generator._sample_initial_solutions = MagicMock(return_value=([[0, 1], [1, 0]], [0, 1, 0], 1000.0, 0.99))
        generator.neighborhoods.shake = MagicMock()

        # Ensure post-processing smoother preserves path and fitness
        generator.smoother.smooth = MagicMock(return_value=([0, 1, 0], 1000.0))
        mock_evaluator.evaluate.return_value = 0.99

        path, fitness = generator.generate_route()

        generator.neighborhoods.shake.assert_not_called()
        assert fitness == 0.99

    def test_generate_route_resets_k_on_improvement(self, default_vns_params, mock_evaluator, stage_graphs):
        """Resets neighborhood perturbation index k=1 and stagnation counter upon finding improvement."""
        generator = VNSLoopGenerator(
            params=default_vns_params,
            checkpoints=[0, 1],
            stage_graphs=stage_graphs,
            evaluator=mock_evaluator,
        )

        # Skip sampling
        generator._sample_initial_solutions = MagicMock(return_value=([[0, 1], [1, 0]], [0, 1, 0], 600.0, 0.40))

        generator.neighborhoods.shake = MagicMock(return_value=[[0, 10, 1], [1, 0]])

        # Iteration 1 (k=1): Worse fitness (0.35) -> k becomes 2
        # Iteration 2 (k=2): Better fitness (0.80) -> k resets to 1
        # Iteration 3: Hits target fitness (0.99) -> terminates
        generator.connector.evaluate_candidate_stages = MagicMock(
            side_effect=[
                ([0, 1, 0], 600.0, 0.40),  # Baseline init
                ([0, 1, 0], 550.0, 0.35),  # Iter 1: worse
                ([0, 10, 1, 0], 900.0, 0.80),  # Iter 2: better
                ([0, 10, 1, 0], 1000.0, 0.99),  # Iter 3: goal reached
            ]
        )

        generator.smoother.smooth = MagicMock(side_effect=lambda p: (p, 1000.0))
        mock_evaluator.evaluate.return_value = 0.99

        path, fitness = generator.generate_route()

        # Improvement was recorded once on iteration 2
        assert generator.neighborhoods.stats[2].improvements == 1
        assert fitness == 0.99

    def test_generate_route_triggers_stagnation_cutoff(self, default_vns_params, mock_evaluator, stage_graphs):
        """Stops VNS execution when no improvement occurs within max_stagnation_iterations."""
        default_vns_params = VNSParams(
            target_distance=1000.0,
            max_iterations=50,
            max_stagnation_iterations=3,
            target_fitness=0.99,
            num_initial_samples=1,
            neighborhood_params=NeighborhoodParams(max_k=2),
        )

        generator = VNSLoopGenerator(
            params=default_vns_params,
            checkpoints=[0, 1],
            stage_graphs=stage_graphs,
            evaluator=mock_evaluator,
        )

        generator._sample_initial_solutions = MagicMock(return_value=([[0, 1], [1, 0]], [0, 1, 0], 500.0, 0.30))

        # Baseline evaluation
        # Every subsequent shake evaluation fails to improve over baseline 0.30
        generator.connector.evaluate_candidate_stages = MagicMock(
            side_effect=[
                ([0, 1, 0], 500.0, 0.30),  # Base init
                ([0, 10, 1, 0], 520.0, 0.25),  # Stagnation 1
                ([0, 10, 1, 0], 510.0, 0.20),  # Stagnation 2
                ([0, 10, 1, 0], 490.0, 0.22),  # Stagnation 3 -> cutoff
            ]
        )

        generator.generate_route()

        # Exactly 3 stagnation steps + 1 base init = 4 calls to evaluate_candidate_stages
        assert generator.connector.evaluate_candidate_stages.call_count == 4

    def test_generate_route_applies_post_smoothing_and_logging(self, default_vns_params, mock_evaluator, stage_graphs):
        """Ensures post-processing smoother cleans the winning route and triggers diagnostic breakdown."""
        generator = VNSLoopGenerator(
            params=default_vns_params,
            checkpoints=[0, 1],
            stage_graphs=stage_graphs,
            evaluator=mock_evaluator,
        )

        generator._sample_initial_solutions = MagicMock(return_value=([[0, 1], [1, 0]], [0, 1, 0], 900.0, 0.99))
        generator.connector.evaluate_candidate_stages = MagicMock(return_value=([0, 1, 0], 900.0, 0.99))

        # Mock smoother output
        generator.smoother.smooth = MagicMock(return_value=([0, 1, 0], 880.0))
        mock_evaluator.evaluate.return_value = 0.99

        best_path, best_fitness = generator.generate_route()

        generator.smoother.smooth.assert_called_once_with([0, 1, 0])
        mock_evaluator.evaluate_with_breakdown.assert_called_once_with([0, 1, 0], 880.0)
        assert best_path == [0, 1, 0]
        assert best_fitness == 0.99
