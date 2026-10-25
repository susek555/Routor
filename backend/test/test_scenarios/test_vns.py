import logging
import math
import os
import time

import folium
from folium import LayerControl
from src.database.geo_point import GeoPoint
from src.generate_routes.algorithm.aco.evaluator import RouteEvaluator
from src.generate_routes.algorithm.aco.utils.common import get_heading_rad, haversine
from src.generate_routes.algorithm.aco.utils.evaluator import BoundingBoxEnum, EvaluatorParams
from src.generate_routes.algorithm.checkpoint_refiner import CheckpointRefiner
from src.generate_routes.algorithm.checkpoints_generator import CheckpointsGenerator
from src.generate_routes.algorithm.snapper import Snapper
from src.generate_routes.algorithm.subgrapher import Subgrapher
from src.generate_routes.algorithm.vns.vns_generator import VNSLoopGenerator
from src.generate_routes.algorithm.vns.vns_params import VNSParams
from src.generate_routes.graph_builder.graph_builder import GraphBuilder
from src.generate_routes.graph_builder.graph_converter import GraphConverter

logging.basicConfig(level=logging.INFO)

ESRI_SATELLITE = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
ESRI_ATTR = "Esri World Imagery"

ROUTE_PALETTE = ["#00E5FF", "#FF0055", "#76FF03", "#FFD600", "#D500F9"]


def create_base_map(center: GeoPoint, zoom: int = 14) -> folium.Map:
    """Tworzy bazową mapę z warstwą satelitarną Esri i OSM."""
    m = folium.Map(
        location=[center.latitude, center.longitude],
        zoom_start=zoom,
        tiles=None,
    )

    folium.TileLayer(
        tiles=ESRI_SATELLITE,
        attr=ESRI_ATTR,
        name="Esri Satellite",
        max_zoom=19,
        overlay=False,
        control=True,
    ).add_to(m)

    folium.TileLayer(
        tiles="OpenStreetMap",
        name="OpenStreetMap",
        overlay=False,
        control=True,
    ).add_to(m)

    return m


def calculate_reconstructed_distance(points: list[GeoPoint]) -> float:
    """Computes total route distance in meters from reconstructed GPS points."""
    total_dist = 0.0
    for i in range(len(points) - 1):
        p1 = (points[i].latitude, points[i].longitude)
        p2 = (points[i + 1].latitude, points[i + 1].longitude)
        total_dist += haversine(p1, p2)
    return total_dist


def plot_routes_comparison_map(
    converter: GraphConverter,
    snapped_center: GeoPoint,
    routes_data: list[dict],
    target_distance: float,
    output_html: str,
):
    """Renders Folium map with alternative VNS generated routes."""
    m = create_base_map(snapped_center, zoom=13)

    start_layer = folium.FeatureGroup(name="Punkt startowy", show=True)
    folium.Marker(
        [snapped_center.latitude, snapped_center.longitude],
        popup=f"Start: ({snapped_center.latitude:.5f}, {snapped_center.longitude:.5f})",
        icon=folium.Icon(color="green", icon="play"),
    ).add_to(start_layer)
    start_layer.add_to(m)

    for idx, item in enumerate(routes_data, start=1):
        color = ROUTE_PALETTE[(idx - 1) % len(ROUTE_PALETTE)]
        length = item["length"]
        node_path = item["path"]
        refined_cps = item["refined_checkpoints"]

        diff_meters = length - target_distance
        diff_pct = (diff_meters / target_distance) * 100.0
        sign = "+" if diff_meters >= 0 else ""

        layer_name = f"Trasa #{idx} | {length / 1000.0:.2f} km ({sign}{diff_meters:.0f} m / {sign}{diff_pct:.1f}%)"
        route_group = folium.FeatureGroup(name=layer_name, show=True)

        reconstructed_pts = converter.reconstruct_route_from_node_ids(node_path)
        coords = [(p.latitude, p.longitude) for p in reconstructed_pts]

        folium.PolyLine(
            locations=coords,
            color=color,
            weight=4,
            opacity=0.85,
            tooltip=layer_name,
        ).add_to(route_group)

        for cp_idx, ref_p in enumerate(refined_cps, start=1):
            folium.CircleMarker(
                location=[ref_p.latitude, ref_p.longitude],
                radius=5,
                color="#FFFFFF",
                weight=1.5,
                fill=True,
                fill_color=color,
                fill_opacity=0.9,
                tooltip=f"Trasa #{idx} | CP {cp_idx}",
            ).add_to(route_group)

        route_group.add_to(m)

    LayerControl(collapsed=False).add_to(m)
    m.save(output_html)
    print(f"\n🗺 Mapa porównawcza tras zapisana do: {os.path.abspath(output_html)}")


def visualize_all_routes_overlaps(
    snapped_center: GeoPoint,
    routes_data: list[dict],
    evaluator_params: EvaluatorParams,
    output_html_path: str = "routes_overlap_comparison.html",
) -> None:
    """Generuje wspólną mapę Folium dla wszystkich tras z detekcją nakładań."""
    debug_map = create_base_map(snapped_center, zoom=14)

    exclusion_radius = evaluator_params.start_finish_exclusion_radius_meters
    deg_lat = evaluator_params.bounding_box.DEG_LAT
    deg_lon = evaluator_params.bounding_box.DEG_LON

    zone_layer = folium.FeatureGroup(name="Strefa Start/Meta (Ochronna)", show=True)
    folium.Circle(
        location=[snapped_center.latitude, snapped_center.longitude],
        radius=exclusion_radius,
        color="#28a745",
        fill=True,
        fill_opacity=0.2,
        tooltip=f"Start/Finish Protected Exclusion Zone ({exclusion_radius:.0f}m)",
    ).add_to(zone_layer)
    folium.Marker(
        [snapped_center.latitude, snapped_center.longitude],
        popup="Start / Meta",
        icon=folium.Icon(color="green", icon="flag"),
    ).add_to(zone_layer)
    zone_layer.add_to(debug_map)

    total_out_and_back = 0
    total_opposite = 0
    start_coord = (snapped_center.latitude, snapped_center.longitude)

    for idx, item in enumerate(routes_data, start=1):
        full_path: list[int] = item["path"]
        evaluator: RouteEvaluator = item["evaluator"]
        color = ROUTE_PALETTE[(idx - 1) % len(ROUTE_PALETTE)]

        if len(full_path) < evaluator_params.min_path_nodes_to_overlap:
            continue

        route_group = folium.FeatureGroup(name=f"Nakładania - Trasa #{idx}", show=(idx == 1))

        path_coords: list[tuple[float, float]] = []
        for u, v in zip(full_path[:-1], full_path[1:]):
            samples, _ = evaluator.edge_info_cache.get((u, v), ([(0.0, 0.0)], 1.0))
            path_coords.extend(samples)

        folium.PolyLine(
            locations=path_coords,
            color=color,
            weight=3,
            opacity=0.5,
            tooltip=f"Trasa #{idx} Path",
        ).add_to(route_group)

        visited_edges: set[frozenset[int]] = set()
        history: list[tuple[tuple[float, float], float, float, bool]] = []
        current_cumulative_dist = 0.0

        out_and_back_count = 0
        opposite_count = 0

        for i in range(len(full_path) - 1):
            u, v = full_path[i], full_path[i + 1]
            if u == v:
                continue

            edge_key = frozenset((u, v))
            samples, edge_len = evaluator.edge_info_cache.get((u, v), ([(0.0, 0.0)], 1.0))

            c_u = evaluator.node_coord_cache.get(u, (0.0, 0.0))
            c_v = evaluator.node_coord_cache.get(v, (0.0, 0.0))
            curr_heading = get_heading_rad(c_u, c_v)

            is_edge_protected = any(evaluator._is_near_start_finish(pt, start_coord) for pt in samples)

            # 1. Bezwzględne powtórzenie topologiczne
            if edge_key in visited_edges:
                if not is_edge_protected:
                    out_and_back_count += 1
                    mid_sample = samples[len(samples) // 2]
                    folium.CircleMarker(
                        location=[mid_sample[0], mid_sample[1]],
                        radius=6,
                        color="#dc3545",
                        fill=True,
                        fill_color="#dc3545",
                        fill_opacity=0.9,
                        popup=(
                            f"<b>TRASA #{idx} - OUT-AND-BACK</b><br>"
                            f"Krok: {i}<br>Krawędź: ({u}, {v})<br>"
                            f"Długość: {edge_len:.1f}m<br>"
                            f"Kara: {evaluator_params.out_and_back_penalty_multiplier}x"
                        ),
                    ).add_to(route_group)
            else:
                # 2. Przeciwbieżny korytarz
                if not is_edge_protected:
                    conflict_found = False
                    for pt in samples:
                        if evaluator._is_near_start_finish(pt, start_coord):
                            continue

                        lat_m, lon_m = pt
                        for (prev_lat, prev_lon), prev_heading, prev_cum_dist, prev_in_zone in history:
                            if prev_in_zone:
                                continue

                            if (current_cumulative_dist - prev_cum_dist) < evaluator_params.min_path_separation_meters:
                                continue

                            if abs(lat_m - prev_lat) < deg_lat and abs(lon_m - prev_lon) < deg_lon:
                                dist = haversine(pt, (prev_lat, prev_lon))
                                if dist < evaluator_params.default_corridor_threshold_meters:
                                    delta_heading = abs(curr_heading - prev_heading)
                                    if delta_heading > math.pi:
                                        delta_heading = 2.0 * math.pi - delta_heading

                                    if delta_heading >= evaluator_params.antiparallel_min_rad:
                                        if evaluator._is_perpendicular_corridor(pt, (prev_lat, prev_lon), curr_heading):
                                            opposite_count += 1
                                            folium.CircleMarker(
                                                location=[lat_m, lon_m],
                                                radius=5,
                                                color="#9c27b0",
                                                fill=True,
                                                fill_color="#9c27b0",
                                                fill_opacity=0.9,
                                                popup=(
                                                    f"<b>TRASA #{idx} - OPPOSITE CORRIDOR</b><br>"
                                                    f"Krok: {i}<br>"
                                                    f"Separacja wzdłuż trasy: {current_cumulative_dist - prev_cum_dist:.1f}m<br>"
                                                    f"Odległość boczna: {dist:.1f}m &lt; {evaluator_params.default_corridor_threshold_meters}m<br>"
                                                    f"Kąt zwrotu: {math.degrees(delta_heading):.1f}°<br>"
                                                    f"Mnożnik kary: {evaluator_params.opposite_corridor_penalty_multiplier}x"
                                                ),
                                            ).add_to(route_group)

                                            folium.PolyLine(
                                                locations=[[lat_m, lon_m], [prev_lat, prev_lon]],
                                                color="#ffc107",
                                                weight=2,
                                                dash_array="4, 6",
                                                opacity=0.8,
                                                tooltip=f"T#{idx} Konflikt korytarza: {dist:.1f}m",
                                            ).add_to(route_group)

                                            conflict_found = True
                                            break

                        if conflict_found:
                            break

            visited_edges.add(edge_key)
            for pt in samples:
                in_zone = evaluator._is_near_start_finish(pt, start_coord)
                history.append((pt, curr_heading, current_cumulative_dist, in_zone))

            current_cumulative_dist += edge_len

        route_group.add_to(debug_map)
        total_out_and_back += out_and_back_count
        total_opposite += opposite_count

    LayerControl(collapsed=False).add_to(debug_map)
    debug_map.save(output_html_path)

    print(
        f"\n🗺️ Zbiorcza mapa overlapów wygenerowana pod: {os.path.abspath(output_html_path)}\n"
        f"   - Łącznie Out-and-back: {total_out_and_back}\n"
        f"   - Łącznie Przeciwne korytarze (Opposite / Hairpin): {total_opposite}"
    )


def main():
    # center = GeoPoint(latitude=50.45, longitude=23.423)  # TL
    # center = GeoPoint(latitude=52.323832, longitude=20.948670)
    center = GeoPoint(latitude=52.23, longitude=21.00)  # WWA
    # center = GeoPoint(latitude=50.485, longitude=23.495)  # Justynowka
    radius_meters = 10000.0
    target_distance_meters = 2.0 * radius_meters

    print("1. Pobieranie surowego grafu OSM raz dla całego obszaru...")
    raw_graph = GraphBuilder.build_graph(center, radius_meters)
    if raw_graph is None or len(raw_graph.nodes) == 0:
        print("❌ Graf jest pusty.")
        return

    print("2. Upraszczanie grafu i usuwanie dróg prywatnych...")
    converter = GraphConverter(original_map=raw_graph)
    simple_graph = converter.convert_graph_to_algorithm()

    snapper = Snapper(raw_map=simple_graph)
    start_node_id, snapped_center = snapper.snap_point(center)
    print(f"   -> Start snap: node {start_node_id} ({snapped_center.latitude:.5f}, {snapped_center.longitude:.5f})")

    # 3. Konfiguracja parametrów ewaluatora (dokładnie te same co w ACO)
    evaluator_params = EvaluatorParams(
        distance_penalty_weight=2.0,
        overlap_penalty_weight=5.0,
        bounding_box=BoundingBoxEnum.M_80.value,
    )

    # 4. Parametry nowego algorytmu VNS
    vns_params = VNSParams(
        target_distance=target_distance_meters,
    )

    routes_data = []

    print(f"\n🎯 Docelowy dystans: {target_distance_meters / 1000.0:.2f} km ({target_distance_meters:.0f} m)")
    print("=" * 80)

    for route_idx in range(1, 6):
        print(f"\n--- Generowanie Wariantu Trasy VNS #{route_idx}/5 ---")
        start_time = time.perf_counter()

        # Generowanie losowych punktów kontrolnych dla danego wariantu
        raw_checkpoints = CheckpointsGenerator.generate_checkpoints(center=center, radius=radius_meters)
        snapped_pairs = snapper.snap_points(raw_checkpoints)

        snapped_node_ids = [start_node_id] + [node_id for node_id, _ in snapped_pairs]
        snapped_checkpoints = [pt for _, pt in snapped_pairs]

        points_chain = [snapped_center] + snapped_checkpoints
        stage_subgraphs = Subgrapher.extract_subgraphs(
            map_graph=simple_graph, checkpoints=points_chain, checkpoint_node_ids=snapped_node_ids
        )

        refined_node_ids, stage_subgraphs = CheckpointRefiner.refine_stage_checkpoints(
            stage_subgraphs=stage_subgraphs,
            checkpoint_node_ids=snapped_node_ids,
            target_distance_meters=target_distance_meters,
            max_retraction_ratio=0.25,
        )

        refined_checkpoints = []
        for node_id in refined_node_ids[1:]:
            node_data = simple_graph.nodes[node_id]
            lat = node_data.get("y", node_data.get("lat"))
            lon = node_data.get("x", node_data.get("lon"))
            refined_checkpoints.append(GeoPoint(latitude=lat, longitude=lon))

        # Przygotowanie ewaluatora
        evaluator = RouteEvaluator(
            stage_graphs=stage_subgraphs,
            target_distance=target_distance_meters,
            params=evaluator_params,
        )

        # Uruchomienie solvera VNS
        vns_generator = VNSLoopGenerator(
            params=vns_params,
            checkpoints=refined_node_ids,  # <--- PRZEKAZUJEMY CHECKPOINTY
            stage_graphs=stage_subgraphs,  # <--- ORAZ PODGRAFY ETAPÓW
            evaluator=evaluator,
        )

        route_nodes, route_fitness = vns_generator.generate_route()
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        if not route_nodes:
            print("⚠️ Nie udało się wyznaczyć poprawnej pętli VNS.")
            continue

        reconstructed_pts = converter.reconstruct_route_from_node_ids(route_nodes)
        actual_distance = calculate_reconstructed_distance(reconstructed_pts)

        print(
            f"⏱️ Czas generowania: {elapsed_ms:.1f} ms | Długość: {actual_distance:.1f} m | Fitness: {route_fitness:.4f}"
        )

        routes_data.append(
            {
                "path": route_nodes,
                "length": actual_distance,
                "refined_checkpoints": refined_checkpoints,
                "evaluator": evaluator,
            }
        )

    # 1. Mapa porównawcza 5 tras
    plot_routes_comparison_map(
        converter=converter,
        snapped_center=snapped_center,
        routes_data=routes_data,
        target_distance=target_distance_meters,
        output_html="test_5_different_routes_comparison_vns.html",
    )

    # 2. Zbiorcza mapa nakładań z parametrami z EvaluatorParams
    visualize_all_routes_overlaps(
        snapped_center=snapped_center,
        routes_data=routes_data,
        evaluator_params=evaluator_params,
        output_html_path="routes_overlap_comparison_vns.html",
    )


if __name__ == "__main__":
    main()
