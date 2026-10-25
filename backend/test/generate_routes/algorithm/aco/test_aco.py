from unittest.mock import MagicMock, call, patch

import networkx as nx
import pytest
from src.generate_routes.algorithm.aco.aco import ACO
from src.generate_routes.algorithm.aco.aco_params import ACOParams
from src.generate_routes.algorithm.evaluator_params import EvaluationBreakdown

MODULE_PATH = ACO.__module__


@pytest.fixture
def mock_aco_params():
    """Provides baseline mock parameters for ACO configuration."""
    params = MagicMock(spec=ACOParams)
    params.target_distance = 2000.0
    params.initial_pheromone = 1.0
    params.num_iterations = 2
    params.num_ants = 2
    params.warm_start_seed_multiplier = 2.0
    params.pheromone_deposit_multiplier = 1.5
    params.evaporation_rate = 0.1
    params.inter_stage_slack_damping = 0.5
    params.max_inter_stage_slack_meters = 150.0

    # Sub-params forwarded to collaborators
    params.heuristics_params = MagicMock()
    params.evaluator_params = MagicMock()
    params.walker_params = MagicMock()
    return params


@pytest.fixture
def two_stage_graphs():
    """Builds two simple graphs forming a 2-stage closed loop: CP0 -> CP1 -> CP0.

    Stage 0 (CP0 -> CP1): 10 -> 20 (length 500m)
    Stage 1 (CP1 -> CP0): 20 -> 10 (length 500m)
    """
    g0 = nx.MultiDiGraph()
    g0.add_node(10, y=52.000, x=21.000)
    g0.add_node(20, y=52.005, x=21.000)
    g0.add_edge(10, 20, key=0, length=500.0)

    g1 = nx.MultiDiGraph()
    g1.add_node(20, y=52.005, x=21.000)
    g1.add_node(10, y=52.000, x=21.000)
    g1.add_edge(20, 10, key=0, length=500.0)

    return [g0, g1]


class TestACOExecutionFlow:
    @patch(f"{MODULE_PATH}.StageWalker")
    @patch(f"{MODULE_PATH}.RouteEvaluator")
    @patch(f"{MODULE_PATH}.BudgetManager")
    @patch(f"{MODULE_PATH}.EdgePheromoneRegistry")
    def test_init_instantiates_all_collaborators(
        self,
        mock_registry_cls,
        mock_budget_cls,
        mock_evaluator_cls,
        mock_walker_cls,
        mock_aco_params,
        two_stage_graphs,
    ):
        """Verifies that constructor instantiates all dependent managers with proper configurations."""
        checkpoints = [10, 20]
        aco = ACO(
            params=mock_aco_params,
            checkpoints=checkpoints,
            stage_graphs=two_stage_graphs,
        )

        mock_registry_cls.assert_called_once_with(
            stage_graphs=two_stage_graphs,
            initial_pheromone=mock_aco_params.initial_pheromone,
        )
        mock_budget_cls.assert_called_once_with(
            stage_graphs=two_stage_graphs,
            checkpoints=checkpoints,
            target_distance=mock_aco_params.target_distance,
            params=mock_aco_params.heuristics_params,
        )
        mock_evaluator_cls.assert_called_once_with(
            stage_graphs=two_stage_graphs,
            target_distance=mock_aco_params.target_distance,
            params=mock_aco_params.evaluator_params,
        )
        mock_walker_cls.assert_called_once_with(
            pheromone_registry=aco.registry,
            budget_manager=aco.budget_manager,
            params=mock_aco_params.walker_params,
        )

    @patch(f"{MODULE_PATH}.StageWalker")
    @patch(f"{MODULE_PATH}.RouteEvaluator")
    @patch(f"{MODULE_PATH}.BudgetManager")
    @patch(f"{MODULE_PATH}.EdgePheromoneRegistry")
    def test_simulate_single_ant_execution_flow(
        self,
        mock_registry_cls,
        mock_budget_cls,
        mock_evaluator_cls,
        mock_walker_cls,
        mock_aco_params,
        two_stage_graphs,
    ):
        """Validates traversal progression across stages, slack propagation, and fitness evaluation."""
        checkpoints = [10, 20]
        aco = ACO(mock_aco_params, checkpoints, two_stage_graphs)

        # Stage 0: budget 1000m, walks 900m -> slack = (1000 - 900) * 0.5 = 50m
        # Stage 1: budget 1050m, walks 1050m -> slack = 0m
        aco.budget_manager.get_effective_stage_budget.side_effect = [1000.0, 1050.0]
        aco.walker.walk_stage.side_effect = [
            ([10, 20], [frozenset((10, 20))], 900.0),
            ([20, 10], [frozenset((20, 10))], 1050.0),
        ]
        aco.evaluator.evaluate.return_value = 0.88

        full_path, all_edges, total_dist, fitness = aco._simulate_single_ant()

        assert aco.budget_manager.get_effective_stage_budget.call_args_list == [
            call(stage_idx=0, accumulated_slack=0.0),
            call(stage_idx=1, accumulated_slack=50.0),
        ]
        assert aco.walker.walk_stage.call_count == 2
        aco.evaluator.evaluate.assert_called_once_with([10, 20, 10], 1950.0)

        assert full_path == [10, 20, 10]
        assert all_edges == [frozenset((10, 20)), frozenset((20, 10))]
        assert total_dist == pytest.approx(1950.0)
        assert fitness == 0.88

    @patch(f"{MODULE_PATH}.StageWalker")
    @patch(f"{MODULE_PATH}.RouteEvaluator")
    @patch(f"{MODULE_PATH}.BudgetManager")
    @patch(f"{MODULE_PATH}.EdgePheromoneRegistry")
    def test_generate_route_orchestration_flow(
        self,
        mock_registry_cls,
        mock_budget_cls,
        mock_evaluator_cls,
        mock_walker_cls,
        mock_aco_params,
        two_stage_graphs,
    ):
        """Verifies full loop orchestration: warm start, iterations, deposit collection, and evaporation."""
        mock_aco_params.num_iterations = 1
        mock_aco_params.num_ants = 2
        checkpoints = [10, 20]
        aco = ACO(mock_aco_params, checkpoints, two_stage_graphs)

        # Baseline skeleton setup
        skeleton_path = [10, 20, 10]
        skeleton_dist = 1000.0
        with (
            patch.object(aco, "_build_dijkstra_skeleton", return_value=(skeleton_path, skeleton_dist)),
            patch.object(aco, "_simulate_single_ant") as mock_simulate,
        ):
            # Skeleton fitness = 0.5; Ant 1 beats it (0.9), Ant 2 fails/worse (0.2)
            aco.evaluator.evaluate.side_effect = [
                0.5,  # Skeleton evaluation
            ]
            mock_simulate.side_effect = [
                ([10, 20, 10], [frozenset((10, 20))], 1000.0, 0.9),
                ([10, 20, 10], [frozenset((10, 20))], 1000.0, 0.2),
            ]

            empty_buffer = {0: 0.0}
            aco.registry.create_empty_deposit_buffer.return_value = empty_buffer
            aco.registry.get_edge_id.return_value = 0

            mock_breakdown = MagicMock(spec=EvaluationBreakdown)
            aco.evaluator.evaluate_with_breakdown.return_value = mock_breakdown

            best_path, best_fitness = aco.generate_route()

            # 1. Warm start seed check
            aco.registry.seed_path_pheromones.assert_called_once_with(
                skeleton_path,
                boost_factor=mock_aco_params.warm_start_seed_multiplier,
            )

            # 2. Ant simulation calls
            assert mock_simulate.call_count == 2

            # 3. Evaporation and deposit calls
            aco.registry.evaporate.assert_called_once_with(mock_aco_params.evaporation_rate)
            aco.registry.apply_deposits.assert_called_once_with(empty_buffer)

            # 4. Result breakdown logging and outputs
            mock_breakdown.log_summary.assert_called_once_with("Best Found Ant Loop")
            assert best_path == [10, 20, 10]
            assert best_fitness == 0.9


class TestACOUnitAndIntegration:
    @patch(f"{MODULE_PATH}.StageWalker")
    @patch(f"{MODULE_PATH}.RouteEvaluator")
    @patch(f"{MODULE_PATH}.BudgetManager")
    @patch(f"{MODULE_PATH}.EdgePheromoneRegistry")
    def test_build_dijkstra_skeleton_builds_closed_loop(
        self,
        mock_registry_cls,
        mock_budget_cls,
        mock_evaluator_cls,
        mock_walker_cls,
        mock_aco_params,
        two_stage_graphs,
    ):
        """Integrates real NetworkX shortest path traversal to construct baseline skeleton loop."""
        checkpoints = [10, 20]
        aco = ACO(mock_aco_params, checkpoints, two_stage_graphs)

        skeleton_path, skeleton_dist = aco._build_dijkstra_skeleton()

        assert skeleton_path == [10, 20, 10]
        assert skeleton_dist == pytest.approx(1000.0)

    @patch(f"{MODULE_PATH}.StageWalker")
    @patch(f"{MODULE_PATH}.RouteEvaluator")
    @patch(f"{MODULE_PATH}.BudgetManager")
    @patch(f"{MODULE_PATH}.EdgePheromoneRegistry")
    def test_build_dijkstra_skeleton_handles_missing_path(
        self,
        mock_registry_cls,
        mock_budget_cls,
        mock_evaluator_cls,
        mock_walker_cls,
        mock_aco_params,
        two_stage_graphs,
    ):
        """Safely skips disconnected stages without throwing NetworkXNoPath exceptions."""
        # Sever the connection in stage 1 by removing the edge
        two_stage_graphs[1].remove_edge(20, 10, key=0)

        checkpoints = [10, 20]
        aco = ACO(mock_aco_params, checkpoints, two_stage_graphs)

        skeleton_path, skeleton_dist = aco._build_dijkstra_skeleton()

        # Only stage 0 (10 -> 20) succeeds; stage 1 is skipped
        assert skeleton_path == [10, 20]
        assert skeleton_dist == pytest.approx(500.0)

    @patch(f"{MODULE_PATH}.StageWalker")
    @patch(f"{MODULE_PATH}.RouteEvaluator")
    @patch(f"{MODULE_PATH}.BudgetManager")
    @patch(f"{MODULE_PATH}.EdgePheromoneRegistry")
    def test_extract_stage_coords_retrieves_lat_lon(
        self,
        mock_registry_cls,
        mock_budget_cls,
        mock_evaluator_cls,
        mock_walker_cls,
        mock_aco_params,
        two_stage_graphs,
    ):
        """Extracts latitude and longitude tuples for given stage nodes from graph attributes."""
        checkpoints = [10, 20]
        aco = ACO(mock_aco_params, checkpoints, two_stage_graphs)

        coords = aco._extract_stage_coords(stage_idx=0, stage_path=[10, 20])

        assert len(coords) == 2
        assert coords[0] == (52.000, 21.000)
        assert coords[1] == (52.005, 21.000)
