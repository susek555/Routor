import math
from unittest.mock import MagicMock, patch

import networkx as nx
import pytest
from src.database.geo_point import GeoPoint
from src.generate_routes.algorithm.subgrapher import (
    EXPECTED_CHECKPOINT_COUNT,
    Subgrapher,
)

MODULE_PATH = Subgrapher.__module__


@pytest.fixture
def empty_map():
    return nx.MultiDiGraph()


@pytest.fixture
def square_loop_checkpoints():
    """Returns 4 GeoPoints forming a rough square loop of ~500m side length."""
    return [
        GeoPoint(latitude=52.2000, longitude=21.0000),  # CP0
        GeoPoint(latitude=52.2045, longitude=21.0000),  # CP1 (North)
        GeoPoint(latitude=52.2045, longitude=21.0075),  # CP2 (North-East)
        GeoPoint(latitude=52.2000, longitude=21.0075),  # CP3 (East)
    ]


@pytest.fixture
def linear_corridor_graph():
    """Builds a connected graph with main route, intermediate detour, and a dead-end stub.

    Nodes:
      - 0: Start node (lat 52.2000, lon 21.0000)
      - 1: Intermediate corridor node (lat 52.2020, lon 21.0000)
      - 2: End node (lat 52.2045, lon 21.0000)
      - 3: Dead-end stub branch connected only from node 1 (degree = 1 <= 1)
    """
    graph = nx.MultiDiGraph()
    graph.add_node(0, y=52.2000, x=21.0000)
    graph.add_node(1, y=52.2020, x=21.0000)
    graph.add_node(2, y=52.2045, x=21.0000)
    graph.add_node(3, y=52.2020, x=21.0005)

    # Main path 0 -> 1 -> 2
    graph.add_edge(0, 1, key=0, length=220.0)
    graph.add_edge(1, 2, key=0, length=280.0)

    # Single-edge dead-end stub 1 -> 3 (total degree of node 3 is 1 <= 1)
    graph.add_edge(1, 3, key=0, length=35.0)

    return graph


class TestSubgrapherExecutionFlow:
    @patch.object(Subgrapher, "_build_stage_subgraph")
    @patch.object(Subgrapher, "_extract_corridor_nodes")
    def test_extract_subgraphs_execution_flow(
        self,
        mock_extract_nodes,
        mock_build_subgraph,
        empty_map,
        square_loop_checkpoints,
    ):
        """Verifies iterative corridor extraction and stage construction across all 4 stages."""
        mock_extract_nodes.return_value = {1, 2, 3}
        mock_stage_graph = MagicMock()
        mock_build_subgraph.return_value = mock_stage_graph

        node_ids = [10, 20, 30, 40]
        results = Subgrapher.extract_subgraphs(
            map_graph=empty_map,
            checkpoints=square_loop_checkpoints,
            checkpoint_node_ids=node_ids,
            base_lateral_slack=150.0,
            max_lateral_slack=300.0,
        )

        # 4 stages expected: 0->1, 1->2, 2->3, 3->0
        assert mock_extract_nodes.call_count == EXPECTED_CHECKPOINT_COUNT
        assert mock_build_subgraph.call_count == EXPECTED_CHECKPOINT_COUNT
        assert len(results) == EXPECTED_CHECKPOINT_COUNT
        assert all(res == mock_stage_graph for res in results)

        # Check call arguments for the first stage
        mock_extract_nodes.assert_any_call(
            graph=empty_map,
            start_point=square_loop_checkpoints[0],
            end_point=square_loop_checkpoints[1],
            base_slack=150.0,
            max_slack=300.0,
        )
        mock_build_subgraph.assert_any_call(empty_map, {1, 2, 3}, 10, 20)

    def test_extract_subgraphs_early_exit_on_invalid_checkpoint_count(
        self,
        empty_map,
        square_loop_checkpoints,
    ):
        """Returns the full unsegmented graph copy if checkpoint count does not match expected size."""
        truncated_checkpoints = square_loop_checkpoints[:3]

        results = Subgrapher.extract_subgraphs(
            map_graph=empty_map,
            checkpoints=truncated_checkpoints,
        )

        assert len(results) == 1
        assert isinstance(results[0], nx.MultiDiGraph)


class TestSubgrapherUnitAndIntegration:
    def test_haversine_distance_accuracy(self):
        """Verifies great-circle haversine calculation against known approximate baseline."""
        # 1 degree of latitude is roughly 111.1 - 111.3 km
        lat1, lon1 = 52.0, 21.0
        lat2, lon2 = 53.0, 21.0

        dist = Subgrapher._haversine_distance(lat1, lon1, lat2, lon2)
        assert 111_000.0 < dist < 111_500.0

        # Coincident coordinates must yield 0 distance
        assert Subgrapher._haversine_distance(lat1, lon1, lat1, lon1) == pytest.approx(0.0)

    def test_is_node_in_corridor_or_buffer_radial_inclusion(self):
        """Confirms that points within endpoint radial buffer are included regardless of perimeter."""
        start = GeoPoint(latitude=52.0000, longitude=21.0000)
        end = GeoPoint(latitude=52.0100, longitude=21.0000)

        # Point situated ~100m north of start (well within CHECKPOINT_BUFFER_RADIUS_METERS = 250m)
        d_lat = (100.0 / 6371000.0) * (180.0 / math.pi)
        node_lat = start.latitude + d_lat
        node_lon = start.longitude

        # Even with an artificially restrictive max_perimeter, radial buffer inclusion prevails
        is_inside = Subgrapher._is_node_in_corridor_or_buffer(
            node_lat=node_lat,
            node_lon=node_lon,
            start_point=start,
            end_point=end,
            max_perimeter=0.0,
        )
        assert is_inside is True

    def test_extract_corridor_nodes_filters_distant_nodes(self, empty_map):
        """Nodes outside corridor envelope and buffer radius must be excluded."""
        start = GeoPoint(latitude=52.0000, longitude=21.0000)
        end = GeoPoint(latitude=52.0050, longitude=21.0000)

        # Node inside corridor (along midline)
        empty_map.add_node(1, y=52.0025, x=21.0000)
        # Node far away to the west (> 2 km)
        empty_map.add_node(2, y=52.0025, x=20.9500)
        # Node with missing coordinates
        empty_map.add_node(3)

        corridor_nodes = Subgrapher._extract_corridor_nodes(
            graph=empty_map,
            start_point=start,
            end_point=end,
            base_slack=100.0,
            max_slack=200.0,
        )

        assert 1 in corridor_nodes
        assert 2 not in corridor_nodes
        assert 3 not in corridor_nodes

    def test_prune_dead_ends_removes_unprotected_stubs(self, linear_corridor_graph):
        """Ensures that dead-end nodes with degree <= 1 are pruned while protected nodes stay intact."""
        # Unprotected dead-end node 3 should be removed
        pruned = Subgrapher._prune_dead_ends(linear_corridor_graph, protected_nodes={0, 2})
        assert 3 not in pruned.nodes
        assert {0, 1, 2}.issubset(pruned.nodes)

        # When node 3 is explicitly protected, it must survive
        pruned_protected = Subgrapher._prune_dead_ends(linear_corridor_graph, protected_nodes={0, 2, 3})
        assert 3 in pruned_protected.nodes

    def test_ensure_connected_nodes_falls_back_to_global_graph(self, empty_map):
        """Fetches missing bridging nodes from global graph when stage corridor is disconnected."""
        # Graph path: 1 -> 2 -> 3
        empty_map.add_node(1, y=52.0, x=21.0)
        empty_map.add_node(2, y=52.1, x=21.1)
        empty_map.add_node(3, y=52.2, x=21.2)
        empty_map.add_edge(1, 2, key=0, length=100.0)
        empty_map.add_edge(2, 3, key=0, length=100.0)

        # stage_nodes only contains disconnected endpoints 1 and 3
        stage_nodes = {1, 3}
        connected_nodes = Subgrapher._ensure_connected_nodes(
            graph=empty_map,
            stage_nodes=stage_nodes,
            source=1,
            target=3,
        )

        # Bridge node 2 should be automatically resolved and added
        assert connected_nodes == {1, 2, 3}

    def test_build_stage_subgraph_integration_flow(self, linear_corridor_graph):
        """Tests complete pipeline of subgraph building: connection guarantee + dead-end pruning."""
        stage_nodes = {0, 1, 2, 3}
        subgraph = Subgrapher._build_stage_subgraph(
            map_graph=linear_corridor_graph,
            stage_nodes=stage_nodes,
            source_node=0,
            target_node=2,
        )

        # Baseline shortest path is [0, 1, 2], so dead-end 3 must be pruned
        assert 0 in subgraph.nodes
        assert 1 in subgraph.nodes
        assert 2 in subgraph.nodes
        assert 3 not in subgraph.nodes
        assert nx.has_path(subgraph, 0, 2)
