from unittest.mock import patch

import networkx as nx
import pytest
from src.database.geo_point import GeoPoint
from src.generate_routes.algorithm.snapper import Snapper

MODULE_PATH = Snapper.__module__


@pytest.fixture
def empty_map():
    return nx.MultiDiGraph()


@pytest.fixture
def graph_with_service_and_public_nodes():
    """Builds a test graph with mixed edge types:

    - Node 1: Public node connected via highway='residential'
    - Node 2: Intermediate node connected to Node 1 (public) and Node 3 (service)
    - Node 3: Exclusively private service node (all incident edges are highway='service')
    - Node 4: Isolated node with no edges
    """
    graph = nx.MultiDiGraph()
    # Coordinates in Warsaw area (lat ~52.2, lon ~21.0)
    graph.add_node(1, y=52.2300, x=21.0100)
    graph.add_node(2, y=52.2310, x=21.0110)
    graph.add_node(3, y=52.2320, x=21.0120)
    graph.add_node(4, y=52.2330, x=21.0130)

    # Public edge between 1 and 2
    graph.add_edge(1, 2, key=0, highway="residential")

    # Service edges connecting to 3
    graph.add_edge(2, 3, key=0, highway="service")
    graph.add_edge(3, 2, key=0, highway="service")

    return graph


class TestSnapperExecutionFlow:
    @patch.object(Snapper, "_build_index")
    def test_init_calls_build_index(self, mock_build_index, empty_map):
        """Verifies that KDTree initialization runs automatically upon instantiation."""
        snapper = Snapper(raw_map=empty_map)

        mock_build_index.assert_called_once()
        assert snapper.raw_graph == empty_map
        assert snapper.valid_node_ids == []
        assert snapper._kdtree is None

    def test_snap_points_delegates_to_snap_point(self, empty_map):
        """Verifies snap_points iterates and invokes snap_point for each item."""
        snapper = Snapper(raw_map=empty_map)
        dummy_point_1 = GeoPoint(latitude=52.0, longitude=21.0)
        dummy_point_2 = GeoPoint(latitude=52.1, longitude=21.1)

        mock_result_1 = (1, dummy_point_1)
        mock_result_2 = (2, dummy_point_2)

        with patch.object(snapper, "snap_point", side_effect=[mock_result_1, mock_result_2]) as mock_snap:
            results = snapper.snap_points([dummy_point_1, dummy_point_2])

            assert mock_snap.call_count == 2
            assert results == [mock_result_1, mock_result_2]


class TestSnapperUnitAndIntegration:
    @pytest.mark.parametrize(
        ("edge_attrs", "expected_is_service"),
        [
            ({"highway": "service"}, True),
            ({"highway": "SERVICE"}, True),
            ({"highway": " service "}, True),
            ({"highway": ["service", "service"]}, True),
            ({"highway": ["residential", "service"]}, False),
            ({"highway": "residential"}, False),
            ({"highway": "footway"}, False),
            ({}, False),
        ],
    )
    def test_is_service_edge_tag_parsing(self, edge_attrs, expected_is_service):
        """Validates identification of service tags in string, sequence, and empty formats."""
        assert Snapper._is_service_edge(edge_attrs) is expected_is_service

    def test_node_filtering_rejects_pure_service_and_isolated_nodes(self, graph_with_service_and_public_nodes):
        """Ensures nodes exclusively touching service roads or isolated nodes are filtered out."""
        snapper = Snapper(raw_map=graph_with_service_and_public_nodes)

        # Node 1 touches residential (valid)
        # Node 2 touches residential and service (valid, has at least one non-service edge)
        # Node 3 touches ONLY service edges (rejected)
        # Node 4 has no incident edges (rejected)
        assert set(snapper.valid_node_ids) == {1, 2}
        assert snapper._kdtree is not None
        assert snapper._kdtree.n == 2

    def test_snap_point_selects_closest_valid_node(self, graph_with_service_and_public_nodes):
        """Verifies point snapping avoids closer service nodes and chooses nearest valid node."""
        snapper = Snapper(raw_map=graph_with_service_and_public_nodes)

        # Target point is placed very close to Node 3 (lat=52.2320, lon=21.0120),
        # but Node 3 is an invalid service-only node. Nearest valid node is Node 2.
        query_point = GeoPoint(latitude=52.2319, longitude=21.0119)
        node_id, snapped_geo = snapper.snap_point(query_point)

        assert node_id == 2
        assert isinstance(snapped_geo, GeoPoint)
        assert snapped_geo.latitude == 52.2310
        assert snapped_geo.longitude == 21.0110

    def test_snap_point_supports_lat_lon_fallback_keys(self, empty_map):
        """Verifies graph attribute fallbacks ('lat'/'lon' instead of 'y'/'x')."""
        empty_map.add_node(10, lat=52.25, lon=21.05)
        empty_map.add_edge(10, 10, key=0, highway="primary")

        snapper = Snapper(raw_map=empty_map)
        node_id, snapped_geo = snapper.snap_point(GeoPoint(latitude=52.251, longitude=21.051))

        assert node_id == 10
        assert snapped_geo.latitude == 52.25
        assert snapped_geo.longitude == 21.05

    def test_snap_point_raises_error_when_no_valid_nodes(self, empty_map):
        """Raises ValueError when raw graph does not contain any eligible non-service nodes."""
        empty_map.add_node(1, y=52.0, x=21.0)
        empty_map.add_edge(1, 1, key=0, highway="service")

        snapper = Snapper(raw_map=empty_map)

        assert snapper.valid_node_ids == []
        assert snapper._kdtree is None
        with pytest.raises(ValueError, match="No valid non-service nodes found"):
            snapper.snap_point(GeoPoint(latitude=52.0, longitude=21.0))
