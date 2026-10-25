from unittest.mock import MagicMock

import networkx as nx
import pytest
from src.generate_routes.algorithm.evaluator import RouteEvaluator
from src.generate_routes.algorithm.vns.detour_sampler import DetourSampler
from src.generate_routes.algorithm.vns.route_smoother import RouteSmoother
from src.generate_routes.algorithm.vns.vns_params import SmootherParams


@pytest.fixture
def default_smoother_params():
    return SmootherParams(
        min_nodes_to_smooth=6,
        min_smoothed_path_nodes=4,
        max_lookahead_nodes=5,
        min_shortcut_hop_diff=2,
        micro_spur_proximity_meters=25.0,
        min_distance_retention_ratio=0.50,
        default_fallback_edge_length=10.0,
    )


@pytest.fixture
def mock_evaluator():
    evaluator = MagicMock(spec=RouteEvaluator)
    evaluator.edge_info_cache = {}
    return evaluator


@pytest.fixture
def spur_graph():
    """Graph with an unnecessary detour spur: 0-1-2-3-4-5-6-7-8-0 where 2 and 5 are close."""
    g = nx.MultiDiGraph()
    # Coordinates: node 2 and node 5 are ~10m apart
    coords = {
        0: (52.000, 21.000),
        1: (52.001, 21.000),
        2: (52.002, 21.000),
        3: (52.005, 21.005),  # Out-of-the-way spur
        4: (52.005, 21.004),
        5: (52.002, 21.0001),  # Directly opposite node 2 (~7m)
        6: (52.001, 21.002),
        7: (52.000, 21.002),
        8: (52.000, 21.001),
    }
    for n, (y, x) in coords.items():
        g.add_node(n, y=y, x=x)

    # Shortcut edge between 2 and 5
    g.add_edge(2, 5, key=0, length=7.0)
    return g, coords


class TestRouteSmoother:
    def test_smooth_skips_short_paths(self, default_smoother_params, mock_evaluator):
        """Preserves paths shorter than min_nodes_to_smooth without modification."""
        sampler = MagicMock(spec=DetourSampler)
        smoother = RouteSmoother(
            params=default_smoother_params,
            evaluator=mock_evaluator,
            sampler=sampler,
            reference_graph=nx.MultiDiGraph(),
            target_distance=500.0,
        )

        short_path = [0, 1, 2]
        smoothed, dist = smoother.smooth(short_path)

        assert smoothed == short_path

    def test_smooth_replaces_micro_spur_with_direct_path(self, default_smoother_params, mock_evaluator, spur_graph):
        """Detects proximity between node 2 and 5 and cuts out intermediate spur nodes."""
        graph, coords = spur_graph
        sampler = MagicMock(spec=DetourSampler)
        sampler.get_coord.side_effect = lambda node, g: coords[node]

        smoother = RouteSmoother(
            params=default_smoother_params,
            evaluator=mock_evaluator,
            sampler=sampler,
            reference_graph=graph,
            target_distance=50.0,
        )

        full_path = [0, 1, 2, 3, 4, 5, 6, 7, 8, 0]
        smoothed, _ = smoother.smooth(full_path)

        # Nodes 3 and 4 should be bypassed by the direct connection (2 -> 5)
        assert 3 not in smoothed
        assert 4 not in smoothed
        assert smoothed == [0, 1, 2, 5, 6, 7, 8, 0]

    def test_smooth_anti_collapse_guard_restores_original_path(self, default_smoother_params, mock_evaluator):
        """Reverts smoothing if resulting distance collapses below min_distance_retention_ratio."""
        sampler = MagicMock(spec=DetourSampler)
        # Return valid dummy coordinates for each node
        sampler.get_coord.side_effect = lambda node, g: (52.0 + node * 0.001, 21.0)

        smoother = RouteSmoother(
            params=default_smoother_params,
            evaluator=mock_evaluator,
            sampler=sampler,
            reference_graph=nx.MultiDiGraph(),
            target_distance=10000.0,
        )

        smoother.calculate_path_distance = MagicMock(side_effect=[500.0, 50.0])

        full_path = list(range(12))
        smoothed, dist = smoother.smooth(full_path)

        assert smoothed == full_path
        assert dist == 500.0
