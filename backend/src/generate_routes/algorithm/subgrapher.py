import math

import networkx as nx

from src.database.geo_point import GeoPoint
from src.generate_routes.data.map import Map


class Subgrapher:
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
    def _extract_corridor_nodes(
        cls,
        graph: Map,
        start_point: GeoPoint,
        end_point: GeoPoint,
        slack_ratio: float,
        min_slack_meters: float,
    ) -> set[int]:
        """Extracts node IDs situated within the geometric elliptic corridor between two points."""
        euclidean_distance = cls._haversine_distance(
            start_point.latitude, start_point.longitude, end_point.latitude, end_point.longitude
        )
        max_corridor_perimeter = (1.0 + slack_ratio) * euclidean_distance + min_slack_meters

        corridor_node_ids: set[int] = set()
        for node_id, node_attrs in graph.nodes(data=True):
            lat = node_attrs.get("y", node_attrs.get("lat"))
            lon = node_attrs.get("x", node_attrs.get("lon"))
            if lat is None or lon is None:
                continue

            dist_to_start = cls._haversine_distance(start_point.latitude, start_point.longitude, lat, lon)
            dist_to_end = cls._haversine_distance(lat, lon, end_point.latitude, end_point.longitude)

            if (dist_to_start + dist_to_end) <= max_corridor_perimeter:
                corridor_node_ids.add(node_id)

        return corridor_node_ids

    @classmethod
    def extract_subgraphs(
        cls,
        map: Map,
        checkpoints: list[GeoPoint],
        checkpoint_node_ids: list[int] | None = None,
        slack_ratio: float = 0.30,
        min_slack_meters: float = 150.0,
    ) -> list[Map]:
        """
        Slices the simplified graph into 4 sequential stage subgraphs along elliptic corridors.
        Guarantees graph connectivity: if no route exists within the corridor (common in sparse rural areas),
        it falls back to computing the global shortest path and adds its nodes to the stage subgraph.
        """
        EXPECTED_CHECKPOINT_COUNT = 4

        if len(checkpoints) != EXPECTED_CHECKPOINT_COUNT:
            return [map.copy()]

        closed_checkpoints = list(checkpoints)
        if checkpoints[0] != checkpoints[-1]:
            closed_checkpoints.append(checkpoints[0])

        closed_node_ids = None
        if checkpoint_node_ids:
            closed_node_ids = list(checkpoint_node_ids)
            if checkpoint_node_ids[0] != checkpoint_node_ids[-1]:
                closed_node_ids.append(checkpoint_node_ids[0])

        stage_subgraphs: list[Map] = []

        for step_idx in range(len(closed_checkpoints) - 1):
            start_point = closed_checkpoints[step_idx]
            end_point = closed_checkpoints[step_idx + 1]

            stage_nodes = cls._extract_corridor_nodes(
                graph=map,
                start_point=start_point,
                end_point=end_point,
                slack_ratio=slack_ratio,
                min_slack_meters=min_slack_meters,
            )

            # Connectivity guarantee: append global fallback path if corridor is disconnected
            if closed_node_ids is not None:
                source_node = closed_node_ids[step_idx]
                target_node = closed_node_ids[step_idx + 1]
                stage_nodes.add(source_node)
                stage_nodes.add(target_node)

                candidate_subgraph = map.subgraph(stage_nodes)
                if not nx.has_path(candidate_subgraph, source_node, target_node):
                    try:
                        fallback_path = nx.shortest_path(map, source=source_node, target=target_node, weight="length")
                        stage_nodes.update(fallback_path)
                    except nx.NetworkXNoPath:
                        pass

            stage_subgraph: Map = map.subgraph(stage_nodes).copy()
            stage_subgraphs.append(stage_subgraph)

        return stage_subgraphs
