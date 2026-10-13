import os

import folium
from folium import LayerControl
from src.database.geo_point import GeoPoint
from src.generate_routes.algorithm.aco.aco import ACO
from src.generate_routes.algorithm.aco.aco_params import ACOParams
from src.generate_routes.algorithm.aco.utils import haversine
from src.generate_routes.algorithm.checkpoint_refiner import CheckpointRefiner
from src.generate_routes.algorithm.checkpoints_generator import CheckpointsGenerator
from src.generate_routes.algorithm.snapper import Snapper
from src.generate_routes.algorithm.subgrapher import Subgrapher
from src.generate_routes.graph_builder.graph_builder import GraphBuilder
from src.generate_routes.graph_builder.graph_converter import GraphConverter

ESRI_SATELLITE = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
ESRI_ATTR = "Esri World Imagery"

# Distinct color palette for 5 unique loop alternatives
ROUTE_PALETTE = ["#00E5FF", "#FF0055", "#76FF03", "#FFD600", "#D500F9"]


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
    """Renders Folium map with 5 alternative ACO generated routes."""
    m = folium.Map(
        location=[snapped_center.latitude, snapped_center.longitude],
        zoom_start=13,
        tiles=ESRI_SATELLITE,
        attr=ESRI_ATTR,
    )

    # Common Start Marker
    start_layer = folium.FeatureGroup(name="Start Point", show=True)
    folium.Marker(
        [snapped_center.latitude, snapped_center.longitude],
        popup=f"Start: ({snapped_center.latitude:.5f}, {snapped_center.longitude:.5f})",
        icon=folium.Icon(color="green", icon="play"),
    ).add_to(start_layer)
    start_layer.add_to(m)

    # Draw each route and its own checkpoints
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

        # 1. PolyLine of reconstructed curve
        reconstructed_pts = converter.reconstruct_route_from_node_ids(node_path)
        coords = [(p.latitude, p.longitude) for p in reconstructed_pts]

        folium.PolyLine(
            locations=coords,
            color=color,
            weight=4,
            opacity=0.85,
            tooltip=layer_name,
        ).add_to(route_group)

        # 2. Refined Checkpoint markers for this route
        for cp_idx, ref_p in enumerate(refined_cps, start=1):
            folium.CircleMarker(
                location=[ref_p.latitude, ref_p.longitude],
                radius=5,
                color="#FFFFFF",
                weight=1.5,
                fill=True,
                fill_color=color,
                fill_opacity=0.9,
                tooltip=f"Trasa #{idx} - CP{cp_idx}",
            ).add_to(route_group)

        route_group.add_to(m)

    LayerControl(collapsed=False).add_to(m)
    m.save(output_html)
    print(f"\n🗺 Mapa porównawcza 5 tras zapisana do: {os.path.abspath(output_html)}")


def main():
    center = GeoPoint(latitude=50.45, longitude=23.423)  # TL
    # center = GeoPoint(latitude=52.23, longitude=21.00)  # WWA
    # center = GeoPoint(latitude=50.485, longitude=23.495)  # Justynowka
    radius_meters = 2500.0
    target_distance_meters = 2.0 * radius_meters

    print("1. Pobieranie surowego grafu OSM raz dla całego obszaru...")
    raw_graph = GraphBuilder.build_graph(center, radius_meters)
    if raw_graph is None or len(raw_graph.nodes) == 0:
        print("❌ Graf jest pusty.")
        return

    snapper = Snapper(raw_map=raw_graph)
    start_node_id, snapped_center = snapper.snap_point(center)
    print(f"   -> Start snap: node {start_node_id} ({snapped_center.latitude:.5f}, {snapped_center.longitude:.5f})")

    aco_params = ACOParams(
        num_ants=25,
        num_iterations=30,
        alpha=1.0,
        beta=2.0,
        evaporation_rate=0.15,
        initial_pheromone=1.0,
        target_distance=target_distance_meters,
        fitness_alpha=1.5,
        fitness_beta=20.0,
    )

    routes_data = []
    converter = None

    print(f"\n🎯 Docelowy dystans: {target_distance_meters / 1000.0:.2f} km ({target_distance_meters:.0f} m)")
    print("================================================================================")

    for route_idx in range(1, 6):
        print(f"\n--- Generowanie Wariantu Trasy #{route_idx}/5 ---")

        # 1. Losowanie nowego szkieletu punktów kontrolnych (inny obrót / układ)
        raw_checkpoints = CheckpointsGenerator.generate_checkpoints(center=center, radius=radius_meters)
        snapped_pairs = snapper.snap_points(raw_checkpoints)

        snapped_node_ids = [start_node_id] + [node_id for node_id, _ in snapped_pairs]
        snapped_checkpoints = [pt for _, pt in snapped_pairs]

        # 2. Uproszczenie topologiczne z zabezpieczeniem węzłów bieżącej trasy
        converter = GraphConverter(original_map=raw_graph)
        simple_graph = converter.convert_graph_to_algorithm(protected_nodes=set(snapped_node_ids))

        # 3. Wycięcie korytarzy etapowych
        points_chain = [snapped_center] + snapped_checkpoints
        stage_subgraphs = Subgrapher.extract_subgraphs(
            map=simple_graph,
            checkpoints=points_chain,
            checkpoint_node_ids=snapped_node_ids,
            base_lateral_slack_meters=160.0,
            max_lateral_slack_meters=320.0,
        )

        # 4. Zwijanie wybiegów / agrafek
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

        # 5. Uruchomienie ACO na wyciętych podgrafach
        aco = ACO(
            params=aco_params,
            checkpoints=refined_node_ids,
            stage_graphs=stage_subgraphs,
        )
        route_nodes, route_fitness = aco.generate_route()

        reconstructed_pts = converter.reconstruct_route_from_node_ids(route_nodes)
        actual_distance = calculate_reconstructed_distance(reconstructed_pts)

        diff = actual_distance - target_distance_meters
        diff_pct = (diff / target_distance_meters) * 100.0
        sign = "+" if diff >= 0 else ""

        print(
            f"✅ Wariant #{route_idx}: {actual_distance / 1000.0:.2f} km "
            f"({sign}{diff:.0f} m | {sign}{diff_pct:.1f}%) | Węzłów: {len(route_nodes)}"
            f" | Fitness: {route_fitness:.4f}"
        )

        routes_data.append(
            {
                "path": route_nodes,
                "length": actual_distance,
                "refined_checkpoints": refined_checkpoints,
            }
        )

    # Wizualizacja wszystkich 5 tras na jednej mapie
    output_html = "test_5_different_routes_comparison.html"
    plot_routes_comparison_map(
        converter=converter,
        snapped_center=snapped_center,
        routes_data=routes_data,
        target_distance=target_distance_meters,
        output_html=output_html,
    )


if __name__ == "__main__":
    main()
