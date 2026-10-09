from unittest.mock import patch

import mercantile
import pytest
from src.database.geo_point import GeoPoint
from src.generate_routes.data.tile_pointer import TilePointer
from src.generate_routes.graph_builder.tile_resolver import TileResolver


@pytest.fixture
def center_point():
    return GeoPoint(latitude=52.2297, longitude=21.0122)


class TestTileResolver:
    @patch("src.generate_routes.graph_builder.tile_resolver.ox.utils_geo.bbox_from_point")
    @patch("src.generate_routes.graph_builder.tile_resolver.mercantile.tiles")
    def test_resolve_tiles_execution_flow(self, mock_mercantile_tiles, mock_bbox_from_point, center_point):
        """Verifies that bbox parameters and mercantile tiles are correctly resolved into TilePointer list."""
        mock_bbox_from_point.return_value = (
            20.9,
            52.1,
            21.1,
            52.3,
        )  # west, south, east, north

        mock_tile_1 = mercantile.Tile(x=2300, y=1400, z=12)
        mock_tile_2 = mercantile.Tile(x=2301, y=1400, z=12)
        mock_mercantile_tiles.return_value = [mock_tile_1, mock_tile_2]

        radius = 1500.0
        results = TileResolver.resolve_tiles(center_point, radius)

        mock_bbox_from_point.assert_called_once_with((center_point.latitude, center_point.longitude), dist=radius)
        mock_mercantile_tiles.assert_called_once_with(20.9, 52.1, 21.1, 52.3, TileResolver.ZOOM_LEVEL)

        assert len(results) == 2
        assert all(isinstance(t, TilePointer) for t in results)
        assert results[0].x == 2300 and results[0].y == 1400 and results[0].z == 12
        assert results[1].x == 2301 and results[1].y == 1400 and results[1].z == 12

    def test_resolve_tiles_integration_real_coords(self, center_point):
        """Integration-level test checking real tile calculations without mocks."""
        radius = 1000.0  # 1 km
        results = TileResolver.resolve_tiles(center_point, radius)

        assert isinstance(results, list)
        assert len(results) > 0
        for pointer in results:
            assert isinstance(pointer, TilePointer)
            assert pointer.z == TileResolver.ZOOM_LEVEL
            assert isinstance(pointer.x, int)
            assert isinstance(pointer.y, int)
