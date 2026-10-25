import math
import random

from src.generate_routes.algorithm.common_utils import get_node_coords, haversine
from src.generate_routes.algorithm.vns.vns_params import SamplerParams
from src.generate_routes.data.map import Map


class DetourSampler:
    """Manages geometric candidate scoring and biased random selection for detour exploration."""

    def __init__(
        self,
        params: SamplerParams,
        node_coord_cache: dict[int, tuple[float, float]],
    ) -> None:
        self.params = params
        self.node_coord_cache = node_coord_cache

    def get_coord(self, node: int, graph: Map) -> tuple[float, float]:
        """Retrieves latitude/longitude coordinates from cache or graph with lazy lookup."""
        if node not in self.node_coord_cache:
            self.node_coord_cache[node] = get_node_coords(graph, node)
        return self.node_coord_cache[node]

    def is_in_terminal_zone(self, node: int, start_node: int, dest_node: int, graph: Map) -> bool:
        """Determines if a node is protected within start or finish approach radii."""
        c_node = self.get_coord(node, graph)
        c_start = self.get_coord(start_node, graph)
        c_dest = self.get_coord(dest_node, graph)

        in_start_zone = haversine(c_node, c_start) <= self.params.approach_lock_radius_meters
        in_dest_zone = haversine(c_node, c_dest) <= self.params.approach_lock_radius_meters

        return in_start_zone or in_dest_zone

    def calculate_candidate_score(
        self,
        node: int,
        u: int,
        w: int,
        graph: Map,
        needed_distance: float,
    ) -> float:
        """Computes fitness attractiveness for inserting node between u and w."""
        c_node = self.get_coord(node, graph)
        c_u = self.get_coord(u, graph)
        c_w = self.get_coord(w, graph)

        dist_u_node = haversine(c_u, c_node)
        dist_node_w = haversine(c_node, c_w)
        direct_dist = max(haversine(c_u, c_w), self.params.direct_dist_epsilon)

        detour_cost = (dist_u_node + dist_node_w) - direct_dist

        s = (dist_u_node + dist_node_w + direct_dist) / 2.0
        area_sq = max(0.0, s * (s - dist_u_node) * (s - dist_node_w) * (s - direct_dist))
        lateral_height = (2.0 * math.sqrt(area_sq)) / direct_dist

        lateral_score = min(
            self.params.max_lateral_score,
            (lateral_height / self.params.lateral_scale_meters) * self.params.lateral_bonus_weight,
        )

        if needed_distance > 0:
            diff = abs(detour_cost - needed_distance)
            fit_score = 1.0 / (1.0 + (diff / self.params.deficit_diff_scale) * self.params.distance_fit_weight)
        else:
            fit_score = 1.0 / (1.0 + (detour_cost / self.params.surplus_diff_scale))

        return float(self.params.epsilon_weight + lateral_score + fit_score)

    def select_biased_candidate(
        self,
        allowed_candidates: list[int],
        u: int,
        w: int,
        graph: Map,
        needed_distance: float,
    ) -> int:
        """Selects a candidate node using roulette-wheel selection on biased heuristic weights."""
        if not allowed_candidates:
            return u

        sample_pool = (
            random.sample(allowed_candidates, min(len(allowed_candidates), self.params.max_sample_pool_size))
            if len(allowed_candidates) > self.params.max_sample_pool_size
            else allowed_candidates
        )

        weights = [self.calculate_candidate_score(n, u, w, graph, needed_distance) for n in sample_pool]
        return random.choices(sample_pool, weights=weights, k=1)[0]  # noqa: S311
