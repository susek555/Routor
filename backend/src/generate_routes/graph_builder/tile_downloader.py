import networkx as nx
import osmnx as ox

from src.generate_routes.graph_builder.data.map_tile import MapTile
from src.generate_routes.graph_builder.data.tile_pointer import TilePointer


class TileDownloader:
    @staticmethod
    def download_tile(tile_pointer: TilePointer, network_type: str = "walk") -> MapTile:
        b = tile_pointer.bounds

        try:
            graph = ox.graph_from_bbox(
                bbox=(b.north, b.south, b.east, b.west), network_type=network_type
            )
            return graph
        except Exception:
            # empty graph fallback (TODO, not good)
            return nx.MultiDiGraph()
