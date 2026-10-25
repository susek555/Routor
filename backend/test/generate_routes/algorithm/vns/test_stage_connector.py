from unittest.mock import MagicMock

import networkx as nx
import pytest
from src.generate_routes.algorithm.evaluator import RouteEvaluator
from src.generate_routes.algorithm.vns.stage_connector import StageConnector


@pytest.fixture
def mock_evaluator():
    evaluator = MagicMock(spec=RouteEvaluator)
    evaluator.edge_info_cache = {
        (0, 1): ([], 100.0),
        (1, 0): ([], 100.0),
        (1, 2): ([], 80.0),
        (2, 1): ([], 80.0),
        (2, 0): ([], 200.0),
        (0, 2): ([], 200.0),
        (1, 3): ([], 50.0),
        (3, 2): ([], 50.0),
    }
    evaluator.evaluate.return_value = 0.95
    return evaluator


@pytest.fixture
def simple_stage_graph():
    """Creates a basic directed graph with an alternative detour path."""
    g = nx.MultiDiGraph()
    g.add_node(0, y=52.000, x=21.000)
    g.add_node(1, y=52.005, x=21.000)
    g.add_node(2, y=52.005, x=21.005)
    g.add_node(3, y=52.010, x=21.005)

    g.add_edge(0, 1, key=0, length=100.0)
    g.add_edge(1, 2, key=0, length=80.0)
    g.add_edge(1, 3, key=0, length=50.0)
    g.add_edge(3, 2, key=0, length=50.0)
    return g


class TestStageConnector:
    def test_try_connect_stage_strict_detects_overlap(self, simple_stage_graph, mock_evaluator):
        """Fails strict connection when waypoints force node re-visitation."""
        connector = StageConnector(stage_graphs=[simple_stage_graph], evaluator=mock_evaluator)

        # Path: 0 -> 1 -> 3 -> 1 (node 1 repeated)
        waypoints = [0, 1, 3, 1]
        path, dist = connector._try_connect_stage(simple_stage_graph, waypoints, allow_overlap=False)

        assert path == []
        assert dist == 0.0

    def test_try_connect_stage_soft_allows_overlap(self, simple_stage_graph, mock_evaluator):
        """Allows repeated nodes when allow_overlap is set to True."""
        mock_evaluator.edge_info_cache[(3, 1)] = ([], 50.0)
        simple_stage_graph.add_edge(3, 1, key=0, length=50.0)

        connector = StageConnector(stage_graphs=[simple_stage_graph], evaluator=mock_evaluator)
        waypoints = [0, 1, 3, 1]

        path, dist = connector._try_connect_stage(simple_stage_graph, waypoints, allow_overlap=True)

        assert path == [0, 1, 3, 1]
        assert dist == pytest.approx(200.0)

    def test_connect_stage_fallback_to_chord_when_intermediate_unreachable(
        self, simple_stage_graph, mock_evaluator
    ):
        """Falls back to base chord (waypoints[0] -> waypoints[-1]) if detour node is disconnected."""
        simple_stage_graph.add_node(999, y=53.0, x=22.0)
        connector = StageConnector(stage_graphs=[simple_stage_graph], evaluator=mock_evaluator)

        waypoints = [0, 999, 2]
        path, dist = connector.connect_stage(0, waypoints)

        assert path == [0, 1, 2]
        assert dist == pytest.approx(180.0)

    def test_connect_stage_global_emergency_fallback(
        self, simple_stage_graph, mock_evaluator
    ):
        """Reaches for global graph if stage graph has no connectivity."""
        isolated_graph = nx.MultiDiGraph()
        isolated_graph.add_node(0, y=52.0, x=21.0)
        isolated_graph.add_node(2, y=52.005, x=21.005)

        mock_evaluator.graph = simple_stage_graph

        connector = StageConnector(stage_graphs=[isolated_graph], evaluator=mock_evaluator)
        waypoints = [0, 2]

        path, dist = connector.connect_stage(0, waypoints)

        assert path == [0, 1, 2]
        assert dist == pytest.approx(180.0)

    def test_evaluate_candidate_stages_glues_loop_correctly(self, simple_stage_graph, mock_evaluator):
        """Correctly connects multiple stages into a seamless loop without duplicate junction nodes."""
        g1 = nx.MultiDiGraph()
        g1.add_edge(0, 1, key=0, length=100.0)
        g2 = nx.MultiDiGraph()
        g2.add_edge(1, 0, key=0, length=100.0)

        connector = StageConnector(stage_graphs=[g1, g2], evaluator=mock_evaluator)
        stage_wps = [[0, 1], [1, 0]]

        full_path, total_dist, fitness = connector.evaluate_candidate_stages(stage_wps)

        # 0 -> 1 glued with 1 -> 0 should result in [0, 1, 0]
        assert full_path == [0, 1, 0]
        assert total_dist == pytest.approx(200.0)
        assert fitness == 0.95
        mock_evaluator.evaluate.assert_called_once_with([0, 1, 0], total_distance=200.0)
