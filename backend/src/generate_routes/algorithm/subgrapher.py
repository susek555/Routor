import math

import networkx as nx

from src.database.geo_point import GeoPoint
from src.generate_routes.data.map import Map

# Buffer radius around checkpoint endpoints to ensure multiple entry/exit streets
CHECKPOINT_BUFFER_RADIUS_METERS = 500.0

# Lateral slack bounds for elliptical stage corridor
BASE_LATERAL_SLACK_METERS = 500.0
MAX_LATERAL_SLACK_METERS = 1000.0
SLACK_FOCAL_GROWTH_FACTOR = 0.20

# Expected checkpoint count for standard 4-stage loop partitioning
EXPECTED_CHECKPOINT_COUNT = 4


class Subgrapher:
    """Extracts, buffers, and prunes stage subgraphs along sequential checkpoint corridors."""

    @staticmethod
    def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculates the great-circle distance in meters between two points on Earth."""
        earth_radius_meters = 6371000.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        haversine_formula = (
            math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
        )
        return 2.0 * earth_radius_meters * math.atan2(math.sqrt(haversine_formula), math.sqrt(1.0 - haversine_formula))

    @classmethod
    def _is_node_in_corridor_or_buffer(
        cls,
        node_lat: float,
        node_lon: float,
        start_point: GeoPoint,
        end_point: GeoPoint,
        max_perimeter: float,
    ) -> bool:
        """Checks if coordinates lie within either the ellipse perimeter or checkpoint buffer spheres."""
        dist_start = cls._haversine_distance(start_point.latitude, start_point.longitude, node_lat, node_lon)
        dist_end = cls._haversine_distance(node_lat, node_lon, end_point.latitude, end_point.longitude)

        # 1. Checkpoint sphere buffers (provides topological bypasses around tight junctions)
        if dist_start <= CHECKPOINT_BUFFER_RADIUS_METERS or dist_end <= CHECKPOINT_BUFFER_RADIUS_METERS:
            return True

        # 2. Main elliptical corridor boundary
        return (dist_start + dist_end) <= max_perimeter

    @classmethod
    def _extract_corridor_nodes(
        cls,
        graph: Map,
        start_point: GeoPoint,
        end_point: GeoPoint,
        base_slack: float,
        max_slack: float,
    ) -> set[int]:
        """Extracts node IDs situated within the corridor ellipse and checkpoint radial buffers."""
        focal_dist = cls._haversine_distance(
            start_point.latitude, start_point.longitude, end_point.latitude, end_point.longitude
        )
        c = focal_dist / 2.0

        semi_minor_b = min(base_slack + SLACK_FOCAL_GROWTH_FACTOR * focal_dist, max_slack)
        semi_major_a = math.hypot(c, semi_minor_b)
        max_perimeter = 2.0 * semi_major_a

        corridor_node_ids: set[int] = set()
        for node_id, node_attrs in graph.nodes(data=True):
            lat = node_attrs.get("y", node_attrs.get("lat"))
            lon = node_attrs.get("x", node_attrs.get("lon"))
            if lat is None or lon is None:
                continue

            if cls._is_node_in_corridor_or_buffer(lat, lon, start_point, end_point, max_perimeter):
                corridor_node_ids.add(node_id)

        return corridor_node_ids

    @staticmethod
    def _prune_dead_ends(graph: nx.Graph, protected_nodes: set[int]) -> nx.Graph:
        """Iteratively removes dead-end nodes (degree <= 1), preserving protected route nodes."""
        pruned_graph = graph.copy()

        while True:
            dead_ends = [
                node for node in pruned_graph.nodes if node not in protected_nodes and pruned_graph.degree(node) <= 1
            ]
            if not dead_ends:
                break
            pruned_graph.remove_nodes_from(dead_ends)

        return pruned_graph

    @classmethod
    def _ensure_connected_nodes(
        cls,
        graph: Map,
        stage_nodes: set[int],
        source: int,
        target: int,
    ) -> set[int]:
        """Guarantees at least one traversable path between source and target."""
        stage_nodes.update((source, target))
        if not nx.has_path(graph.subgraph(stage_nodes), source, target):
            try:
                fallback_path = nx.shortest_path(graph, source=source, target=target, weight="length")
                stage_nodes.update(fallback_path)
            except nx.NetworkXNoPath:
                pass
        return stage_nodes

    @classmethod
    def _build_stage_subgraph(
        cls,
        map_graph: Map,
        stage_nodes: set[int],
        source_node: int | None,
        target_node: int | None,
    ) -> Map:
        """Builds, connects, and prunes dead ends for a single stage corridor."""
        if source_node is None or target_node is None:
            return map_graph.subgraph(stage_nodes).copy()

        connected_nodes = cls._ensure_connected_nodes(map_graph, stage_nodes, source_node, target_node)
        subgraph: Map = map_graph.subgraph(connected_nodes).copy()

        if nx.has_path(subgraph, source_node, target_node):
            try:
                baseline_path = nx.shortest_path(subgraph, source=source_node, target=target_node, weight="length")
                protected = set(baseline_path)
            except nx.NetworkXNoPath:
                protected = {source_node, target_node}
            return cls._prune_dead_ends(subgraph, protected_nodes=protected)

        return subgraph

    @classmethod
    def extract_subgraphs(
        cls,
        map_graph: Map,
        checkpoints: list[GeoPoint],
        checkpoint_node_ids: list[int] | None = None,
        base_lateral_slack: float = BASE_LATERAL_SLACK_METERS,
        max_lateral_slack: float = MAX_LATERAL_SLACK_METERS,
    ) -> list[Map]:
        """Slices map into sequential stage subgraphs with elliptical corridors and node buffers."""
        if len(checkpoints) != EXPECTED_CHECKPOINT_COUNT:
            return [map_graph.copy()]

        pts = list(checkpoints) + [checkpoints[0]]
        nodes = list(checkpoint_node_ids) + [checkpoint_node_ids[0]] if checkpoint_node_ids else None

        stage_subgraphs: list[Map] = []
        for i in range(len(pts) - 1):
            stage_nodes = cls._extract_corridor_nodes(
                graph=map_graph,
                start_point=pts[i],
                end_point=pts[i + 1],
                base_slack=base_lateral_slack,
                max_slack=max_lateral_slack,
            )

            src = nodes[i] if nodes else None
            tgt = nodes[i + 1] if nodes else None

            stage_subgraphs.append(cls._build_stage_subgraph(map_graph, stage_nodes, src, tgt))

        return stage_subgraphs
