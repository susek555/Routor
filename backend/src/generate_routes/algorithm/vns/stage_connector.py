import networkx as nx
from src.generate_routes.algorithm.aco.evaluator import RouteEvaluator
from src.generate_routes.data.map import Map


class StageConnector:
    """Handles multi-level shortest path routing between stage waypoints with fallback mechanisms."""

    def __init__(
        self,
        stage_graphs: list[Map],
        evaluator: RouteEvaluator,
    ) -> None:
        self.stage_graphs = stage_graphs
        self.evaluator = evaluator
        self.num_stages = len(stage_graphs)

    def _try_connect_stage(
        self,
        graph: Map,
        waypoints: list[int],
        allow_overlap: bool,
    ) -> tuple[list[int], float]:
        """Attempts to connect a list of waypoints using Dijkstra shortest path."""
        stage_path: list[int] = []
        stage_distance = 0.0
        visited_nodes: set[int] = set()

        for u, v in zip(waypoints[:-1], waypoints[1:], strict=False):
            if u == v:
                return [], 0.0

            try:
                segment = nx.shortest_path(graph, source=u, target=v, weight="length")
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                return [], 0.0

            if not allow_overlap:
                if any(node in visited_nodes for node in segment[1:]):
                    return [], 0.0

            for node in segment[1:]:
                visited_nodes.add(node)

            if not stage_path:
                visited_nodes.add(segment[0])
                stage_path.extend(segment)
            else:
                stage_path.extend(segment[1:])

            for src, dst in zip(segment[:-1], segment[1:], strict=False):
                _, edge_len = self.evaluator.edge_info_cache.get((src, dst), ([], 1.0))
                stage_distance += edge_len

        return stage_path, stage_distance

    def connect_stage(self, stage_idx: int, waypoints: list[int]) -> tuple[list[int], float]:
        """Connects stage waypoints using a 4-tier robust fallback mechanism."""
        graph = self.stage_graphs[stage_idx]

        # Level 1: Strict Dijkstra (no node repetition within stage)
        strict_path, strict_dist = self._try_connect_stage(graph, waypoints, allow_overlap=False)
        if strict_path:
            return strict_path, strict_dist

        # Level 2: Soft fallback (allow shared intersections/nodes)
        soft_path, soft_dist = self._try_connect_stage(graph, waypoints, allow_overlap=True)
        if soft_path:
            return soft_path, soft_dist

        # Level 3: Base chord fallback (drop intermediate detours, connect endpoints)
        base_waypoints = [waypoints[0], waypoints[-1]]
        fallback_path, fallback_dist = self._try_connect_stage(graph, base_waypoints, allow_overlap=True)
        if fallback_path:
            return fallback_path, fallback_dist

        # Level 4: Global emergency fallback (sparse network / rural fallback)
        try:
            full_graph = getattr(self.evaluator, "graph", self.stage_graphs[0])
            emergency_segment = nx.shortest_path(
                full_graph,
                source=waypoints[0],
                target=waypoints[-1],
                weight="length",
            )
            emergency_dist = sum(
                self.evaluator.edge_info_cache.get((u, v), ([], 1.0))[1]
                for u, v in zip(emergency_segment[:-1], emergency_segment[1:], strict=False)
            )
            return emergency_segment, emergency_dist
        except (nx.NetworkXNoPath, nx.NodeNotFound, Exception):
            return [], 0.0

    def evaluate_candidate_stages(
        self,
        stage_waypoint_lists: list[list[int]],
    ) -> tuple[list[int], float, float]:
        """Glues sequential stages into a single closed loop and computes global fitness."""
        full_path: list[int] = []
        total_distance = 0.0

        for stage_idx in range(self.num_stages):
            sub_wps = stage_waypoint_lists[stage_idx]
            sub_path, sub_dist = self.connect_stage(stage_idx, sub_wps)

            if not sub_path:
                return [], 0.0, -1.0

            if not full_path:
                full_path.extend(sub_path)
            else:
                full_path.extend(sub_path[1:])
            total_distance += sub_dist

        fitness = self.evaluator.evaluate(full_path, total_distance=total_distance)
        return full_path, total_distance, fitness
