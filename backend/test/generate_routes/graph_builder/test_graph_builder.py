from unittest.mock import MagicMock, patch

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
    @patch("src.generate_routes.graph_builder.graph_builder.TileCacheManager.get_tiles")
    @patch("src.generate_routes.graph_builder.graph_builder.nx.compose_all")
    @patch(
        "src.generate_routes.graph_builder.graph_builder.GraphBuilder._calc_closest_node_id"
    )
    @patch(
        "src.generate_routes.graph_builder.graph_builder.ox.truncate.truncate_graph_dist"
    )
    def test_build_graph_execution_flow(
        self,
        mock_truncate,
        mock_calc_node,
        mock_compose,
        mock_get_tiles,
        mock_resolve,
        center_point,
    ):
        """Tests the complete data flow of the builder
        without executing real map logic."""

        # Setup mock returns
        mock_resolve.return_value = ["mock_pointer_1", "mock_pointer_2"]
        mock_get_tiles.return_value = ["mock_tile_1", "mock_tile_2"]

        mock_composed_map = MagicMock()
        mock_compose.return_value = mock_composed_map

        mock_calc_node.return_value = 999

        mock_final_map = MagicMock()
        mock_truncate.return_value = mock_final_map

        radius = 2000.0

        # Execute
        result = GraphBuilder.build_graph(center_point, radius)

        # Assert flow and parameter passing
        assert result == mock_final_map

        mock_resolve.assert_called_once_with(center_point, radius)
        mock_get_tiles.assert_called_once_with(["mock_pointer_1", "mock_pointer_2"])
        mock_compose.assert_called_once_with(["mock_tile_1", "mock_tile_2"])
        mock_calc_node.assert_called_once_with(mock_composed_map, center_point)
        mock_truncate.assert_called_once_with(mock_composed_map, 999, radius)
