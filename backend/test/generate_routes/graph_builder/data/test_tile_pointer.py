from dataclasses import FrozenInstanceError

import mercantile
import pytest
from src.generate_routes.graph_builder.data.tile_pointer import TilePointer


class TestTilePointer:
    def test_tile_pointer_initialization_and_id(self):
        pointer = TilePointer(x=100, y=200, z=14)

        assert pointer.x == 100
        assert pointer.y == 200
        assert pointer.z == 14
        assert pointer.id == "14_100_200"

    def test_tile_pointer_bounds_calculation(self):
        pointer = TilePointer(x=9145, y=5393, z=14)
        bounds = pointer.bounds

        assert isinstance(bounds, mercantile.LngLatBbox)
        assert bounds.west < bounds.east
        assert bounds.south < bounds.north

    def test_tile_pointer_is_immutable(self):
        pointer = TilePointer(x=100, y=200, z=14)

        with pytest.raises(FrozenInstanceError):
            pointer.x = 101
