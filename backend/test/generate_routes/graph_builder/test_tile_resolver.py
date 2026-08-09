from unittest.mock import patch

import mercantile
from src.database.geo_point import GeoPoint
from src.generate_routes.graph_builder.data.tile_pointer import TilePointer
from src.generate_routes.graph_builder.tile_resolver import TileResolver


class TestTileResolver:
    @patch("src.generate_routes.graph_builder.tile_resolver.mercantile.tiles")
    @patch(
        "src.generate_routes.graph_builder.tile_resolver.ox.utils_geo.bbox_from_point"
    )
    def test_resolve_tiles_calls_dependencies_correctly(self, mock_bbox, mock_tiles):
        """Mocked test checking data flow and correct argument passing."""
        mock_bbox.return_value = (10.0, 20.0, 30.0, 40.0)

        mock_tiles.return_value = [
            mercantile.Tile(x=100, y=200, z=14),
            mercantile.Tile(x=101, y=200, z=14),
        ]

        center = GeoPoint(latitude=52.2297, longitude=21.0122)
        radius = 1500.0

        result = TileResolver.resolve_tiles(center, radius)

        # Assert OSMnx bbox calculation was called correctly
        mock_bbox.assert_called_once_with((52.2297, 21.0122), dist=1500.0)

        # Assert mercantile was called with correct bbox unpacking and zoom level
        mock_tiles.assert_called_once_with(10.0, 20.0, 30.0, 40.0, 14)

        # Assert mapping to domain objects
        assert len(result) == 2
        assert isinstance(result[0], TilePointer)
        assert result[0].x == 100
        assert result[0].y == 200
        assert result[0].z == 14
        assert result[1].x == 101

    def test_resolve_tiles_real_math_execution(self):
        """Integration test executing real math logic without network requests."""
        # Warsaw center
        center = GeoPoint(latitude=52.2297, longitude=21.0122)
        radius = 500.0

        result = TileResolver.resolve_tiles(center, radius)

        assert len(result) > 0
        assert all(isinstance(tile, TilePointer) for tile in result)
        assert all(tile.z == 14 for tile in result)
