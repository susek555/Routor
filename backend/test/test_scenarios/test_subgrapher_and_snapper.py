import os

import folium
from folium import LayerControl
from src.database.geo_point import GeoPoint
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
    simplified_graph: Map,
    raw_center: GeoPoint,
    snapped_center: GeoPoint,
    raw_checkpoints: list[GeoPoint],
    snapped_checkpoints: list[GeoPoint],
    stage_subgraphs: list[Map],
    output_html: str,
):
    """Generates an interactive Folium map illustrating the full pipeline stages."""
    m = folium.Map(
        location=[snapped_center.latitude, snapped_center.longitude],
        zoom_start=14,
        tiles=ESRI_SATELLITE,
        attr=ESRI_ATTR,
    )

    # 1. Full contracted graph background layer
    base_layer = folium.FeatureGroup(name="1. Simplified Graph (All)", show=False)
    for u, v in simplified_graph.edges():
        geometry = converter.reconstruct_route_from_node_ids([u, v])
        coords = [(p.latitude, p.longitude) for p in geometry]
        folium.PolyLine(locations=coords, color="#FFFFFF", weight=1, opacity=0.3).add_to(base_layer)
    base_layer.add_to(m)

    # 2. Stage subgraphs with exact road curve reconstruction
    for idx, stage_graph in enumerate(stage_subgraphs, start=1):
        color = STAGE_PALETTE[(idx - 1) % len(STAGE_PALETTE)]
        stage_layer = folium.FeatureGroup(
            name=f"2. Stage {idx} Subgraph ({len(stage_graph.nodes)} nodes, {len(stage_graph.edges)} edges)",
            show=True,
        )

        for u, v in stage_graph.edges():
            geometry = converter.reconstruct_route_from_node_ids([u, v])
            coords = [(p.latitude, p.longitude) for p in geometry]
            folium.PolyLine(locations=coords, color=color, weight=3, opacity=0.85).add_to(stage_layer)

        for n, data in stage_graph.nodes(data=True):
            folium.CircleMarker(
                location=[data["y"], data["x"]],
                radius=3,
                color=color,
                weight=1,
                fill=True,
                fill_color=color,
                fill_opacity=0.9,
                tooltip=f"Stage {idx} | Node ID: {n}",
            ).add_to(stage_layer)

        stage_layer.add_to(m)

    # 3. Snapping inspection layer (Raw vs Snapped)
    snapping_layer = folium.FeatureGroup(name="3. Snapping Inspection", show=True)

    # Start displacement vector
    folium.PolyLine(
        locations=[
            (raw_center.latitude, raw_center.longitude),
            (snapped_center.latitude, snapped_center.longitude),
        ],
        color="#FFFFFF",
        weight=2,
        dash_array="2, 6",
    ).add_to(snapping_layer)

    folium.Marker(
        [snapped_center.latitude, snapped_center.longitude],
        popup=f"Start: ({snapped_center.latitude:.5f}, {snapped_center.longitude:.5f})",
        icon=folium.Icon(color="green", icon="play"),
    ).add_to(snapping_layer)

    # Checkpoint displacement vectors and markers
    for raw_p, snap_p, idx in zip(
        raw_checkpoints, snapped_checkpoints, range(1, len(raw_checkpoints) + 1), strict=False
    ):
        color = STAGE_PALETTE[(idx - 1) % len(STAGE_PALETTE)]
        folium.PolyLine(
            locations=[(raw_p.latitude, raw_p.longitude), (snap_p.latitude, snap_p.longitude)],
            color="#FFFFFF",
            weight=2,
            dash_array="2, 6",
        ).add_to(snapping_layer)

        # Raw generated point (before snapping)
        folium.CircleMarker(
            location=[raw_p.latitude, raw_p.longitude],
            radius=4,
            color="#9E9E9E",
            weight=1,
            fill=True,
            fill_color="#BDBDBD",
            fill_opacity=0.7,
            tooltip=f"CP{idx} (Raw)",
        ).add_to(snapping_layer)

        # Snapped and protected node
        folium.CircleMarker(
            location=[snap_p.latitude, snap_p.longitude],
            radius=7,
            color="#FFFFFF",
            weight=2,
            fill=True,
            fill_color=color,
            fill_opacity=1.0,
            tooltip=f"CP{idx} (Snapped & Protected)",
        ).add_to(snapping_layer)

    snapping_layer.add_to(m)

    LayerControl(collapsed=False).add_to(m)
    m.save(output_html)
    print(f"🗺 Pipeline visualization map saved to: {os.path.abspath(output_html)}")


def main():
    center = GeoPoint(latitude=50.45, longitude=23.423)
    radius_meters = 2500.0

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
    print(f"   -> Protected waypoint nodes: {snapped_node_ids}")

    print("4. Simplifying graph while protecting snapped transit nodes...")
    converter = GraphConverter(original_map=raw_graph)
    simple_graph = converter.convert_graph_to_algorithm(protected_nodes=set(snapped_node_ids))
    print(f"   -> Node reduction: raw={len(raw_graph.nodes)} -> simplified={len(simple_graph.nodes)}")

    print("5. Slicing graph into stage corridor subgraphs...")
    points_chain = [snapped_center] + snapped_checkpoints
    stage_subgraphs = Subgrapher.extract_subgraphs(
        map=simple_graph,
        checkpoints=points_chain,
        checkpoint_node_ids=snapped_node_ids,
        slack_ratio=0.30,
        min_slack_meters=150.0,
    )

    for i, sg in enumerate(stage_subgraphs, start=1):
        print(f"   -> Stage {i}: {len(sg.nodes)} nodes, {len(sg.edges)} edges")

    output_html = "test_pipeline_result.html"
    plot_pipeline_map(
        converter=converter,
        simplified_graph=simple_graph,
        raw_center=center,
        snapped_center=snapped_center,
        raw_checkpoints=raw_checkpoints,
        snapped_checkpoints=snapped_checkpoints,
        stage_subgraphs=stage_subgraphs,
        output_html=output_html,
    )


if __name__ == "__main__":
    main()
