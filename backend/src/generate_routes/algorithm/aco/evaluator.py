import networkx as nx

from src.generate_routes.algorithm.aco.utils import get_min_edge_length, get_node_coords

type Map = nx.MultiDiGraph

# Angular thresholds for fast bounding-box filtering (~25m in Poland)
DEG_LAT_25M = 0.00023
DEG_LON_25M = 0.00036

# Minimum nodes required to form at least two edges (and thus a potential overlap)
MIN_PATH_NODES_FOR_OVERLAP = 3

# Penalty multiplier applied when an undirected edge is traversed again (out-and-back)
OUT_AND_BACK_PENALTY_MULTIPLIER = 2.0

# Minimum coordinate points required on an edge polyline to derive an intermediate midpoint
MIN_GEOMETRY_POINTS = 2

# Marginal bracket constants for progressive distance penalty
DISTANCE_TOLERANCE_THRESHOLD = 0.20  # 20% base tolerance zone
UNDER_THRESHOLD_WEIGHT = 0.10  # Penalty accumulates 10x slower below threshold
OVER_THRESHOLD_WEIGHT = 1.00  # Standard penalty rate above threshold


class RouteEvaluator:
    """Evaluates the global quality (fitness) of a candidate ant loop.
    Penalizes both topological repeats and parallel sidewalk corridors.
    """

    def __init__(
        self,
        stage_graphs: list[Map],
        target_distance: float,
        fitness_alpha: float = 2.0,
        fitness_beta: float = 50.0,
        corridor_threshold_meters: float = 25.0,
        distance_tolerance_ratio: float = DISTANCE_TOLERANCE_THRESHOLD,
    ):
        self.stage_graphs = stage_graphs
        self.target_distance = max(target_distance, 1.0)
        self.alpha = fitness_alpha
        self.beta = fitness_beta
        self.corridor_threshold = corridor_threshold_meters
        self.tolerance_ratio = distance_tolerance_ratio

        # Cache midpoints and lengths for all edges across graphs
        self.edge_info_cache: dict[tuple[int, int], tuple[tuple[float, float], float]] = {}
        self._build_edge_cache()

    def _build_edge_cache(self) -> None:
        """Precomputes midpoints and lengths for fast spatial overlap detection."""
        for graph in self.stage_graphs:
            for u, v in graph.edges():
                if (u, v) in self.edge_info_cache:
                    continue
                edge_len = get_min_edge_length(graph, u, v)

                # Try using midpoint of geometry_points if available
                mid_pt = None
                edge_data = graph.get_edge_data(u, v)
                for d in edge_data.values():
                    geom = d.get("geometry_points")
                    if geom and len(geom) >= MIN_GEOMETRY_POINTS:
                        p = geom[len(geom) // 2]
                        mid_pt = (p.latitude, p.longitude)
                        break

                if not mid_pt:
                    c_u = get_node_coords(graph, u)
                    c_v = get_node_coords(graph, v)
                    mid_pt = ((c_u[0] + c_v[0]) / 2.0, (c_u[1] + c_v[1]) / 2.0)

                self.edge_info_cache[(u, v)] = (mid_pt, edge_len)
                self.edge_info_cache[(v, u)] = (mid_pt, edge_len)

    def calculate_corridor_overlap_penalty(self, full_path: list[int]) -> float:
        if len(full_path) < MIN_PATH_NODES_FOR_OVERLAP:
            return 0.0

        penalty = 0.0
        # Set of unique undirected edges traversed along the route
        visited_undirected = set()

        for i in range(len(full_path) - 1):
            u, v = full_path[i], full_path[i + 1]
            if u == v:
                continue

            edge_key = frozenset((u, v))
            edge_len = self.edge_info_cache.get((u, v), ((0, 0), 1.0))[1]

            # 1. Absolute penalty for repeating the same edge in the opposite direction (out-and-back)
            if edge_key in visited_undirected:
                penalty += edge_len * OUT_AND_BACK_PENALTY_MULTIPLIER
            visited_undirected.add(edge_key)

        return penalty

    def _calculate_marginal_distance_penalty(self, raw_diff_ratio: float) -> float:
        """Calculates distance penalty using a bracketed system (similar to income tax brackets).

        Below threshold, penalty grows 10x slower. Above threshold, the surplus
        is taxed at full rate, maintaining mathematical continuity (no jump step).
        """
        if raw_diff_ratio <= self.tolerance_ratio:
            return raw_diff_ratio * UNDER_THRESHOLD_WEIGHT

        base_bracket_penalty = self.tolerance_ratio * UNDER_THRESHOLD_WEIGHT
        excess_diff = raw_diff_ratio - self.tolerance_ratio
        return base_bracket_penalty + (excess_diff * OVER_THRESHOLD_WEIGHT)

    def evaluate(
        self,
        full_path: list[int],
        traversed_edges: list[frozenset[int]] | None = None,
        total_distance: float = 0.0,
    ) -> float:
        """Calculates global fitness score."""
        if not full_path or full_path[0] != full_path[-1]:
            return 0.0

        raw_diff_ratio = abs(total_distance - self.target_distance) / self.target_distance
        effective_dist_penalty = self._calculate_marginal_distance_penalty(raw_diff_ratio)

        overlap_penalty = self.calculate_corridor_overlap_penalty(full_path)
        overlap_ratio = overlap_penalty / self.target_distance

        fitness = 1.0 / (1.0 + self.alpha * effective_dist_penalty + self.beta * overlap_ratio)
        return float(fitness)
