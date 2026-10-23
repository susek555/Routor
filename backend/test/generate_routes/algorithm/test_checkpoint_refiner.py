from unittest.mock import MagicMock, patch

import networkx as nx
import pytest
from src.generate_routes.algorithm.checkpoint_refiner import (
    EXPECTED_CHECKPOINT_COUNT,
    CheckpointRefiner,
)

MODULE_PATH = CheckpointRefiner.__module__


@pytest.fixture
def empty_graph():
    return nx.MultiDiGraph()


@pytest.fixture
def loop_subgraphs_with_spur():
    """Builds 4 stage subgraphs forming a closed loop (CP0 -> CP1 -> CP2 -> CP3 -> CP0).

    Stage 0 (CP0 -> CP1):
      0 -> 10 -> 1 (length 100 + 30 = 130m)
    Stage 1 (CP1 -> CP2):
      1 -> 10 -> 2 (reverses back through 10: 1->10: 30m, 10->2: 100m)
      => Spur at node 1 going back to node 10. Spur length = 30m (round-trip = 60m).
    Stage 2 (CP2 -> CP3) & Stage 3 (CP3 -> CP0):
      Smooth transit without spurs.
    """
    g0 = nx.MultiDiGraph()
    g0.add_edge(0, 10, key=0, length=100.0)
    g0.add_edge(10, 1, key=0, length=30.0)

    g1 = nx.MultiDiGraph()
    g1.add_edge(1, 10, key=0, length=30.0)
    g1.add_edge(10, 2, key=0, length=100.0)

    g2 = nx.MultiDiGraph()
    g2.add_edge(2, 3, key=0, length=100.0)

    g3 = nx.MultiDiGraph()
    g3.add_edge(3, 0, key=0, length=100.0)

    return [g0, g1, g2, g3]


class TestCheckpointRefinerExecutionFlow:
    @patch.object(CheckpointRefiner, "_evaluate_checkpoint_spur")
    def test_refine_stage_checkpoints_execution_flow(self, mock_evaluate):
        """Verifies evaluation calls for all intermediate checkpoints (CP1, CP2, CP3)."""
        mock_subgraphs = [MagicMock() for _ in range(EXPECTED_CHECKPOINT_COUNT)]
        checkpoint_ids = [100, 200, 300, 400]

        # CP1 collapsed to fork 250, others have no spur
        mock_evaluate.side_effect = [250, None, None]

        target_dist = 2000.0
        retraction_ratio = 0.15
        expected_budget = target_dist * retraction_ratio

        refined_ids, subgraphs = CheckpointRefiner.refine_stage_checkpoints(
            mock_subgraphs,
            checkpoint_ids,
            target_distance_meters=target_dist,
            max_retraction_ratio=retraction_ratio,
        )

        assert mock_evaluate.call_count == 3
        # Check first call parameters: (graph_in, graph_out, nodes_triplet, max_retraction, checkpoint_idx)
        mock_evaluate.assert_any_call(
            graph_in=mock_subgraphs[0],
            graph_out=mock_subgraphs[1],
            nodes=(100, 200, 300),
            max_retraction_meters=expected_budget,
            checkpoint_idx=1,
        )

        assert refined_ids == [100, 250, 300, 400]
        assert subgraphs == mock_subgraphs

    def test_refine_stage_checkpoints_early_exit_on_invalid_count(self):
        """Early returns untouched input when checkpoint or graph count does not match expected size."""
        graphs = [nx.MultiDiGraph()]
        checkpoints = [1, 2]

        refined_ids, result_graphs = CheckpointRefiner.refine_stage_checkpoints(
            graphs, checkpoints, target_distance_meters=1000.0
        )

        assert refined_ids == checkpoints
        assert result_graphs == graphs


class TestCheckpointRefinerUnitAndIntegration:
    def test_get_edge_length_various_structures(self, empty_graph):
        """Tests robust extraction of edge length across different graph configurations."""
        # Simple directional edge
        empty_graph.add_edge(1, 2, key=0, length=45.5)
        assert CheckpointRefiner._get_edge_length(empty_graph, 1, 2) == 45.5
        # Reverse lookup fallback
        assert CheckpointRefiner._get_edge_length(empty_graph, 2, 1) == 45.5

        # Multi-edge picks the minimum length
        empty_graph.add_edge(2, 3, key=0, length=80.0)
        empty_graph.add_edge(2, 3, key=1, length=35.0)
        assert CheckpointRefiner._get_edge_length(empty_graph, 2, 3) == 35.0

        # Non-existent edge returns 0.0
        assert CheckpointRefiner._get_edge_length(empty_graph, 99, 100) == 0.0

    def test_evaluate_checkpoint_spur_missing_node_or_path(self, empty_graph):
        """Returns None safely when nodes or valid paths are missing."""
        g_in = nx.MultiDiGraph()
        g_out = nx.MultiDiGraph()
        g_in.add_node(1)  # Missing curr_node 2 in both graphs

        fork = CheckpointRefiner._evaluate_checkpoint_spur(
            graph_in=g_in,
            graph_out=g_out,
            nodes=(1, 2, 3),
            max_retraction_meters=100.0,
            checkpoint_idx=1,
        )
        assert fork is None

        # Nodes exist, but no topological path exists
        g_in.add_node(2)
        g_out.add_node(2)
        g_out.add_node(3)
        fork_no_path = CheckpointRefiner._evaluate_checkpoint_spur(
            graph_in=g_in,
            graph_out=g_out,
            nodes=(1, 2, 3),
            max_retraction_meters=100.0,
            checkpoint_idx=1,
        )
        assert fork_no_path is None

    def test_evaluate_checkpoint_spur_exceeds_budget(self, loop_subgraphs_with_spur):
        """Preserves out-and-back route when round-trip spur cost exceeds allowed limit."""
        # Spur length = 30m, round-trip cost = 60m. Set limit to 50m.
        fork = CheckpointRefiner._evaluate_checkpoint_spur(
            graph_in=loop_subgraphs_with_spur[0],
            graph_out=loop_subgraphs_with_spur[1],
            nodes=(0, 1, 2),
            max_retraction_meters=50.0,
            checkpoint_idx=1,
        )
        assert fork is None

    def test_refine_stage_checkpoints_collapses_spur_into_fork(self, loop_subgraphs_with_spur):
        """Successfully detects and collapses intermediate spur when within retraction budget."""
        checkpoint_ids = [0, 1, 2, 3]
        target_dist = 1000.0
        max_ratio = 0.15  # Budget: 150m (spur round-trip: 60m <= 150m)

        refined_ids, refined_subgraphs = CheckpointRefiner.refine_stage_checkpoints(
            stage_subgraphs=loop_subgraphs_with_spur,
            checkpoint_node_ids=checkpoint_ids,
            target_distance_meters=target_dist,
            max_retraction_ratio=max_ratio,
        )

        # CP1 (node 1) should be collapsed back to fork candidate (node 10)
        assert refined_ids == [0, 10, 2, 3]
        assert refined_subgraphs[0].has_node(10)
        assert refined_subgraphs[1].has_node(10)
