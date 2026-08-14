import mercantile
import osmnx as ox

from src.database.geo_point import GeoPoint
from src.generate_routes.graph_builder.data.tile_pointer import TilePointer


class TileResolver:
    ZOOM_LEVEL = 12

    @classmethod
    def resolve_tiles(cls, center: GeoPoint, radius_meters: float) -> list[TilePointer]:
        bbox = ox.utils_geo.bbox_from_point(
            (center.latitude, center.longitude),
            dist=radius_meters
        )
        west, south, east, north = bbox

        tiles_generator = mercantile.tiles(west, south, east, north, cls.ZOOM_LEVEL)

        return [
            TilePointer(x=t.x, y=t.y, z=t.z)
            for t in tiles_generator
        ]
