import json
from unittest.mock import MagicMock, patch

import pytest

# Adapt import path to the module location containing generate_route_task
import src.generate_routes.task as route_tasks
from src.api.data.task_state import (
    TaskState,
    TaskStateEnum,
)
from src.api.exceptions.exceptions import GraphGenerationError
from src.generate_routes.data.geo_point import GeoPoint
from src.generate_routes.task import generate_route_task, update_task_state

MODULE_PATH = route_tasks.__name__


@pytest.fixture
def sample_payload_dict():
    return {
        "user_id": "b1a7d6e4-9876-4f32-bb99-31741f2389a1",
        "center": {"latitude": 52.2297, "longitude": 21.0122},
        "target_distance": 10000.0,
        "fcm_token": "sample_fcm_token_123",
    }


@pytest.fixture
def mock_redis_client():
    client = MagicMock()
    client.set = MagicMock()
    client.publish = MagicMock()
    return client


class TestUpdateTaskState:
    def test_update_task_state_sets_cache_with_ttl_and_publishes(self, mock_redis_client):
        """Verifies that Redis key is saved with 1800s TTL and published to the matching channel."""
        task_id = "test-task-123"
        payload = TaskState(state=TaskStateEnum.LOADING_GRAPH)

        with (
            patch(f"{MODULE_PATH}.ws_state_key_prefix", "routes:state"),
            patch(f"{MODULE_PATH}.ws_channel_prefix", "routes"),
        ):
            update_task_state(task_id, payload, mock_redis_client)

        expected_data = payload.model_dump_json()
        expected_state_key = "routes:state:test-task-123"
        expected_channel = "routes:test-task-123"

        mock_redis_client.set.assert_called_once_with(expected_state_key, expected_data, ex=1800)
        mock_redis_client.publish.assert_called_once_with(expected_channel, expected_data)


class TestGenerateRouteTaskExecutionFlow:
    @patch(f"{MODULE_PATH}.save_route_variants_sync")
    @patch(f"{MODULE_PATH}.VNSLoopGenerator")
    @patch(f"{MODULE_PATH}.RouteEvaluator")
    @patch(f"{MODULE_PATH}.CheckpointRefiner.refine_stage_checkpoints")
    @patch(f"{MODULE_PATH}.Subgrapher.extract_subgraphs")
    @patch(f"{MODULE_PATH}.CheckpointsGenerator.generate_checkpoints")
    @patch(f"{MODULE_PATH}.Snapper")
    @patch(f"{MODULE_PATH}.GraphConverter")
    @patch(f"{MODULE_PATH}.GraphBuilder.build_graph")
    @patch(f"{MODULE_PATH}.redis.Redis.from_url")
    def test_generate_route_task_success_flow(
        self,
        mock_redis_from_url,
        mock_build_graph,
        mock_graph_converter_cls,
        mock_snapper_cls,
        mock_generate_checkpoints,
        mock_extract_subgraphs,
        mock_refine_checkpoints,
        mock_route_evaluator_cls,
        mock_vns_generator_cls,
        mock_save_variants,
        sample_payload_dict,
        mock_redis_client,
    ):
        """Verifies full execution pipeline: state transitions, DB save, and 5 route variants generation."""
        task_id = "task-uuid-abc"
        mock_redis_from_url.return_value = mock_redis_client

        # 1. GraphBuilder mock
        mock_raw_graph = MagicMock()
        mock_raw_graph.nodes = [1, 2, 3]
        mock_raw_graph.edges = [(1, 2), (2, 3)]
        mock_build_graph.return_value = mock_raw_graph

        # 2. Converter & Snapper mocks
        mock_converter = MagicMock()
        mock_graph_converter_cls.return_value = mock_converter
        mock_simple_graph = MagicMock()
        mock_converter.convert_graph_to_algorithm.return_value = mock_simple_graph

        mock_snapper = MagicMock()
        mock_snapper_cls.return_value = mock_snapper
        snapped_center_pt = GeoPoint(latitude=52.2298, longitude=21.0123)
        mock_snapper.snap_point.return_value = (100, snapped_center_pt)

        # 3. Algorithm components mock
        mock_generate_checkpoints.return_value = [GeoPoint(latitude=52.23, longitude=21.02)]
        mock_snapper.snap_points.return_value = [(200, GeoPoint(latitude=52.23, longitude=21.02))]
        mock_extract_subgraphs.return_value = [MagicMock()]
        mock_refine_checkpoints.return_value = ([100, 200], [MagicMock()])

        mock_vns_instance = MagicMock()
        mock_vns_generator_cls.return_value = mock_vns_instance
        mock_vns_instance.generate_route.return_value = ([100, 200, 100], 0.95)

        reconstructed_pts = [
            GeoPoint(latitude=52.2298, longitude=21.0123),
            GeoPoint(latitude=52.23, longitude=21.02),
        ]
        mock_converter.reconstruct_route_from_node_ids.return_value = (reconstructed_pts, 10042.4)

        # Execute Celery task directly with mocked self
        mock_self = MagicMock()
        mock_self.request.id = task_id

        generate_route_task.run.__func__(mock_self, sample_payload_dict)

        # Assert GraphBuilder was called with radius = target_distance * 0.5
        mock_build_graph.assert_called_once_with(
            GeoPoint(**sample_payload_dict["center"]),
            sample_payload_dict["target_distance"] * 0.5,
        )

        # Assert 5 iterations were computed
        assert mock_vns_instance.generate_route.call_count == 5
        assert mock_converter.reconstruct_route_from_node_ids.call_count == 5

        # Assert DB save was triggered with 5 variants
        mock_save_variants.assert_called_once()
        save_kwargs = mock_save_variants.call_args.kwargs
        assert save_kwargs["task_id"] == task_id
        assert str(save_kwargs["user_id"]) == sample_payload_dict["user_id"]
        assert len(save_kwargs["variants"]) == 5
        assert save_kwargs["variants"][0].distance_meters == 10042
        assert save_kwargs["variants"][0].fitness_score == pytest.approx(0.95)
        assert save_kwargs["variants"][0].geojson["type"] == "LineString"
        assert save_kwargs["variants"][0].geojson["coordinates"] == [[21.0123, 52.2298], [21.02, 52.23]]

        # Assert state progression published to Redis
        published_states = [
            json.loads(call_args[0][1])["state"] for call_args in mock_redis_client.publish.call_args_list
        ]
        expected_states = [
            TaskStateEnum.LOADING_GRAPH.value,
            TaskStateEnum.SIMPLIFYING_GRAPH.value,
            TaskStateEnum.GENERATING_ROUTE.value,
            TaskStateEnum.GENERATING_ROUTE.value,
            TaskStateEnum.GENERATING_ROUTE.value,
            TaskStateEnum.GENERATING_ROUTE.value,
            TaskStateEnum.GENERATING_ROUTE.value,
            TaskStateEnum.COMPLETED.value,
        ]
        assert published_states == expected_states

    @patch(f"{MODULE_PATH}.save_route_variants_sync")
    @patch(f"{MODULE_PATH}.VNSLoopGenerator")
    @patch(f"{MODULE_PATH}.RouteEvaluator")
    @patch(f"{MODULE_PATH}.CheckpointRefiner.refine_stage_checkpoints")
    @patch(f"{MODULE_PATH}.Subgrapher.extract_subgraphs")
    @patch(f"{MODULE_PATH}.CheckpointsGenerator.generate_checkpoints")
    @patch(f"{MODULE_PATH}.Snapper")
    @patch(f"{MODULE_PATH}.GraphConverter")
    @patch(f"{MODULE_PATH}.GraphBuilder.build_graph")
    @patch(f"{MODULE_PATH}.redis.Redis.from_url")
    def test_generate_route_task_partial_valid_variants(
        self,
        mock_redis_from_url,
        mock_build_graph,
        mock_graph_converter_cls,
        mock_snapper_cls,
        mock_generate_checkpoints,
        mock_extract_subgraphs,
        mock_refine_checkpoints,
        mock_route_evaluator_cls,
        mock_vns_generator_cls,
        mock_save_variants,
        sample_payload_dict,
        mock_redis_client,
    ):
        """Verifies that empty route results in single iterations are skipped and remaining ones are saved."""
        mock_redis_from_url.return_value = mock_redis_client

        mock_raw_graph = MagicMock()
        mock_raw_graph.nodes = [1]
        mock_build_graph.return_value = mock_raw_graph

        mock_converter = MagicMock()
        mock_graph_converter_cls.return_value = mock_converter
        mock_converter.reconstruct_route_from_node_ids.return_value = ([], 5000.0)

        mock_snapper = MagicMock()
        mock_snapper_cls.return_value = mock_snapper
        mock_snapper.snap_point.return_value = (1, GeoPoint(latitude=52.0, longitude=21.0))
        mock_snapper.snap_points.return_value = []

        mock_extract_subgraphs.return_value = []
        mock_refine_checkpoints.return_value = ([], [])

        mock_vns_instance = MagicMock()
        mock_vns_generator_cls.return_value = mock_vns_instance
        # 2 valid loops, 3 empty loops
        mock_vns_instance.generate_route.side_effect = [
            ([1, 2], 0.8),
            ([], 0.0),
            ([1, 3], 0.7),
            ([], 0.0),
            ([], 0.0),
        ]

        mock_self = MagicMock()
        mock_self.request.id = "partial-success-task"

        generate_route_task.run.__func__(mock_self, sample_payload_dict)

        mock_save_variants.assert_called_once()
        variants = mock_save_variants.call_args.kwargs["variants"]
        assert len(variants) == 2


class TestGenerateRouteTaskExceptions:
    @patch(f"{MODULE_PATH}.GraphBuilder.build_graph")
    @patch(f"{MODULE_PATH}.redis.Redis.from_url")
    def test_empty_graph_raises_graph_generation_error_and_publishes_failed(
        self,
        mock_redis_from_url,
        mock_build_graph,
        sample_payload_dict,
        mock_redis_client,
    ):
        """Verifies GraphGenerationError handling when retrieved road graph has 0 nodes."""
        mock_redis_from_url.return_value = mock_redis_client
        mock_empty_graph = MagicMock()
        mock_empty_graph.nodes = []
        mock_build_graph.return_value = mock_empty_graph

        mock_self = MagicMock()
        mock_self.request.id = "empty-graph-task"

        with pytest.raises(GraphGenerationError) as exc_info:
            generate_route_task.run.__func__(mock_self, sample_payload_dict)

        assert "Unable to retrieve road network" in str(exc_info.value)

        # Check last published state
        last_publish_call = mock_redis_client.publish.call_args_list[-1]
        published_payload = json.loads(last_publish_call[0][1])
        assert published_payload["state"] == TaskStateEnum.FAILED.value
        assert "Unable to retrieve road network" in published_payload["payload"]["error_message"]

    @patch(f"{MODULE_PATH}.VNSLoopGenerator")
    @patch(f"{MODULE_PATH}.RouteEvaluator")
    @patch(f"{MODULE_PATH}.CheckpointRefiner.refine_stage_checkpoints")
    @patch(f"{MODULE_PATH}.Subgrapher.extract_subgraphs")
    @patch(f"{MODULE_PATH}.CheckpointsGenerator.generate_checkpoints")
    @patch(f"{MODULE_PATH}.Snapper")
    @patch(f"{MODULE_PATH}.GraphConverter")
    @patch(f"{MODULE_PATH}.GraphBuilder.build_graph")
    @patch(f"{MODULE_PATH}.redis.Redis.from_url")
    def test_all_variants_failed_raises_runtime_error_and_publishes_failed(
        self,
        mock_redis_from_url,
        mock_build_graph,
        mock_graph_converter_cls,
        mock_snapper_cls,
        mock_generate_checkpoints,
        mock_extract_subgraphs,
        mock_refine_checkpoints,
        mock_route_evaluator_cls,
        mock_vns_generator_cls,
        sample_payload_dict,
        mock_redis_client,
    ):
        """Verifies that failing to generate any valid loop raises RuntimeError and emits FAILED state."""
        mock_redis_from_url.return_value = mock_redis_client
        mock_raw_graph = MagicMock()
        mock_raw_graph.nodes = [1]
        mock_build_graph.return_value = mock_raw_graph

        mock_snapper = MagicMock()
        mock_snapper_cls.return_value = mock_snapper
        mock_snapper.snap_point.return_value = (1, GeoPoint(latitude=52.2297, longitude=21.0122))
        mock_snapper.snap_points.return_value = []

        mock_converter = MagicMock()
        mock_graph_converter_cls.return_value = mock_converter
        mock_converter.convert_graph_to_algorithm.return_value = MagicMock()

        mock_extract_subgraphs.return_value = []
        mock_refine_checkpoints.return_value = ([], [])
        mock_generate_checkpoints.return_value = []

        mock_vns_instance = MagicMock()
        mock_vns_generator_cls.return_value = mock_vns_instance
        # All 5 variants fail to generate a loop
        mock_vns_instance.generate_route.return_value = ([], 0.0)

        mock_self = MagicMock()
        mock_self.request.id = "all-failed-task"

        with pytest.raises(RuntimeError) as exc_info:
            generate_route_task.run.__func__(mock_self, sample_payload_dict)

        assert "Failed to generate any valid route variant" in str(exc_info.value)

        last_publish_call = mock_redis_client.publish.call_args_list[-1]
        published_payload = json.loads(last_publish_call[0][1])
        assert published_payload["state"] == TaskStateEnum.FAILED.value
        assert "Failed to generate any valid route variant" in published_payload["payload"]["error_message"]
