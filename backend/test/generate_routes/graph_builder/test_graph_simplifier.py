from unittest.mock import MagicMock, patch

import networkx as nx
import pytest
from src.generate_routes.graph_builder.graph_simplifier import GraphSimplifier


class TestGraphSimplifier:
    def test_simplify_empty_or_none_graph(self):
        """Verifies that empty graphs return untouched without exceptions."""
        empty_graph = nx.MultiDiGraph()
        assert GraphSimplifier.simplify(empty_graph) == empty_graph
        assert GraphSimplifier.simplify(None) is None

    @patch("src.generate_routes.graph_builder.graph_simplifier.ox.project_graph")
    @patch("src.generate_routes.graph_builder.graph_simplifier.ox.simplify_graph")
    def test_simplify_execution_flow(self, mock_simplify_graph, mock_project_graph):
        """Verifies the projection, KDTree clustering, and simplification pipeline."""
        # Budowa prostego grafu testowego w układzie UTM z dwoma bliskimi węzłami (odległość 5m)
        g_proj = nx.MultiDiGraph()
        g_proj.graph = {"crs": "epsg:32634"}
        g_proj.add_node(1, x=100.0, y=100.0)
        g_proj.add_node(2, x=103.0, y=104.0)  # odległość = 5m
        g_proj.add_node(3, x=200.0, y=200.0)  # odległy węzeł
        g_proj.add_edge(1, 2, length=5.0)
        g_proj.add_edge(2, 3, length=100.0)

        # Pierwsze wywołanie project_graph rzutuje do UTM, drugie z powrotem do WGS84
        mock_wgs84 = MagicMock()
        mock_wgs84.graph = {}
        mock_project_graph.side_effect = [g_proj, mock_wgs84]

        mock_final_graph = MagicMock()
        mock_simplify_graph.return_value = mock_final_graph

        input_graph = MagicMock()
        input_graph.nodes = [1, 2, 3]

        result = GraphSimplifier.simplify(input_graph, tolerance_meters=10.0)

        assert result == mock_final_graph
        mock_simplify_graph.assert_called_once_with(mock_wgs84)
        assert mock_wgs84.graph["simplified"] is False
