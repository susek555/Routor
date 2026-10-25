from unittest.mock import MagicMock

import networkx as nx
import pytest
from src.generate_routes.algorithm.vns.detour_sampler import DetourSampler
from src.generate_routes.algorithm.vns.neighborhoods import NeighborhoodOperator
from src.generate_routes.algorithm.vns.vns_params import NeighborhoodParams


@pytest.fixture
def default_neighborhood_params():
    return NeighborhoodParams(
        max_k=4,
        max_detours_per_stage=3,
        checkpoint_shift_radius_meters=200.0,
        checkpoint_min_shift_distance_meters=30.0,
    )


@pytest.fixture
def mock_sampler():
    sampler = MagicMock(spec=DetourSampler)
    sampler.is_in_terminal_zone.return_value = False
    sampler.select_biased_candidate.return_value = 999
    # Coordinates ~50m apart
    sampler.get_coord.side_effect = lambda node, g: (52.000 + node * 0.0005, 21.0)
    return sampler


@pytest.fixture
def multi_stage_graphs():
    g1 = nx.MultiDiGraph()
    g1.add_nodes_from([0, 1, 10, 11])
    g2 = nx.MultiDiGraph()
    g2.add_nodes_from([1, 0, 20, 21])
    return [g1, g2]


class TestNeighborhoodOperator:
    def test_record_improvement_updates_stats(self, default_neighborhood_params, mock_sampler):
        """Tracks operator call count and success metrics accurately."""
        op = NeighborhoodOperator(
            params=default_neighborhood_params,
            sampler=mock_sampler,
            stage_graphs=[],
            checkpoints=[0, 1],
            target_distance=1000.0,
        )

        op.stats[1].calls = 10
        op.record_improvement(1)
        op.record_improvement(1)

        assert op.stats[1].improvements == 2
        assert op.stats[1].hit_rate == pytest.approx(20.0)

    def test_op_biased_detour_k1_inserts_new_waypoint(
        self, default_neighborhood_params, mock_sampler, multi_stage_graphs
    ):
        """Verifies k=1 inserts a candidate into waypoints when under distance budget."""
        op = NeighborhoodOperator(
            params=default_neighborhood_params,
            sampler=mock_sampler,
            stage_graphs=multi_stage_graphs,
            checkpoints=[0, 1],
            target_distance=1000.0,
        )

        wps = [[0, 1], [1, 0]]
        # Force stage_idx 0
        op._op_biased_detour(wps, stage_idx=0, needed_dist=500.0, allowed_cands=[10])

        assert len(wps[0]) == 3
        assert 999 in wps[0]

    def test_op_ruin_and_recreate_k3_cleans_and_reseeds(
        self, default_neighborhood_params, mock_sampler, multi_stage_graphs
    ):
        """Verifies k=3 collapses existing detours to base chord and introduces a fresh candidate."""
        op = NeighborhoodOperator(
            params=default_neighborhood_params,
            sampler=mock_sampler,
            stage_graphs=multi_stage_graphs,
            checkpoints=[0, 1],
            target_distance=1000.0,
        )

        # Stage 0 has multiple intermediate waypoints
        wps = [[0, 10, 11, 1], [1, 0]]
        op._op_ruin_and_recreate(wps, stage_idx=0, needed_dist=300.0, allowed_cands=[20])

        # Must collapse back to [start, candidate, dest]
        assert wps[0] == [0, 999, 1]

    def test_shake_dispatches_via_operator_table(self, default_neighborhood_params, mock_sampler, multi_stage_graphs):
        """Ensures shake invokes registered handler and increments operator call counter."""
        op = NeighborhoodOperator(
            params=default_neighborhood_params,
            sampler=mock_sampler,
            stage_graphs=multi_stage_graphs,
            checkpoints=[0, 1],
            target_distance=1000.0,
        )

        mock_handler = MagicMock()
        op._operators[2] = mock_handler

        current_wps = [[0, 1], [1, 0]]
        op.shake(current_wps, k=2, current_dist=500.0)

        assert op.stats[2].calls == 1
        mock_handler.assert_called_once()
