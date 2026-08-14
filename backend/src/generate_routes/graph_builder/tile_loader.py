import os
import pickle

import networkx as nx

from src.generate_routes.graph_builder.data.map_tile import MapTile
from src.generate_routes.graph_builder.data.tile_pointer import TilePointer


class TileLoader:
    TILES_DIR = "/app/tiles_data"

    @classmethod
    def get_tiles(cls, tile_pointers: list[TilePointer]) -> list[MapTile]:
        tiles = []
        for pointer in tile_pointers:
            tile = cls._load_from_disk(pointer)
            if len(tile.nodes) > 0:
                tiles.append(tile)
        return tiles

    @classmethod
    def _load_from_disk(cls, pointer: TilePointer) -> MapTile:
        file_path = os.path.join(cls.TILES_DIR, f"{pointer.id}.pkl")

        if not os.path.exists(file_path):
            return nx.MultiDiGraph()

        try:
            with open(file_path, "rb") as f:
                return pickle.load(f)  # noqa: S301
        except Exception as e:
            print(f"Error loading tile {pointer.id}: {e}")
            return nx.MultiDiGraph()
