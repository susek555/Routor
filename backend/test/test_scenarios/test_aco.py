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

# Distinct high-contrast palette for comparing 5 routes
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
    refined_checkpoints: list[GeoPoint],
    routes: list[list[int]],
    route_lengths: list[float],
    target_distance: float,
    output_html: str,
):
    """Renders Folium map comparing generated routes against waypoints and target distance."""
    m = folium.Map(
        location=[snapped_center.latitude, snapped_center.longitude],
        zoom_start=13,
        tiles=ESRI_SATELLITE,
        attr=ESRI_ATTR,
    )

    # 1. Plot each of the 5 ACO routes
    for idx, (node_path, length) in enumerate(zip(routes, route_lengths, strict=True), start=1):
        color = ROUTE_PALETTE[(idx - 1) % len(ROUTE_PALETTE)]
        diff_meters = length - target_distance
        diff_pct = (diff_meters / target_distance) * 100.0
        sign = "+" if diff_meters >= 0 else ""

        layer_name = f"Route #{idx} | {length / 1000.0:.2f} km ({sign}{diff_meters:.0f} m / {sign}{diff_pct:.1f}%)"
        route_layer = folium.FeatureGroup(name=layer_name, show=True)

        reconstructed_pts = converter.reconstruct_route_from_node_ids(node_path)
        coords = [(p.latitude, p.longitude) for p in reconstructed_pts]

        folium.PolyLine(
            locations=coords,
            color=color,
            weight=4,
            opacity=0.85,
            tooltip=layer_name,
        ).add_to(route_layer)

        route_layer.add_to(m)

    # 2. Checkpoints & Start marker layer
    inspection_layer = folium.FeatureGroup(name="Waypoints (Start + CPs)", show=True)

    folium.Marker(
        [snapped_center.latitude, snapped_center.longitude],
        popup=f"Start: ({snapped_center.latitude:.5f}, {snapped_center.longitude:.5f})",
        icon=folium.Icon(color="green", icon="play"),
    ).add_to(inspection_layer)

    for idx, ref_p in enumerate(refined_checkpoints, start=1):
        folium.CircleMarker(
            location=[ref_p.latitude, ref_p.longitude],
            radius=6,
            color="#FFFFFF",
            weight=2,
            fill=True,
            fill_color="#FF9800",
            fill_opacity=1.0,
            tooltip=f"Refined CP{idx}",
        ).add_to(inspection_layer)

    inspection_layer.add_to(m)

    LayerControl(collapsed=False).add_to(m)
    m.save(output_html)
    print(f"🗺 Comparison map saved to: {os.path.abspath(output_html)}")


def main():
    center = GeoPoint(latitude=50.45, longitude=23.423)  # TL
    # center = GeoPoint(latitude=52.23, longitude=21.00)    # WWA
    # center = GeoPoint(latitude=50.485, longitude=23.495)  # Justynowka
    radius_meters = 5000.0
    target_distance_meters = 2.0 * radius_meters / 0.7  # ~14.28 km target

    print("1. Fetching raw OSM graph...")
    raw_graph = GraphBuilder.build_graph(center, radius_meters)
    if raw_graph is None or len(raw_graph.nodes) == 0:
        print("❌ Graph is empty or failed to load.")
        return

    print("2. Generating raw transit checkpoints...")
    raw_checkpoints = CheckpointsGenerator.generate_checkpoints(center=center, radius=radius_meters)

    print("3. Snapping points on RAW graph (filtering out highway='service')...")
    snapper = Snapper(raw_map=raw_graph)
    start_node_id, snapped_center = snapper.snap_point(center)
    snapped_pairs = snapper.snap_points(raw_checkpoints)

    snapped_node_ids = [start_node_id] + [node_id for node_id, _ in snapped_pairs]
    snapped_checkpoints = [pt for _, pt in snapped_pairs]

    print("4. Simplifying graph while protecting snapped transit nodes...")
    converter = GraphConverter(original_map=raw_graph)
    simple_graph = converter.convert_graph_to_algorithm(protected_nodes=set(snapped_node_ids))

    print("5. Slicing graph into stage corridor subgraphs...")
    points_chain = [snapped_center] + snapped_checkpoints
    stage_subgraphs = Subgrapher.extract_subgraphs(
        map=simple_graph,
        checkpoints=points_chain,
        checkpoint_node_ids=snapped_node_ids,
        base_lateral_slack_meters=160.0,
        max_lateral_slack_meters=320.0,
    )

    print("6. Refining checkpoints within stage subgraphs (collapsing spurs to forks)...")
    refined_node_ids, stage_subgraphs = CheckpointRefiner.refine_stage_checkpoints(
        stage_subgraphs=stage_subgraphs,
        checkpoint_node_ids=snapped_node_ids,
        target_distance_meters=target_distance_meters,
        max_retraction_ratio=0.12,
    )

    refined_checkpoints: list[GeoPoint] = []
    for node_id in refined_node_ids[1:]:
        node_data = simple_graph.nodes[node_id]
        lat = node_data.get("y", node_data.get("lat"))
        lon = node_data.get("x", node_data.get("lon"))
        refined_checkpoints.append(GeoPoint(latitude=lat, longitude=lon))

    print(f"\n🎯 Target distance: {target_distance_meters / 1000.0:.2f} km ({target_distance_meters:.0f} m)")
    print("7. Running 5 independent ACO runs for comparison...")

    aco_params = ACOParams(
        num_ants=25,
        num_iterations=30,
        alpha=1.0,
        beta=2.0,
        evaporation_rate=0.15,
        initial_pheromone=1.0,
        target_distance=target_distance_meters,
        fitness_alpha=2.5,
        fitness_beta=3.0,
    )

    generated_routes: list[list[int]] = []
    generated_lengths: list[float] = []

    for run_idx in range(1, 6):
        aco = ACO(
            params=aco_params,
            checkpoints=refined_node_ids,
            stage_graphs=stage_subgraphs,
        )
        route_nodes = aco.generate_route()
        reconstructed_pts = converter.reconstruct_route_from_node_ids(route_nodes)
        actual_distance = calculate_reconstructed_distance(reconstructed_pts)

        diff = actual_distance - target_distance_meters
        diff_pct = (diff / target_distance_meters) * 100.0
        sign = "+" if diff >= 0 else ""

        generated_routes.append(route_nodes)
        generated_lengths.append(actual_distance)

        print(
            f"   -> Run #{run_idx}: {actual_distance / 1000.0:.2f} km "
            f"({sign}{diff:.0f} m | {sign}{diff_pct:.1f}%) | Nodes: {len(route_nodes)}"
        )

    output_html = "test_aco_comparison_result.html"
    plot_routes_comparison_map(
        converter=converter,
        snapped_center=snapped_center,
        refined_checkpoints=refined_checkpoints,
        routes=generated_routes,
        route_lengths=generated_lengths,
        target_distance=target_distance_meters,
        output_html=output_html,
    )


if __name__ == "__main__":
    main()
