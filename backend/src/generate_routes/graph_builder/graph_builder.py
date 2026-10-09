import networkx as nx
import osmnx as ox

from src.database.geo_point import GeoPoint
from src.generate_routes.data.map import Map
from src.generate_routes.graph_builder.tile_loader import TileLoader
from src.generate_routes.graph_builder.tile_resolver import TileResolver


class GraphBuilder:
    @classmethod
    def build_graph(cls, center: GeoPoint, radius: float) -> Map:
        tile_pointers = TileResolver.resolve_tiles(center, radius)
        tiles = TileLoader.get_tiles(tile_pointers)

        if not tiles:
            return nx.MultiDiGraph()

        merged_map = nx.compose_all(tiles)

        if tiles and hasattr(tiles[0], "graph") and "crs" in tiles[0].graph:
            merged_map.graph["crs"] = tiles[0].graph["crs"]
        else:
            merged_map.graph["crs"] = "epsg:4326"

        closest_node = cls._calc_closest_node_id(merged_map, center)
        truncated_map = ox.truncate.truncate_graph_dist(merged_map, closest_node, radius)

        return truncated_map

    @staticmethod
    def _calc_closest_node_id(map: Map, center: GeoPoint) -> int:
        return ox.distance.nearest_nodes(map, X=center.longitude, Y=center.latitude)
