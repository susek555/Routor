from unittest.mock import MagicMock, patch

import networkx as nx
import pytest
from shapely.geometry import LineString
from src.database.geo_point import GeoPoint
from src.generate_routes.graph_builder.graph_converter import GraphConverter


@pytest.fixture
def empty_map():
    return nx.MultiDiGraph()


@pytest.fixture
def linear_corridor_map():
    """Builds a linear directed chain: 1 -> 2 -> 3 -> 4, where nodes 2 and 3 have degree 2."""
    graph = nx.MultiDiGraph()
    graph.add_node(1, x=21.0, y=52.0)
    graph.add_node(2, x=21.1, y=52.1)
    graph.add_node(3, x=21.2, y=52.2)
    graph.add_node(4, x=21.3, y=52.3)

    graph.add_edge(1, 2, key=0, length=100.0)
    graph.add_edge(2, 3, key=0, length=100.0)
    graph.add_edge(3, 4, key=0, length=100.0)
    return graph


@pytest.fixture
def dead_end_map():
    """Builds a T-junction graph where node 2 is a 3-way junction.

    Topology:
      1 <-> 2 (short dead-end stub: length=30.0 < threshold 50.0)
      3 <-> 2 <-> 4 (main thoroughfare: 200.0m each side)
    Node 2 has degree 3, making it a true junction.
    """
    graph = nx.MultiDiGraph()
    for n, (lon, lat) in enumerate([(21.0, 52.0), (21.1, 52.1), (21.2, 52.2), (21.3, 52.3)], start=1):
        graph.add_node(n, x=lon, y=lat)

    # 1 <-> 2: short dead-end stub (length 30.0)
    graph.add_edge(1, 2, key=0, length=30.0)
    graph.add_edge(2, 1, key=0, length=30.0)

    # 3 <-> 2 <-> 4: main corridor through junction 2
    graph.add_edge(3, 2, key=0, length=200.0)
    graph.add_edge(2, 3, key=0, length=200.0)
    graph.add_edge(2, 4, key=0, length=200.0)
    graph.add_edge(4, 2, key=0, length=200.0)
    return graph


class TestGraphConverterExecutionFlow:
    @patch.object(GraphConverter, "_keep_largest_component")
    @patch.object(GraphConverter, "_prune_dead_ends")
    @patch.object(GraphConverter, "_contract_degree_two")
    def test_convert_graph_to_algorithm_execution_flow(
        self,
        mock_contract,
        mock_prune,
        mock_keep_largest,
        empty_map,
    ):
        """Verifies simplification pipeline sequence and private edge pruning."""
        # Set up a graph containing one private driveway and one public road
        empty_map.add_node(1, x=21.0, y=52.0)
        empty_map.add_node(2, x=21.1, y=52.1)
        empty_map.add_node(3, x=21.2, y=52.2)
        empty_map.add_edge(1, 2, key=0, service="driveway")
        empty_map.add_edge(2, 3, key=0, service="highway")

        contracted_mock = MagicMock()
        mock_contract.return_value = contracted_mock
        largest_comp_mock = MagicMock()
        mock_keep_largest.return_value = largest_comp_mock

        converter = GraphConverter(original_map=empty_map)
        protected_nodes = {1}
        result = converter.convert_graph_to_algorithm(protected_nodes=protected_nodes)

        # Step 1: Ensure private edges are stripped before passing to contraction
        mock_contract.assert_called_once()
        passed_graph = mock_contract.call_args[0][0]
        assert not passed_graph.has_edge(1, 2)
        assert passed_graph.has_edge(2, 3)

        # Step 2: Contract degree-2 corridors
        assert mock_contract.call_args[0][1] == protected_nodes

        # Step 3: Prune dead-end stubs
        mock_prune.assert_called_once_with(
            contracted_mock,
            converter.MIN_DEAD_END_LENGTH_METERS,
            protected_nodes,
        )

        # Step 4: Retain the largest connected component
        mock_keep_largest.assert_called_once_with(contracted_mock)
        assert result == largest_comp_mock
        assert converter.simplified_map == largest_comp_mock


class TestGraphConverterIntegration:
    def test_corridor_contraction_creates_macro_edge(self, linear_corridor_map):
        """Verifies that intermediate degree-2 nodes are collapsed into a single macro-edge."""
        converter = GraphConverter(original_map=linear_corridor_map)
        simplified = converter.convert_graph_to_algorithm()

        # Nodes 2 and 3 should be contracted away, leaving only terminals 1 and 4
        assert set(simplified.nodes) == {1, 4}
        assert simplified.has_edge(1, 4)

        macro_edge = simplified.get_edge_data(1, 4)[0]
        assert macro_edge["length"] == 300.0
        assert macro_edge["path_nodes"] == [1, 2, 3, 4]

    def test_protected_nodes_prevent_contraction(self, linear_corridor_map):
        """Protected nodes must remain intact regardless of their topological degree."""
        converter = GraphConverter(original_map=linear_corridor_map)
        # Protecting node 2 splits the corridor into 1 -> 2 and 2 -> 4
        simplified = converter.convert_graph_to_algorithm(protected_nodes={2})

        assert 2 in simplified.nodes
        assert simplified.has_edge(1, 2)
        assert simplified.has_edge(2, 4)

    def test_private_and_service_edges_filtering(self, empty_map):
        """Ensures access and service attributes filter out restricted road segments."""
        # Nodes 1, 2, and 3 forming a protected loop so valid segments survive dead-end pruning
        empty_map.add_node(1, x=21.0, y=52.0)
        empty_map.add_node(2, x=21.1, y=52.1)
        empty_map.add_node(3, x=21.2, y=52.2)

        # Restricted access edges between 1 and 2
        empty_map.add_edge(1, 2, key=0, access="private", length=100.0)
        empty_map.add_edge(1, 2, key=1, access=["permissive", "private"], length=100.0)
        empty_map.add_edge(1, 2, key=2, service="parking_aisle", length=100.0)
        empty_map.add_edge(1, 2, key=3, service="driveway", length=100.0)

        # Public edge that should survive filtering
        empty_map.add_edge(1, 2, key=4, access="public", length=100.0)

        # Closing cycle so edges are part of a loop and not pruned as dead ends
        empty_map.add_edge(2, 3, key=0, access="public", length=100.0)
        empty_map.add_edge(3, 1, key=0, access="public", length=100.0)

        converter = GraphConverter(original_map=empty_map)
        # Protect nodes to bypass degree-2 corridor contraction and isolate edge filtering check
        simplified = converter.convert_graph_to_algorithm(protected_nodes={1, 2, 3})

        remaining_edges_1_2 = simplified.get_edge_data(1, 2) or {}
        assert len(remaining_edges_1_2) == 1

        # MultiDiGraph reindexes macro-edge keys automatically; inspect edge attributes directly
        surviving_edge_attrs = next(iter(remaining_edges_1_2.values()))
        assert surviving_edge_attrs["length"] == 100.0
        assert surviving_edge_attrs["path_nodes"] == [1, 2]

    def test_prune_dead_ends_respects_threshold_and_protection(self, dead_end_map):
        """Dead ends under the length threshold are pruned unless explicitly protected."""
        # Unprotected: node 1 stub (length=30.0 < 50.0m) should be pruned
        converter = GraphConverter(original_map=dead_end_map, MIN_DEAD_END_LENGTH_METERS=50.0)
        simplified = converter.convert_graph_to_algorithm()
        assert 1 not in simplified.nodes
        assert 2 in simplified.nodes

        # Protected: node 1 must be preserved despite being a short dead-end stub
        converter_protected = GraphConverter(original_map=dead_end_map, MIN_DEAD_END_LENGTH_METERS=50.0)
        simplified_protected = converter_protected.convert_graph_to_algorithm(protected_nodes={1})
        assert 1 in simplified_protected.nodes

    def test_reconstruct_route_with_linestring_geometry(self, empty_map):
        """Verifies geometric reconstruction using underlying LineString data."""
        # Node 1 -> Node 2 with intermediate curvature stored in LineString
        empty_map.add_node(1, x=21.0, y=52.0)
        empty_map.add_node(2, x=21.2, y=52.2)

        curve = LineString([(21.0, 52.0), (21.1, 52.05), (21.2, 52.2)])
        empty_map.add_edge(1, 2, key=0, length=150.0, geometry=curve)

        converter = GraphConverter(original_map=empty_map)
        converter.simplified_map = empty_map

        route = converter.reconstruct_route_from_node_ids([1, 2])

        assert len(route) == 3
        assert all(isinstance(pt, GeoPoint) for pt in route)
        assert (route[0].latitude, route[0].longitude) == (52.0, 21.0)
        assert (route[1].latitude, route[1].longitude) == (52.05, 21.1)
        assert (route[2].latitude, route[2].longitude) == (52.2, 21.2)

    def test_reconstruct_route_fallback_to_node_coords_when_no_linestring(self, linear_corridor_map):
        """Falls back to straight node coordinates when edges lack LineString geometry."""
        converter = GraphConverter(original_map=linear_corridor_map)
        simplified = converter.convert_graph_to_algorithm()

        # Reconstruct path from simplified end nodes [1, 4]
        route = converter.reconstruct_route_from_node_ids([1, 4])

        assert len(route) == 4
        assert [pt.latitude for pt in route] == [52.0, 52.1, 52.2, 52.3]
        assert [pt.longitude for pt in route] == [21.0, 21.1, 21.2, 21.3]

    def test_reconstruct_route_single_or_empty_node_path(self, empty_map):
        """Returns direct point representations when path length is below minimum preservation threshold."""
        empty_map.add_node(10, x=21.01, y=52.22)
        converter = GraphConverter(original_map=empty_map)

        route = converter.reconstruct_route_from_node_ids([10])

        assert len(route) == 1
        assert route[0].latitude == 52.22
        assert route[0].longitude == 21.01
