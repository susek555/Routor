import networkx as nx
import osmnx as ox

from src.database.geo_point import GeoPoint
from src.generate_routes.graph_builder.data.map import Map
from src.generate_routes.graph_builder.tile_loader import TileLoader
from src.generate_routes.graph_builder.tile_resolver import TileResolver


class GraphBuilder:
    @classmethod
    def build_graph(cls, center: GeoPoint, radius: float) -> Map:
        # 10% margin with radius
        RADIUS_MULT = 1.1

        radius = radius * RADIUS_MULT

        tile_pointers = TileResolver.resolve_tiles(center, radius)
        tiles = TileLoader.get_tiles(tile_pointers)

        if not tiles:
            return nx.MultiDiGraph()

        map = nx.compose_all(tiles)

        if tiles and hasattr(tiles[0], "graph") and "crs" in tiles[0].graph:
            map.graph["crs"] = tiles[0].graph["crs"]
        else:
            map.graph["crs"] = "epsg:4326"

        return ox.truncate.truncate_graph_dist(map, cls._calc_closest_node_id(map, center), radius)

    @staticmethod
    def _calc_closest_node_id(map: Map, center: GeoPoint) -> int:
        return ox.distance.nearest_nodes(map, X=center.longitude, Y=center.latitude)
