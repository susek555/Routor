import os

import folium
from folium import LayerControl
from src.database.geo_point import GeoPoint
from src.generate_routes.graph_builder.graph_builder import GraphBuilder
from src.generate_routes.graph_builder.graph_converter import GraphConverter

ESRI_SATELLITE = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
ESRI_ATTR = "Esri World Imagery"


def plot_comparison_map(orig_graph, simplified_graph, center: GeoPoint, output_html: str):
    m = folium.Map(
        location=[center.latitude, center.longitude],
        zoom_start=16,
        tiles=ESRI_SATELLITE,
        attr=ESRI_ATTR,
    )

    # 1. Original dense graph (cyan) - hidden by default
    orig_layer = folium.FeatureGroup(name="1. Original Graph (All curvature nodes)", show=False)
    for u, v, _ in orig_graph.edges(data=True):
        u_node = orig_graph.nodes[u]
        v_node = orig_graph.nodes[v]
        coords = [(u_node["y"], u_node["x"]), (v_node["y"], v_node["x"])]
        folium.PolyLine(locations=coords, color="#00FFFF", weight=2, opacity=0.7).add_to(orig_layer)

    for n, data in orig_graph.nodes(data=True):
        folium.CircleMarker(
            location=[data["y"], data["x"]],
            radius=2,
            color="#00FFFF",
            fill=True,
            tooltip=f"Orig Node ID: {n}",
        ).add_to(orig_layer)
    orig_layer.add_to(m)

    # 2. Simplified graph (red) - markers only at junctions, lines preserve road curves
    simple_layer = folium.FeatureGroup(name="2. Algorithm Graph (Junctions only)", show=True)

    for u, v, data in simplified_graph.edges(data=True):
        coords = data.get("geometry_points", [])
        if not coords:
            u_node = simplified_graph.nodes[u]
            v_node = simplified_graph.nodes[v]
            coords = [(u_node["y"], u_node["x"]), (v_node["y"], v_node["x"])]

        folium.PolyLine(
            locations=coords,
            color="#FF3333",
            weight=4,
            opacity=0.9,
            tooltip=f"Segment {u} -> {v} | Length: {data.get('length', 0):.1f}m | Curve points: {len(coords)}",
        ).add_to(simple_layer)

    # Nodes represent intersections and dead-ends only
    for n, data in simplified_graph.nodes(data=True):
        folium.CircleMarker(
            location=[data["y"], data["x"]],
            radius=5,
            color="#FFFFFF",
            weight=2,
            fill=True,
            fill_color="#FF0000",
            fill_opacity=1.0,
            tooltip=f"Junction ID: {n}",
        ).add_to(simple_layer)
    simple_layer.add_to(m)

    # Starting query point marker
    folium.Marker(
        [center.latitude, center.longitude],
        popup=f"Start Query Point: ({center.latitude}, {center.longitude})",
        icon=folium.Icon(color="green", icon="play"),
    ).add_to(m)

    LayerControl(collapsed=False).add_to(m)
    m.save(output_html)
    print(f"🗺️️ Comparison map saved to: {os.path.abspath(output_html)}")


def main():
    center = GeoPoint(latitude=50.45, longitude=23.423)
    # center = GeoPoint(latitude=52.23, longitude=21.00)
    radius_meters = 2500.0

    print(f"Fetching graph around ({center.latitude}, {center.longitude})...")
    raw_graph = GraphBuilder.build_graph(center, radius_meters)

    if raw_graph is None or len(raw_graph.nodes) == 0:
        print("❌ Graph is empty or failed to load.")
        return

    converter = GraphConverter(original_map=raw_graph)

    print("Simplifying graph for algorithm...")
    simple_graph = converter.convert_graph_to_algorithm()

    # Simplification statistics
    orig_nodes = len(raw_graph.nodes)
    simple_nodes = len(simple_graph.nodes)
    node_red = (1 - simple_nodes / orig_nodes) * 100

    orig_edges = len(raw_graph.edges)
    simple_edges = len(simple_graph.edges)
    edge_red = (1 - simple_edges / orig_edges) * 100

    print("\n" + "=" * 55)
    print("📈 GRAPH SIMPLIFICATION RESULTS:")
    print("=" * 55)
    print(f"Nodes:     {orig_nodes:>6}  ->  {simple_nodes:>6}  (-{node_red:.1f}%)")
    print(f"Edges:     {orig_edges:>6}  ->  {simple_edges:>6}  (-{edge_red:.1f}%)")
    print("=" * 55 + "\n")

    output_html = "test_graph_simplification.html"
    plot_comparison_map(raw_graph, simple_graph, center, output_html)


if __name__ == "__main__":
    main()
