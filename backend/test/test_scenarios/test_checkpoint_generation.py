import os

import folium
from folium import LayerControl
from src.database.geo_point import GeoPoint
from src.generate_routes.algorithm.checkpoints_generator import CheckpointsGenerator
from src.generate_routes.graph_builder.graph_builder import GraphBuilder
from src.generate_routes.graph_builder.graph_converter import GraphConverter

ESRI_SATELLITE = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
ESRI_ATTR = "Esri World Imagery"

# Kolory dla kolejnych zestawów checkpointów
CHECKPOINT_PALETTE = ["#FF0055", "#00E5FF", "#FFB300", "#76FF03", "#D500F9"]


def plot_checkpoints_map(
    simplified_graph,
    center: GeoPoint,
    checkpoint_variants: list[list[GeoPoint]],
    output_html: str,
):
    m = folium.Map(
        location=[center.latitude, center.longitude],
        zoom_start=14,
        tiles=ESRI_SATELLITE,
        attr=ESRI_ATTR,
    )

    # 1. Warstwa uproszczonego grafu (czerwone linie i skrzyżowania)
    graph_layer = folium.FeatureGroup(name="Simplified Graph", show=True)

    for u, v, data in simplified_graph.edges(data=True):
        coords = data.get("geometry_points", [])
        if not coords:
            u_node = simplified_graph.nodes[u]
            v_node = simplified_graph.nodes[v]
            coords = [(u_node["y"], u_node["x"]), (v_node["y"], v_node["x"])]

        folium.PolyLine(
            locations=coords,
            color="#FF3333",
            weight=2,
            opacity=0.6,
        ).add_to(graph_layer)

    for n, data in simplified_graph.nodes(data=True):
        folium.CircleMarker(
            location=[data["y"], data["x"]],
            radius=3,
            color="#FFFFFF",
            weight=1,
            fill=True,
            fill_color="#FF0000",
            fill_opacity=0.8,
            tooltip=f"Junction ID: {n}",
        ).add_to(graph_layer)
    graph_layer.add_to(m)

    # 2. Punkt startowy
    folium.Marker(
        [center.latitude, center.longitude],
        popup=f"Start: ({center.latitude}, {center.longitude})",
        icon=folium.Icon(color="green", icon="play"),
    ).add_to(m)

    # 3. Nakładanie wariantów checkpointów (jako oddzielne warstwy do przełączania)
    for idx, checkpoints in enumerate(checkpoint_variants, start=1):
        color = CHECKPOINT_PALETTE[(idx - 1) % len(CHECKPOINT_PALETTE)]
        # Domyślnie pokazujemy tylko wariant 1, reszta schowana
        variant_layer = folium.FeatureGroup(name=f"Variant #{idx}", show=(idx == 1))

        # Szkic pętli: Start -> WP1 -> WP2 -> WP3 -> Start
        loop_coords = [
            (center.latitude, center.longitude),
            *[(p.latitude, p.longitude) for p in checkpoints],
            (center.latitude, center.longitude),
        ]

        folium.PolyLine(
            locations=loop_coords,
            color=color,
            weight=3,
            dash_array="6, 8",
            opacity=0.9,
            tooltip=f"Variant #{idx} skeleton loop",
        ).add_to(variant_layer)

        # Markery kolejnych punktów tranzytowych
        for wp_idx, wp in enumerate(checkpoints, start=1):
            folium.CircleMarker(
                location=[wp.latitude, wp.longitude],
                radius=7,
                color="#FFFFFF",
                weight=2,
                fill=True,
                fill_color=color,
                fill_opacity=1.0,
                tooltip=f"V{idx} - Waypoint {wp_idx}",
                popup=f"V{idx} WP{wp_idx}: ({wp.latitude:.5f}, {wp.longitude:.5f})",
            ).add_to(variant_layer)

        variant_layer.add_to(m)

    LayerControl(collapsed=False).add_to(m)
    m.save(output_html)
    print(f"🗺 Map with checkpoints saved to: {os.path.abspath(output_html)}")


def main():
    center = GeoPoint(latitude=50.45, longitude=23.423)
    radius_meters = 2500.0
    variants_count = 5

    print(f"Fetching graph around ({center.latitude}, {center.longitude})...")
    raw_graph = GraphBuilder.build_graph(center, radius_meters)

    if raw_graph is None or len(raw_graph.nodes) == 0:
        print("❌ Graph is empty or failed to load.")
        return

    print("Simplifying graph...")
    converter = GraphConverter(original_map=raw_graph)
    simple_graph = converter.convert_graph_to_algorithm()

    print(f"Generating {variants_count} checkpoint variants...")
    variants = [
        CheckpointsGenerator.generate_checkpoints(center=center, radius=radius_meters) for _ in range(variants_count)
    ]

    output_html = "test_checkpoints_variants.html"
    plot_checkpoints_map(simple_graph, center, variants, output_html)


if __name__ == "__main__":
    main()
