import os

import folium
from folium import LayerControl

from src.database.geo_point import GeoPoint
from src.generate_routes.algorithm.checkpoint_refiner import CheckpointRefiner
from src.generate_routes.algorithm.checkpoints_generator import CheckpointsGenerator
from src.generate_routes.algorithm.snapper import Snapper
from src.generate_routes.algorithm.subgrapher import Subgrapher
from src.generate_routes.data.map import Map
from src.generate_routes.graph_builder.graph_builder import GraphBuilder
from src.generate_routes.graph_builder.graph_converter import GraphConverter

ESRI_SATELLITE = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
ESRI_ATTR = "Esri World Imagery"

# Palette for sequential stage corridors
STAGE_PALETTE = ["#FF0055", "#00E5FF", "#76FF03", "#FFB300"]


def plot_pipeline_map(
    converter: GraphConverter,
    raw_center: GeoPoint,
    snapped_center: GeoPoint,
    raw_checkpoints: list[GeoPoint],
    snapped_checkpoints: list[GeoPoint],
    refined_checkpoints: list[GeoPoint],
    stage_subgraphs: list[Map],
    output_html: str,
):
    """Generates an interactive Folium map illustrating pipeline stages and refinement vectors."""
    m = folium.Map(
        location=[snapped_center.latitude, snapped_center.longitude],
        zoom_start=14,
        tiles=ESRI_SATELLITE,
        attr=ESRI_ATTR,
    )

    # 1. Stage subgraphs with exact road curve reconstruction
    for idx, stage_graph in enumerate(stage_subgraphs, start=1):
        color = STAGE_PALETTE[(idx - 1) % len(STAGE_PALETTE)]
        stage_layer = folium.FeatureGroup(
            name=f"Stage {idx} Subgraph ({len(stage_graph.nodes)} nodes, {len(stage_graph.edges)} edges)",
            show=True,
        )

        for u, v in stage_graph.edges():
            geometry = converter.reconstruct_route_from_node_ids([u, v])
            coords = [(p.latitude, p.longitude) for p in geometry]
            folium.PolyLine(locations=coords, color=color, weight=3, opacity=0.85).add_to(stage_layer)

        for n, data in stage_graph.nodes(data=True):
            lat = data.get("y", data.get("lat"))
            lon = data.get("x", data.get("lon"))
            if lat is None or lon is None:
                continue

            folium.CircleMarker(
                location=[lat, lon],
                radius=3,
                color=color,
                weight=1,
                fill=True,
                fill_color=color,
                fill_opacity=0.9,
                tooltip=f"Stage {idx} | Node ID: {n}",
            ).add_to(stage_layer)

        stage_layer.add_to(m)

    # 2. Snapping & Refinement inspection layer
    inspection_layer = folium.FeatureGroup(name="Waypoints Refinement Inspection", show=True)

    # Start point
    folium.PolyLine(
        locations=[
            (raw_center.latitude, raw_center.longitude),
            (snapped_center.latitude, snapped_center.longitude),
        ],
        color="#FFFFFF",
        weight=2,
        dash_array="2, 6",
    ).add_to(inspection_layer)

    folium.Marker(
        [snapped_center.latitude, snapped_center.longitude],
        popup=f"Start: ({snapped_center.latitude:.5f}, {snapped_center.longitude:.5f})",
        icon=folium.Icon(color="green", icon="play"),
    ).add_to(inspection_layer)

    # Checkpoints (Raw -> Snapped -> Refined)
    for raw_p, snap_p, ref_p, idx in zip(
        raw_checkpoints, snapped_checkpoints, refined_checkpoints, range(1, len(raw_checkpoints) + 1), strict=False
    ):
        color = STAGE_PALETTE[(idx - 1) % len(STAGE_PALETTE)]

        # Vector: Raw -> Snapped
        folium.PolyLine(
            locations=[(raw_p.latitude, raw_p.longitude), (snap_p.latitude, snap_p.longitude)],
            color="#FFFFFF",
            weight=1.5,
            dash_array="2, 6",
        ).add_to(inspection_layer)

        # Vector: Snapped -> Refined (pokazuje cofnięcie z zaułka do skrzyżowania)
        if (snap_p.latitude, snap_p.longitude) != (ref_p.latitude, ref_p.longitude):
            folium.PolyLine(
                locations=[(snap_p.latitude, snap_p.longitude), (ref_p.latitude, ref_p.longitude)],
                color="#FFEB3B",
                weight=3,
                opacity=0.9,
            ).add_to(inspection_layer)

        # Raw point
        folium.CircleMarker(
            location=[raw_p.latitude, raw_p.longitude],
            radius=4,
            color="#9E9E9E",
            weight=1,
            fill=True,
            fill_color="#BDBDBD",
            fill_opacity=0.6,
            tooltip=f"CP{idx} (Raw)",
        ).add_to(inspection_layer)

        # Snapped point
        folium.CircleMarker(
            location=[snap_p.latitude, snap_p.longitude],
            radius=5,
            color="#FFFFFF",
            weight=1,
            fill=True,
            fill_color="#FF9800",
            fill_opacity=0.7,
            tooltip=f"CP{idx} (Pre-refinement Snap)",
        ).add_to(inspection_layer)

        # Final Refined point
        folium.CircleMarker(
            location=[ref_p.latitude, ref_p.longitude],
            radius=7,
            color="#FFFFFF",
            weight=2,
            fill=True,
            fill_color=color,
            fill_opacity=1.0,
            tooltip=f"CP{idx} (Final Refined)",
        ).add_to(inspection_layer)

    inspection_layer.add_to(m)

    LayerControl(collapsed=False).add_to(m)
    m.save(output_html)
    print(f"🗺 Pipeline visualization map saved to: {os.path.abspath(output_html)}")


def main():
    center = GeoPoint(latitude=50.45, longitude=23.423)
    # center = GeoPoint(latitude=52.23, longitude=21.00)
    radius_meters = 5000.0
    target_distance_meters = 2.0 * radius_meters / 0.7

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
    print(f"   -> Snapped waypoint node IDs: {snapped_node_ids}")

    print("4. Simplifying graph while protecting snapped transit nodes...")
    converter = GraphConverter(original_map=raw_graph)
    simple_graph = converter.convert_graph_to_algorithm(protected_nodes=set(snapped_node_ids))
    print(f"   -> Node reduction: raw={len(raw_graph.nodes)} -> simplified={len(simple_graph.nodes)}")

    print("5. Slicing graph into stage corridor subgraphs (wide envelopes)...")
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
    print(f"   -> Final refined waypoint node IDs: {refined_node_ids}")

    # Reconstruct refined GeoPoints for inspection & visualization
    refined_checkpoints: list[GeoPoint] = []
    for node_id in refined_node_ids[1:]:
        node_data = simple_graph.nodes[node_id]
        lat = node_data.get("y", node_data.get("lat"))
        lon = node_data.get("x", node_data.get("lon"))
        refined_checkpoints.append(GeoPoint(latitude=lat, longitude=lon))

    for i, sg in enumerate(stage_subgraphs, start=1):
        print(f"   -> Stage {i}: {len(sg.nodes)} nodes, {len(sg.edges)} edges")

    output_html = "test_pipeline_result.html"
    plot_pipeline_map(
        converter=converter,
        raw_center=center,
        snapped_center=snapped_center,
        raw_checkpoints=raw_checkpoints,
        snapped_checkpoints=snapped_checkpoints,
        refined_checkpoints=refined_checkpoints,
        stage_subgraphs=stage_subgraphs,
        output_html=output_html,
    )


if __name__ == "__main__":
    main()
