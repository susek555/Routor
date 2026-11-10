import asyncio
import json
import logging
import time

import redis

from src.api.data.task_payload import TaskPayload
from src.api.data.task_state import (
    FailedTaskStatePayload,
    ProgressTaskStatePayload,
    TaskState,
    TaskStateEnum,
)
from src.api.exceptions.exceptions import GraphGenerationError
from src.app import REDIS_URL
from src.database.database import get_single_dummy_message
from src.database.dto.route import CalculatedVariantDTO
from src.database.query.route import save_route_variants_sync
from src.firebase_notification import send_push_notification
from src.generate_routes.algorithm.checkpoint_refiner import CheckpointRefiner
from src.generate_routes.algorithm.checkpoints_generator import CheckpointsGenerator
from src.generate_routes.algorithm.evaluator import RouteEvaluator
from src.generate_routes.algorithm.evaluator_params import EvaluatorParams
from src.generate_routes.algorithm.snapper import Snapper
from src.generate_routes.algorithm.subgrapher import Subgrapher
from src.generate_routes.algorithm.vns.vns_generator import VNSLoopGenerator
from src.generate_routes.algorithm.vns.vns_params import VNSParams
from src.generate_routes.graph_builder.graph_builder import GraphBuilder
from src.generate_routes.graph_builder.graph_converter import GraphConverter
from src.generate_routes.worker_app import celery_app, redis_url

logger = logging.getLogger(__name__)


@celery_app.task(name="generate_routes.dummy_task")
def dummy_task(fcm_token: str, ip: str, dummy_message: str):
    print(f"Starting heavy task for user {ip}...")
    time.sleep(10)

    try:
        message_from_db = asyncio.run(get_single_dummy_message())
        print(f"Database communication successful. Retrieved: {message_from_db}")
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to communicate with DB inside Celery: {str(e)}")
        raise e

    r = redis.Redis.from_url(redis_url)
    payload = {
        "event": "DUMMY_TASK_PERFORMED",
        "status": "success",
        "user_ip": ip,
        "message": "Message from worker through redis websocket.",
    }

    # REDIS
    print("Publishing notification to Redis channel...")
    r.publish("global_notifications", json.dumps(payload))

    # GOOGLE FIREBASE
    send_push_notification(fcm_token, "Task has been finished", "Message through google firebase")

    print("Task finished!")
    return {
        "status": "success",
        "user_ip": ip,
        "message_api": dummy_message,
        "message_database": message_from_db,
    }


def update_task_state(task_id: str, payload: TaskState, r: redis.Redis):
    data = payload.model_dump_json()
    state_key = f"routes:state:{task_id}"
    channel = f"routes:{task_id}"

    # TTL = 30 minutes
    r.set(state_key, data, ex=1800)

    # Inform active WebSocket clients about the state change
    r.publish(channel, data)


@celery_app.task(bind=True, name="generate_routes.generate")
def generate_route_task(self, payload_dict: dict):
    payload = TaskPayload.model_validate(payload_dict)
    task_id = self.request.id

    logger.info(f"Starting route generation task with ID {task_id} for user {payload.user_id}...")
    r = redis.Redis.from_url(REDIS_URL)

    try:
        center = payload.center
        target_distance_meters = float(payload.target_distance)
        RADIUS_FACTOR = 0.5  # Factor to determine the radius of the area to consider for route generation
        radius_meters = target_distance_meters * RADIUS_FACTOR

        # --- 1. LOADING GRAPH ---
        update_task_state(task_id, TaskState(state=TaskStateEnum.LOADING_GRAPH), r)
        raw_graph = GraphBuilder.build_graph(center, radius_meters)
        if raw_graph is None or len(raw_graph.nodes) == 0:
            raise GraphGenerationError("Unable to retrieve road network for the specified location.")

        # --- 2. SIMPLIFYING GRAPH ---
        update_task_state(task_id, TaskState(state=TaskStateEnum.SIMPLIFYING_GRAPH), r)
        converter = GraphConverter(original_map=raw_graph)
        simple_graph = converter.convert_graph_to_algorithm()

        snapper = Snapper(raw_map=simple_graph)
        start_node_id, snapped_center = snapper.snap_point(center)
        vns_params = VNSParams(target_distance=target_distance_meters)

        # --- 3. GENERATING ROUTES ---
        total_variants = 5
        calculated_variants: list[CalculatedVariantDTO] = []

        for route_idx in range(1, total_variants + 1):
            update_task_state(
                task_id,
                TaskState(
                    state=TaskStateEnum.GENERATING_ROUTE,
                    payload=ProgressTaskStatePayload(done=route_idx - 1, total=total_variants),
                ),
                r,
            )

            raw_checkpoints = CheckpointsGenerator.generate_checkpoints(center=center, radius=radius_meters)
            snapped_pairs = snapper.snap_points(raw_checkpoints)

            snapped_node_ids = [start_node_id] + [node_id for node_id, _ in snapped_pairs]
            snapped_checkpoints = [pt for _, pt in snapped_pairs]
            points_chain = [snapped_center] + snapped_checkpoints

            stage_subgraphs = Subgrapher.extract_subgraphs(
                map_graph=simple_graph,
                checkpoints=points_chain,
                checkpoint_node_ids=snapped_node_ids,
            )

            refined_node_ids, stage_subgraphs = CheckpointRefiner.refine_stage_checkpoints(
                stage_subgraphs=stage_subgraphs,
                checkpoint_node_ids=snapped_node_ids,
                target_distance_meters=target_distance_meters,
                max_retraction_ratio=0.25,
            )

            evaluator = RouteEvaluator(
                stage_graphs=stage_subgraphs,
                target_distance=target_distance_meters,
                params=EvaluatorParams(),
            )

            vns_generator = VNSLoopGenerator(
                params=vns_params,
                checkpoints=refined_node_ids,
                stage_graphs=stage_subgraphs,
                evaluator=evaluator,
            )

            route_nodes, route_fitness = vns_generator.generate_route()
            if not route_nodes:
                logger.warning(f"Variant #{route_idx} could not find a valid loop.")
                continue

            # Reconstruct the route geometry from node IDs and calculate the actual distance
            reconstructed_pts, actual_distance = converter.reconstruct_route_from_node_ids(route_nodes)

            # MapLibre GeoJSON coordinates standard: [longitude, latitude]
            coordinates = [[pt.longitude, pt.latitude] for pt in reconstructed_pts]

            calculated_variants.append(
                CalculatedVariantDTO(
                    variant_index=route_idx,
                    distance_meters=int(round(actual_distance)),
                    fitness_score=float(route_fitness),
                    geojson={
                        "type": "LineString",
                        "coordinates": coordinates,
                    },
                )
            )

        if not calculated_variants:
            raise RuntimeError("Failed to generate any valid route variant for given parameters.")

        # --- 4. SAVE TO DATABASE ---
        save_route_variants_sync(
            task_id=task_id,
            user_id=payload.user_id,
            variants=calculated_variants,
        )

        # --- 5. TASK FINISHED ---
        update_task_state(task_id, TaskState(state=TaskStateEnum.COMPLETED), r)

        # --- 6. PUSH NOTIFICATION (FIREBASE) ---
        # if payload.fcm_token:
        #     send_push_notification(
        #         fcm_token=payload.fcm_token,
        #         title="Trasy są gotowe!",
        #         body=f"Wygenerowano {len(calculated_variants)} alternatywnych propozycji treningu.",
        #     )

        logger.info(f"Route task {task_id} completed. Generated {len(calculated_variants)} routes.")

    except Exception as exc:
        logger.exception(f"Fatal error during route generation for {task_id}")
        error_msg = str(exc).strip() or "Unknown algorithmic error."

        update_task_state(
            task_id,
            TaskState(
                state=TaskStateEnum.FAILED,
                payload=FailedTaskStatePayload(error_message=error_msg),
            ),
            r,
        )
        raise exc
