import math
from typing import Any

import numpy as np
from scipy.spatial import KDTree

from src.database.geo_point import GeoPoint
from src.generate_routes.data.map import Map


class Snapper:
    """
    Snaps arbitrary geographic coordinates onto the closest valid nodes in the raw OSM graph.
    Requires that the candidate node has at least one incident edge that is not tagged as highway='service'
    (preventing waypoints from landing on private driveways, warehouse yards, or company facilities).
    """

    def __init__(self, raw_map: Map):
        self.raw_graph: Map = raw_map
        self.valid_node_ids: list[int] = []
        self._kdtree: KDTree | None = None
        self._lat_scale: float = 111_320.0
        self._lon_scale: float = 111_320.0

        self._build_index()

    @staticmethod
    def _is_service_edge(edge_attrs: dict[str, Any]) -> bool:
        """Checks if the edge's highway tag represents exclusively a service road."""
        highway_tag = edge_attrs.get("highway")
        if not highway_tag:
            return False
        if isinstance(highway_tag, str):
            return highway_tag.strip().lower() == "service"
        if isinstance(highway_tag, (list, tuple, set)):
            return all(str(item).strip().lower() == "service" for item in highway_tag)
        return False

    def _is_valid_node(self, node_id: int) -> bool:
        """
        Validates whether a node touches at least one public/non-service edge.
        Nodes connected exclusively to highway='service' edges are rejected.
        """
        incident_edges = list(self.raw_graph.out_edges(node_id, data=True)) + list(
            self.raw_graph.in_edges(node_id, data=True)
        )
        if not incident_edges:
            return False

        return any(not self._is_service_edge(attrs) for _, _, attrs in incident_edges)

    def _build_index(self) -> None:
        """Builds a metric 2D KDTree index of eligible non-service nodes."""
        coords_meters: list[list[float]] = []
        node_latitudes: list[float] = []

        for node_id, node_attrs in self.raw_graph.nodes(data=True):
            lat = node_attrs.get("y", node_attrs.get("lat"))
            lon = node_attrs.get("x", node_attrs.get("lon"))
            if lat is None or lon is None:
                continue

            if self._is_valid_node(node_id):
                self.valid_node_ids.append(node_id)
                node_latitudes.append(lat)

        if not self.valid_node_ids:
            return

        # Calculate metric projection scales using the mean latitude
        ref_lat = float(np.mean(node_latitudes))
        self._lat_scale = 111_320.0
        self._lon_scale = 111_320.0 * math.cos(math.radians(ref_lat))

        for node_id in self.valid_node_ids:
            node_attrs = self.raw_graph.nodes[node_id]
            lat = node_attrs.get("y", node_attrs.get("lat"))
            lon = node_attrs.get("x", node_attrs.get("lon"))
            coords_meters.append([lon * self._lon_scale, lat * self._lat_scale])

        self._kdtree = KDTree(coords_meters)

    def snap_point(self, point: GeoPoint) -> tuple[int, GeoPoint]:
        """
        Snaps a single GeoPoint to the nearest valid non-service node in O(log N) time.
        Returns: (node_id, GeoPoint_with_exact_node_coordinates)
        """
        if self._kdtree is None or not self.valid_node_ids:
            raise ValueError("No valid non-service nodes found in raw graph for snapping.")

        target_x = point.longitude * self._lon_scale
        target_y = point.latitude * self._lat_scale

        _, nearest_idx = self._kdtree.query([target_x, target_y])
        best_node_id = self.valid_node_ids[nearest_idx]
        node_attrs = self.raw_graph.nodes[best_node_id]

        snapped_point = GeoPoint(
            latitude=node_attrs.get("y", node_attrs.get("lat")),
            longitude=node_attrs.get("x", node_attrs.get("lon")),
        )
        return best_node_id, snapped_point

    def snap_points(self, points: list[GeoPoint]) -> list[tuple[int, GeoPoint]]:
        """Snaps a list of GeoPoints to the nearest valid non-service nodes."""
        return [self.snap_point(point) for point in points]
