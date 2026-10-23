import math
from unittest.mock import MagicMock, patch

import networkx as nx
import pytest
from src.generate_routes.algorithm.aco.evaluator import RouteEvaluator
from src.generate_routes.algorithm.aco.utils.evaluator import EvaluationBreakdown, EvaluatorParams

MODULE_PATH = RouteEvaluator.__module__


@pytest.fixture
def default_evaluator_params():
    """Provides a baseline EvaluatorParams configuration for testing."""
    params = MagicMock(spec=EvaluatorParams)
    params.edge_sample_step_meters = 20.0
    params.start_finish_exclusion_radius_meters = 50.0
    params.max_perpendicular_deviation_rad = math.pi / 4.0  # 45 degrees
    params.min_path_separation_meters = 30.0
    params.default_corridor_threshold_meters = 25.0
    params.antiparallel_min_rad = math.pi * 0.75  # 135 degrees
    params.opposite_corridor_penalty_multiplier = 1.5
    params.out_and_back_penalty_multiplier = 2.0
    params.min_path_nodes_to_overlap = 3

    # Distance penalty brackets
    params.distance_tolerance_threshold = 0.10
    params.under_threshold_weight = 1.0
    params.over_threshold_weight = 3.0
    params.distance_penalty_weight = 2.0

    # Overlap penalty brackets
    params.overlap_tolerance_ratio = 0.05
    params.overlap_under_threshold_weight = 1.0
    params.overlap_over_threshold_weight = 4.0
    params.overlap_penalty_weight = 2.5

    # Bounding box tolerances
    bounding_box = MagicMock()
    bounding_box.DEG_LAT = 0.001
    bounding_box.DEG_LON = 0.001
    params.bounding_box = bounding_box

    return params


@pytest.fixture
def simple_loop_graph():
    """Builds a simple triangular loop graph: 0 -> 1 -> 2 -> 0.

    Node 0: (52.000, 21.000) - Start/finish point
    Node 1: (52.005, 21.000) - North
    Node 2: (52.005, 21.005) - North-East
    """
    g = nx.MultiDiGraph()
    g.add_node(0, y=52.000, x=21.000)
    g.add_node(1, y=52.005, x=21.000)
    g.add_node(2, y=52.005, x=21.005)

    g.add_edge(0, 1, key=0, length=500.0)
    g.add_edge(1, 0, key=0, length=500.0)

    g.add_edge(1, 2, key=0, length=350.0)
    g.add_edge(2, 1, key=0, length=350.0)

    g.add_edge(2, 0, key=0, length=600.0)
    g.add_edge(0, 2, key=0, length=600.0)
    return g


class TestRouteEvaluatorExecutionFlow:
    @patch.object(RouteEvaluator, "_build_edge_cache")
    def test_init_calls_build_edge_cache(self, mock_build_cache, default_evaluator_params):
        """Verifies cache build execution on evaluator initialization."""
        evaluator = RouteEvaluator(
            stage_graphs=[],
            target_distance=1000.0,
            params=default_evaluator_params,
        )

        mock_build_cache.assert_called_once()
        assert evaluator.target_distance == 1000.0
        assert evaluator.params == default_evaluator_params

    def test_init_clamps_min_target_distance(self, default_evaluator_params):
        """Ensures non-positive target distance is clamped to at least 1.0 meter."""
        evaluator = RouteEvaluator(
            stage_graphs=[],
            target_distance=-50.0,
            params=default_evaluator_params,
        )
        assert evaluator.target_distance == 1.0

    @patch.object(RouteEvaluator, "evaluate_with_breakdown")
    def test_evaluate_delegates_to_evaluate_with_breakdown(
        self,
        mock_evaluate_breakdown,
        default_evaluator_params,
    ):
        """Verifies that evaluate extracts the fitness score from evaluate_with_breakdown."""
        evaluator = RouteEvaluator(
            stage_graphs=[],
            target_distance=1000.0,
            params=default_evaluator_params,
        )
        mock_breakdown = MagicMock(spec=EvaluationBreakdown)
        mock_breakdown.fitness = 0.85
        mock_evaluate_breakdown.return_value = mock_breakdown

        path = [0, 1, 2, 0]
        score = evaluator.evaluate(path, total_distance=950.0)

        mock_evaluate_breakdown.assert_called_once_with(path, 950.0)
        assert score == 0.85


class TestRouteEvaluatorUnitAndIntegration:
    def test_interpolate_edge_points_short_and_long_segments(
        self,
        default_evaluator_params,
    ):
        """Verifies midpoint interpolation for short edges and multi-point sampling for long edges."""
        evaluator = RouteEvaluator(
            stage_graphs=[],
            target_distance=1000.0,
            params=default_evaluator_params,
        )
        c_u = (52.0, 21.0)
        c_v = (52.0, 21.02)

        # 1. Edge length shorter than step (20m): returns exact midpoint
        short_samples = evaluator._interpolate_edge_points(c_u, c_v, edge_len=15.0)
        assert len(short_samples) == 1
        assert short_samples[0] == pytest.approx((52.0, 21.01))

        # 2. Edge length 60m with step 20m: num_samples = 3 -> yields 2 internal fractional points
        long_samples = evaluator._interpolate_edge_points(c_u, c_v, edge_len=60.0)
        assert len(long_samples) == 2
        assert long_samples[0][1] == pytest.approx(21.0 + (1 / 3) * 0.02)
        assert long_samples[1][1] == pytest.approx(21.0 + (2 / 3) * 0.02)

    def test_evaluate_with_breakdown_unclosed_loop_returns_zero_fitness(
        self,
        simple_loop_graph,
        default_evaluator_params,
    ):
        """Returns zero fitness and infinite denominator when candidate route is not a closed loop."""
        evaluator = RouteEvaluator(
            stage_graphs=[simple_loop_graph],
            target_distance=1000.0,
            params=default_evaluator_params,
        )
        # Path does not return to start node
        unclosed_path = [0, 1, 2]
        breakdown = evaluator.evaluate_with_breakdown(unclosed_path, total_distance=850.0)

        assert breakdown.fitness == 0.0
        assert breakdown.denominator == float("inf")
        assert breakdown.dist_error_ratio == 1.0

    def test_marginal_distance_penalty_bracket_transition(
        self,
        default_evaluator_params,
    ):
        """Verifies piecewise linear penalty calculation below and above tolerance threshold."""
        evaluator = RouteEvaluator(
            stage_graphs=[],
            target_distance=1000.0,
            params=default_evaluator_params,
        )
        # Under threshold (0.05 <= 0.10): penalty = 0.05 * 1.0 = 0.05
        under_penalty = evaluator._calculate_marginal_distance_penalty(0.05)
        assert under_penalty == pytest.approx(0.05)

        # Over threshold (0.20 > 0.10):
        # Base bracket = 0.10 * 1.0 = 0.10
        # Excess = (0.20 - 0.10) * 3.0 = 0.30 -> Total = 0.40
        over_penalty = evaluator._calculate_marginal_distance_penalty(0.20)
        assert over_penalty == pytest.approx(0.40)

    def test_calculate_overlap_penalizes_out_and_back_outside_exclusion_zone(
        self,
        default_evaluator_params,
    ):
        """Penalizes repeated topological edges when they lie outside the start/finish exclusion zone."""
        # Exclusion zone covers start area (~100m) protecting edge (0, 1),
        # but leaves node 1 and edge (1, 2) (~500m - 1000m north) completely unprotected.
        default_evaluator_params.start_finish_exclusion_radius_meters = 100.0

        graph = nx.MultiDiGraph()
        # Node 0 at origin, node 1 and 2 placed ~550m and ~1100m north
        graph.add_node(0, y=52.000, x=21.000)
        graph.add_node(1, y=52.005, x=21.000)
        graph.add_node(2, y=52.010, x=21.000)

        graph.add_edge(0, 1, key=0, length=500.0)
        graph.add_edge(1, 0, key=0, length=500.0)
        graph.add_edge(1, 2, key=0, length=500.0)
        graph.add_edge(2, 1, key=0, length=500.0)

        evaluator = RouteEvaluator(
            stage_graphs=[graph],
            target_distance=2000.0,
            params=default_evaluator_params,
        )

        # Path: 0 -> 1 -> 2 -> 1 -> 0
        # Edge (0, 1) touches the start exclusion zone, so its repetition is not penalized.
        # Edge (1, 2) is completely outside the zone, so its repetition is penalized.
        path = [0, 1, 2, 1, 0]
        out_and_back, _ = evaluator.calculate_overlap_details(path)

        expected_penalty = 500.0 * default_evaluator_params.out_and_back_penalty_multiplier
        assert out_and_back == pytest.approx(expected_penalty)

    def test_perfect_loop_evaluation_breakdown(
        self,
        simple_loop_graph,
        default_evaluator_params,
    ):
        """Evaluates a clean loop matching the target distance with no overlap penalties."""
        # Configure generous exclusion zone to encompass the entire small test loop
        default_evaluator_params.start_finish_exclusion_radius_meters = 1000.0

        evaluator = RouteEvaluator(
            stage_graphs=[simple_loop_graph],
            target_distance=1450.0,
            params=default_evaluator_params,
        )
        loop_path = [0, 1, 2, 0]
        actual_distance = 1450.0  # Exactly matches target distance

        breakdown = evaluator.evaluate_with_breakdown(loop_path, total_distance=actual_distance)

        assert breakdown.dist_error_ratio == pytest.approx(0.0)
        assert breakdown.dist_penalty_term == pytest.approx(0.0)
        assert breakdown.total_overlap_meters == pytest.approx(0.0)
        assert breakdown.overlap_penalty_term == pytest.approx(0.0)
        assert breakdown.denominator == pytest.approx(1.0)
        assert breakdown.fitness == pytest.approx(1.0)
