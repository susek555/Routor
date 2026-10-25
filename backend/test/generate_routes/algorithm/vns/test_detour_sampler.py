from dataclasses import replace
from unittest.mock import patch

import networkx as nx
import pytest
from src.generate_routes.algorithm.vns.detour_sampler import DetourSampler
from src.generate_routes.algorithm.vns.vns_params import SamplerParams


@pytest.fixture
def default_sampler_params():
    return SamplerParams(
        approach_lock_radius_meters=100.0,
        lateral_bonus_weight=2.0,
        lateral_scale_meters=500.0,
        distance_fit_weight=2.0,
        epsilon_weight=0.05,
        max_sample_pool_size=10,
    )


@pytest.fixture
def coordinate_graph():
    """Graph configured with explicit geographic positions."""
    g = nx.MultiDiGraph()
    # (lat, lon)
    g.add_node(0, y=52.0000, x=21.0000)  # Start
    g.add_node(1, y=52.0005, x=21.0000)  # ~55m North (inside terminal zone of 0)
    g.add_node(2, y=52.0100, x=21.0000)  # ~1110m North (outside terminal zone)
    g.add_node(3, y=52.0200, x=21.0000)  # Finish
    return g


class TestDetourSampler:
    def test_is_in_terminal_zone_detects_proximity(self, default_sampler_params, coordinate_graph):
        """Identifies nodes situated within start or destination approach exclusion radii."""
        cache = {
            0: (52.0000, 21.0000),
            1: (52.0005, 21.0000),
            2: (52.0100, 21.0000),
            3: (52.0200, 21.0000),
        }
        sampler = DetourSampler(params=default_sampler_params, node_coord_cache=cache)

        # Node 1 is ~55m from Node 0 (threshold 100m) -> True
        assert sampler.is_in_terminal_zone(node=1, start_node=0, dest_node=3, graph=coordinate_graph) is True

        # Node 2 is ~1110m from Node 0 and ~1110m from Node 3 -> False
        assert sampler.is_in_terminal_zone(node=2, start_node=0, dest_node=3, graph=coordinate_graph) is False

    def test_calculate_candidate_score_rewards_needed_distance(self, default_sampler_params):
        """Favors nodes whose detour elongation aligns with the required distance budget."""
        # Isolate distance fit by removing lateral bias for this unit assertion

        params_no_lateral = replace(default_sampler_params, lateral_bonus_weight=0.0)

        cache = {
            10: (52.000, 21.000),  # u
            20: (52.000, 21.020),  # w
            1: (52.002, 21.010),  # moderate detour (~70m detour cost)
            2: (52.008, 21.010),  # large detour (~600m detour cost)
        }
        sampler = DetourSampler(params=params_no_lateral, node_coord_cache=cache)
        graph = nx.MultiDiGraph()

        # cand1 is almost a perfect match (|70 - 70| ≈ 0), cand2 is far off
        score_cand1 = sampler.calculate_candidate_score(1, 10, 20, graph, needed_distance=70.0)
        score_cand2 = sampler.calculate_candidate_score(2, 10, 20, graph, needed_distance=70.0)

        assert score_cand1 > score_cand2

    def test_select_biased_candidate_empty_pool_fallback(self, default_sampler_params):
        """Safely returns base node 'u' if candidate pool is completely empty."""
        sampler = DetourSampler(params=default_sampler_params, node_coord_cache={})
        graph = nx.MultiDiGraph()

        chosen = sampler.select_biased_candidate(
            allowed_candidates=[],
            u=42,
            w=99,
            graph=graph,
            needed_distance=100.0,
        )
        assert chosen == 42

    @patch("random.choices")
    def test_select_biased_candidate_calls_roulette_selection(self, mock_choices, default_sampler_params):
        """Validates that candidate selection calls random.choices using computed scores."""
        cache = {1: (52.0, 21.0), 2: (52.0, 21.1), 3: (52.01, 21.05)}
        sampler = DetourSampler(params=default_sampler_params, node_coord_cache=cache)
        graph = nx.MultiDiGraph()

        mock_choices.return_value = [3]

        chosen = sampler.select_biased_candidate(
            allowed_candidates=[3],
            u=1,
            w=2,
            graph=graph,
            needed_distance=200.0,
        )

        assert chosen == 3
        mock_choices.assert_called_once()
