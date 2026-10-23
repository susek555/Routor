from unittest.mock import MagicMock, patch

import networkx as nx
import pytest
from src.generate_routes.algorithm.aco.edge_pheromone_registry import EdgePheromoneRegistry
from src.generate_routes.algorithm.aco.heuristics import BudgetManager
from src.generate_routes.algorithm.aco.stage_walker import AntState, StageWalker
from src.generate_routes.algorithm.aco.utils.stage_walker import WalkerParams

MODULE_PATH = StageWalker.__module__


@pytest.fixture
def walker_params():
    """Provides baseline configuration parameters for StageWalker."""
    params = MagicMock(spec=WalkerParams)
    params.alpha = 1.0
    params.beta = 2.0
    params.min_probability_epsilon = 1e-6
    params.min_history_for_proximity = 2
    params.history_recency_exclusion_offset = 1
    params.hard_proximity_dist_meters = 15.0
    params.soft_proximity_dist_meters = 35.0
    params.soft_corridor_eta_penalty = 0.5
    params.approach_zone_radius_meters = 100.0
    params.step_limit_node_multiplier = 4
    params.min_step_limit_floor = 20

    bounding_box = MagicMock()
    bounding_box.DEG_LAT = 0.001
    bounding_box.DEG_LON = 0.001
    params.bounding_box = bounding_box
    return params


@pytest.fixture
def mock_dependencies():
    """Creates mock EdgePheromoneRegistry and BudgetManager instances."""
    registry = MagicMock(spec=EdgePheromoneRegistry)
    registry.get_pheromone.return_value = 1.0

    budget_mgr = MagicMock(spec=BudgetManager)
    budget_mgr.calculate_r.return_value = 1.0
    budget_mgr.calculate_eta.return_value = 1.0

    return registry, budget_mgr


@pytest.fixture
def linear_stage_graph():
    """Builds a simple directional corridor graph: 0 -> 1 -> 2."""
    g = nx.MultiDiGraph()
    g.add_node(0, y=52.000, x=21.000)
    g.add_node(1, y=52.001, x=21.000)
    g.add_node(2, y=52.002, x=21.000)

    g.add_edge(0, 1, key=0, length=110.0)
    g.add_edge(1, 2, key=0, length=110.0)
    return g


class TestStageWalkerExecutionFlow:
    @patch.object(StageWalker, "_advance_ant")
    @patch.object(StageWalker, "_select_next_node")
    @patch.object(StageWalker, "_filter_valid_moves")
    def test_walk_stage_standard_execution_flow(
        self,
        mock_filter_moves,
        mock_select_node,
        mock_advance,
        mock_dependencies,
        walker_params,
        linear_stage_graph,
    ):
        """Verifies step-by-step traversal flow: calculate_r -> filter -> select -> advance."""
        registry, budget_mgr = mock_dependencies
        budget_mgr.stage_graphs = [linear_stage_graph]

        walker = StageWalker(registry, budget_mgr, walker_params)
        # Target node is 1, so the loop terminates immediately after a single step
        state = AntState(current=0, dest=1, path=[0])

        mock_filter_moves.return_value = [1]
        mock_select_node.return_value = 1

        def advance_side_effect(graph, next_node, st):
            st.current = next_node
            st.path.append(next_node)

        mock_advance.side_effect = advance_side_effect

        path, edges, dist = walker.walk_stage(stage_idx=0, effective_budget=300.0, state=state)

        budget_mgr.calculate_r.assert_called_once_with(
            stage_idx=0,
            current_node=0,
            effective_budget=300.0,
            dist_done_in_stage=0.0,
        )
        mock_filter_moves.assert_called_once_with(linear_stage_graph, state)
        mock_select_node.assert_called_once_with(0, linear_stage_graph, [1], state, 1.0)
        mock_advance.assert_called_once_with(linear_stage_graph, 1, state)
        assert path == [0, 1]
        assert state.current == 1

    @patch.object(StageWalker, "_emergency_dijkstra")
    def test_dead_end_rollback_triggers_emergency_dijkstra_when_stack_exhausted(
        self,
        mock_emergency,
        mock_dependencies,
        walker_params,
        linear_stage_graph,
    ):
        """Verifies fallback to emergency Dijkstra when backtracking reaches the start node."""
        registry, budget_mgr = mock_dependencies
        walker = StageWalker(registry, budget_mgr, walker_params)

        state = AntState(current=0, dest=2, path=[0])
        mock_emergency.return_value = [1, 2]

        is_exhausted = walker._handle_dead_end_rollback(linear_stage_graph, state)

        assert is_exhausted is True
        mock_emergency.assert_called_once_with(linear_stage_graph, 0, 2)
        assert state.current == 2
        assert state.path == [0, 1, 2]
        assert state.dead_end_nodes == {0}
        assert len(state.stage_edges) == 2
        assert state.distance == pytest.approx(220.0)


class TestStageWalkerUnitAndIntegration:
    def test_advance_ant_updates_all_state_structures(
        self,
        mock_dependencies,
        walker_params,
        linear_stage_graph,
    ):
        """Ensures advancing updates current node, history stacks, distance, and caches."""
        registry, budget_mgr = mock_dependencies
        walker = StageWalker(registry, budget_mgr, walker_params)

        state = AntState(current=0, dest=2, path=[0], past_coords=[(52.000, 21.000)])
        walker._advance_ant(linear_stage_graph, next_node=1, state=state)

        assert state.current == 1
        assert state.path == [0, 1]
        assert state.stage_edges == [frozenset((0, 1))]
        assert state.edge_lengths == [110.0]
        assert state.distance == 110.0
        assert frozenset((0, 1)) in state.visited_edges
        assert state.past_coords == [(52.000, 21.000), (52.001, 21.000)]

    def test_dead_end_rollback_backtracks_one_step(
        self,
        mock_dependencies,
        walker_params,
        linear_stage_graph,
    ):
        """Pops the last step and restores accumulated distance when history has length > 1."""
        registry, budget_mgr = mock_dependencies
        walker = StageWalker(registry, budget_mgr, walker_params)

        state = AntState(
            current=1,
            dest=2,
            path=[0, 1],
            stage_edges=[frozenset((0, 1))],
            edge_lengths=[110.0],
            distance=110.0,
            past_coords=[(52.000, 21.000), (52.001, 21.000)],
        )

        is_exhausted = walker._handle_dead_end_rollback(linear_stage_graph, state)

        assert is_exhausted is False
        assert state.current == 0
        assert state.path == [0]
        assert state.stage_edges == []
        assert state.edge_lengths == []
        assert state.distance == 0.0
        assert state.past_coords == [(52.000, 21.000)]
        assert 1 in state.dead_end_nodes

    def test_is_legal_move_filters_u_turns_and_visited_edges(
        self,
        mock_dependencies,
        walker_params,
        linear_stage_graph,
    ):
        """Validates that self-loops, immediate U-turns, visited edges, and dead ends are rejected."""
        registry, budget_mgr = mock_dependencies
        walker = StageWalker(registry, budget_mgr, walker_params)

        state = AntState(
            current=1,
            dest=2,
            path=[0, 1],
            visited_edges={frozenset((0, 1))},
            dead_end_nodes={3},
        )

        coord_dummy = (52.002, 21.000)

        # 1. Self move
        assert walker._is_legal_move(1, state, coord_dummy) is False
        # 2. Dead end node
        assert walker._is_legal_move(3, state, coord_dummy) is False
        # 3. U-turn to previous node
        assert walker._is_legal_move(0, state, coord_dummy) is False
        # 4. Fresh unvisited valid move
        assert walker._is_legal_move(2, state, coord_dummy) is True

    def test_filter_valid_moves_filters_for_progress_in_approach_zone(
        self,
        mock_dependencies,
        walker_params,
        linear_stage_graph,
    ):
        """Enforces strictly distance-reducing moves when within destination approach zone."""
        registry, budget_mgr = mock_dependencies
        walker_params.approach_zone_radius_meters = 500.0  # Put current node within approach zone

        # Add a detour node that moves away from destination (node 2)
        linear_stage_graph.add_node(3, y=52.0005, x=21.005)
        linear_stage_graph.add_edge(1, 3, key=0, length=100.0)

        walker = StageWalker(registry, budget_mgr, walker_params)
        state = AntState(current=1, dest=2, path=[0, 1])

        valid_moves = walker._filter_valid_moves(linear_stage_graph, state)

        # Node 2 brings ant closer to destination; detour Node 3 is filtered out
        assert valid_moves == [2]

    def test_select_next_node_applies_soft_corridor_penalty(
        self,
        mock_dependencies,
        walker_params,
        linear_stage_graph,
    ):
        """Verifies soft corridor overlap penalty reduces selection probability."""
        registry, budget_mgr = mock_dependencies
        budget_mgr.calculate_eta.return_value = 10.0
        walker = StageWalker(registry, budget_mgr, walker_params)

        state = AntState(current=0, dest=2, path=[0])

        with (
            patch.object(walker, "_check_corridor_overlap", return_value=True),
            patch("numpy.random.choice", return_value=0) as mock_choice,
        ):
            selected = walker._select_next_node(
                stage_idx=0,
                graph=linear_stage_graph,
                valid_moves=[1],
                state=state,
                budget_ratio_r=1.0,
            )

            assert selected == 1
            mock_choice.assert_called_once()
            # Probability array passed to choice should be normalized to [1.0]
            passed_p = mock_choice.call_args[1]["p"]
            assert passed_p == [1.0]

    def test_walk_stage_completes_full_traversal(
        self,
        mock_dependencies,
        walker_params,
        linear_stage_graph,
    ):
        """End-to-end integration test: ant traverses from start to dest across the graph."""
        registry, budget_mgr = mock_dependencies
        budget_mgr.stage_graphs = [linear_stage_graph]

        walker = StageWalker(registry, budget_mgr, walker_params)
        state = AntState(current=0, dest=2, path=[0])

        final_path, stage_edges, total_dist = walker.walk_stage(
            stage_idx=0,
            effective_budget=300.0,
            state=state,
        )

        assert final_path == [0, 1, 2]
        assert stage_edges == [frozenset((0, 1)), frozenset((1, 2))]
        assert total_dist == pytest.approx(220.0)
        assert state.current == 2
