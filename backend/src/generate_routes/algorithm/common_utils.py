import math

from src.generate_routes.data.map import Map


def haversine(coord1: tuple[float, float], coord2: tuple[float, float]) -> float:
    """Computes great-circle distance in meters between (lat1, lon1) and (lat2, lon2)."""
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    earth_radius = 6371000.0  # meters

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return 2.0 * earth_radius * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def get_node_coords(graph: Map, node: int) -> tuple[float, float]:
    """Extracts (latitude, longitude) from node attributes."""
    data = graph.nodes[node]
    lat = data.get("y", data.get("lat", 0.0))
    lon = data.get("x", data.get("lon", 0.0))
    return lat, lon


def get_min_edge_length(graph: Map, u: int, v: int) -> float:
    """Returns the minimal length among all parallel edges between u and v."""
    edge_dict = graph.get_edge_data(u, v)
    if not edge_dict:
        return 1.0
    return min(data.get("length", 1.0) for data in edge_dict.values())


def get_heading_rad(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    """Calculates directional heading angle in radians from point 1 to point 2."""
    lat1, lon1 = p1
    lat2, lon2 = p2
    return math.atan2(lat2 - lat1, lon2 - lon1)
