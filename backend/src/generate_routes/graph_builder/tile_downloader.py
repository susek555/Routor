import networkx as nx
import osmnx as ox

from src.generate_routes.graph_builder.data.map_tile import MapTile
from src.generate_routes.graph_builder.data.tile_pointer import TilePointer

ox.settings.timeout = 180
ox.settings.overpass_endpoint = "https://overpass.kumi.systems/api/interpreter"


class TileDownloader:
    @staticmethod
    def download_tile(tile_pointer: TilePointer, network_type: str = "walk") -> MapTile:
        b = tile_pointer.bounds

        try:
            graph = ox.graph_from_bbox(
                bbox=(b.west, b.south, b.east, b.north),
                network_type=network_type,
                retain_all=True,
            )
            return graph
        except Exception as e:
            print(f"⚠️ Błąd pobierania kafelka {tile_pointer.id}: {e}")
            return nx.MultiDiGraph()
