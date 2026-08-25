from unittest.mock import MagicMock, patch

import networkx as nx
import pytest
from src.database.geo_point import GeoPoint
from src.generate_routes.graph_builder.graph_builder import GraphBuilder


@pytest.fixture
def center_point():
    return GeoPoint(latitude=52.2297, longitude=21.0122)


class TestGraphBuilder:
    @patch("src.generate_routes.graph_builder.graph_builder.ox.distance.nearest_nodes")
    def test_calc_closest_node_id_passes_correct_coordinates(
        self, mock_nearest_nodes, center_point
    ):
        """Verifies that latitude and longitude are mapped to Y and X correctly."""
        mock_map = MagicMock()
        mock_nearest_nodes.return_value = 12345

        result = GraphBuilder._calc_closest_node_id(mock_map, center_point)

        assert result == 12345
        mock_nearest_nodes.assert_called_once_with(
            mock_map, X=center_point.longitude, Y=center_point.latitude
        )

    @patch("src.generate_routes.graph_builder.graph_builder.TileResolver.resolve_tiles")
    @patch("src.generate_routes.graph_builder.graph_builder.TileLoader.get_tiles")
    def test_build_graph_returns_empty_multidigraph_when_no_tiles(
        self, mock_get_tiles, mock_resolve, center_point
    ):
        """Verifies that an empty MultiDiGraph is returned if no tiles are loaded."""
        mock_resolve.return_value = ["mock_pointer_1"]
        mock_get_tiles.return_value = []

        result = GraphBuilder.build_graph(center_point, radius=1000.0)

        assert isinstance(result, nx.MultiDiGraph)
        assert len(result.nodes) == 0
        assert len(result.edges) == 0

    @patch("src.generate_routes.graph_builder.graph_builder.TileResolver.resolve_tiles")
    @patch("src.generate_routes.graph_builder.graph_builder.TileLoader.get_tiles")
    @patch("src.generate_routes.graph_builder.graph_builder.nx.compose_all")
    @patch("src.generate_routes.graph_builder.graph_builder.GraphBuilder._calc_closest_node_id")
    @patch("src.generate_routes.graph_builder.graph_builder.ox.truncate.truncate_graph_dist")
    def test_build_graph_execution_flow_with_custom_crs(
        self,
        mock_truncate,
        mock_calc_node,
        mock_compose,
        mock_get_tiles,
        mock_resolve,
        center_point,
    ):
        """Tests the complete flow preserving tile CRS metadata."""
        mock_tile_1 = MagicMock()
        mock_tile_1.graph = {"crs": "epsg:2180"}
        mock_tile_2 = MagicMock()
        mock_tile_2.graph = {"crs": "epsg:2180"}

        mock_resolve.return_value = ["mock_pointer_1", "mock_pointer_2"]
        mock_get_tiles.return_value = [mock_tile_1, mock_tile_2]

        mock_composed_map = MagicMock()
        mock_composed_map.graph = {}
        mock_compose.return_value = mock_composed_map

        mock_calc_node.return_value = 999
        mock_final_map = MagicMock()
        mock_truncate.return_value = mock_final_map

        radius = 2000.0

        result = GraphBuilder.build_graph(center_point, radius)

        assert result == mock_final_map
        assert mock_composed_map.graph["crs"] == "epsg:2180"

        mock_resolve.assert_called_once_with(center_point, radius)
        mock_get_tiles.assert_called_once_with(["mock_pointer_1", "mock_pointer_2"])
        mock_compose.assert_called_once_with([mock_tile_1, mock_tile_2])
        mock_calc_node.assert_called_once_with(mock_composed_map, center_point)
        mock_truncate.assert_called_once_with(mock_composed_map, 999, radius)

    @patch("src.generate_routes.graph_builder.graph_builder.TileResolver.resolve_tiles")
    @patch("src.generate_routes.graph_builder.graph_builder.TileLoader.get_tiles")
    @patch("src.generate_routes.graph_builder.graph_builder.nx.compose_all")
    @patch("src.generate_routes.graph_builder.graph_builder.GraphBuilder._calc_closest_node_id")
    @patch("src.generate_routes.graph_builder.graph_builder.ox.truncate.truncate_graph_dist")
    def test_build_graph_sets_default_crs_when_missing(
        self,
        mock_truncate,
        mock_calc_node,
        mock_compose,
        mock_get_tiles,
        mock_resolve,
        center_point,
    ):
        """Verifies that fallback 'epsg:4326' is set if tiles have no CRS."""
        mock_tile_no_crs = MagicMock(spec=[])
        mock_resolve.return_value = ["mock_pointer"]
        mock_get_tiles.return_value = [mock_tile_no_crs]

        mock_composed_map = MagicMock()
        mock_composed_map.graph = {}
        mock_compose.return_value = mock_composed_map

        GraphBuilder.build_graph(center_point, radius=500.0)

        assert mock_composed_map.graph["crs"] == "epsg:4326"
