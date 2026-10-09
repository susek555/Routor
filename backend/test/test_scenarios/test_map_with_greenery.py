import os
from collections import Counter

import branca.colormap as cm
import folium
import numpy as np
import osmnx as ox
from shapely.geometry import LineString
from src.database.geo_point import GeoPoint
from src.generate_routes.graph_builder.graph_builder import GraphBuilder

ox.settings.use_cache = False


def print_graph_summary(graph, center_node_id: int):
    print("\n" + "=" * 60)
    print("📊 GRAPH ATTRIBUTES SUMMARY")
    print("=" * 60)

    # 1. Elevation stats
    elevations = [data.get("elevation", 0.0) for _, data in graph.nodes(data=True) if "elevation" in data]
    if elevations:
        print("🏔️ Elevation (m a.s.l.):")
        print(f"   - Min:  {min(elevations):.1f} m")
        print(f"   - Max:  {max(elevations):.1f} m")
        print(f"   - Mean: {np.mean(elevations):.1f} m")
        print(f"   - Span: {max(elevations) - min(elevations):.1f} m")
    else:
        print("⚠️ No 'elevation' attribute found in nodes.")

    # 2. Edge metrics & slope stats
    lengths = []
    grades = []
    surfaces = []
    highways = []
    landuses = []
    leisures = []

    for _, _, data in graph.edges(data=True):
        if "length" in data:
            lengths.append(data["length"])
        if "grade" in data:
            grades.append(data["grade"] * 100.0)
        if "surface" in data and data["surface"] is not None:
            surfaces.append(data["surface"])
        if "highway" in data and data["highway"] is not None:
            highways.append(data["highway"])
        if "landuse" in data and data["landuse"] is not None:
            landuses.append(data["landuse"])
        if "leisure" in data and data["leisure"] is not None:
            leisures.append(data["leisure"])

    total_km = sum(lengths) / 1000.0 if lengths else 0.0
    print("\n🛣️ Network Metrics:")
    print(f"   - Total segment length: {total_km:.2f} km")
    print(f"   - Total nodes: {len(graph.nodes)}")
    print(f"   - Total directed edges: {len(graph.edges)}")

    if grades:
        print("\n📐 Slope / Grade (%):")
        print(f"   - Max uphill:   {max(grades):+.2f}%")
        print(f"   - Max downhill: {min(grades):+.2f}%")
        print(f"   - Mean abs grade: {np.mean(np.abs(grades)):.2f}%")

    # 3. Categorical breakdown
    if surfaces:
        print("\n🧱 Surface Distribution (Top 5):")
        for surf, count in Counter(surfaces).most_common(5):
            print(f"   - {surf:<15}: {count} edges ({count / len(surfaces) * 100:.1f}%)")

    if highways:
        print("\n🚶 Highway Types (Top 5):")
        for hw, count in Counter(highways).most_common(5):
            print(f"   - {hw:<15}: {count} edges ({count / len(highways) * 100:.1f}%)")

    if landuses:
        print("\n🌲 Landuse Distribution:")
        for lu, count in Counter(landuses).most_common(5):
            print(f"   - {lu:<15}: {count} edges ({count / len(graph.edges) * 100:.2f}% of all edges)")
    else:
        print("\n🌲 Landuse: Brak bezpośrednich tagów landuse na drogach.")

    if leisures:
        print("\n⚽ Leisure Distribution:")
        for lei, count in Counter(leisures).most_common(5):
            print(f"   - {lei:<15}: {count} edges ({count / len(graph.edges) * 100:.2f}% of all edges)")

    # 4. Nearest Node Details
    print("\n" + "=" * 60)
    print(f"📍 CENTER / CLOSEST NODE DETAILS (Node ID: {center_node_id})")
    print("=" * 60)
    center_data = graph.nodes[center_node_id]
    for key, val in center_data.items():
        print(f"   - Node [{key}]: {val}")

    out_edges = list(graph.out_edges(center_node_id, data=True))
    print(f"\n   Connected Outgoing Edges ({len(out_edges)}):")
    for _, target, edge_data in out_edges:
        name = edge_data.get("name", "Unnamed")
        hw = edge_data.get("highway", "unknown")
        surf = edge_data.get("surface", "unknown")
        landuse = edge_data.get("landuse", "none")
        leisure = edge_data.get("leisure", "none")
        grade = edge_data.get("grade", 0.0) * 100.0
        elev_chg = edge_data.get("elevation_change", 0.0)
        length = edge_data.get("length", 0.0)
        print(
            f"   -> to Node {target} | {name} ({hw}, {surf}) | landuse: {landuse}, leisure: {leisure} | "
            f"len: {length:.1f}m | slope: {grade:+.1f}% | Δh: {elev_chg:+.1f}m"
        )
    print("=" * 60 + "\n")


def build_colored_elevation_map(graph, center: GeoPoint, output_html: str):
    elevations = [data.get("elevation", 0.0) for _, data in graph.nodes(data=True) if "elevation" in data]
    min_elev = min(elevations) if elevations else 0.0
    max_elev = max(elevations) if elevations else 1.0

    if min_elev == max_elev:
        max_elev += 1.0

    colormap = cm.LinearColormap(
        colors=["#0000ff", "#00ffff", "#00ff00", "#ffff00", "#ff0000"],
        vmin=min_elev,
        vmax=max_elev,
        caption="Elevation a.s.l. (meters)",
    )

    m = folium.Map(
        location=[center.latitude, center.longitude],
        zoom_start=14,
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery",
    )

    for u, v, data in graph.edges(data=True):
        u_elev = graph.nodes[u].get("elevation", min_elev)
        v_elev = graph.nodes[v].get("elevation", min_elev)
        avg_elev = (u_elev + v_elev) / 2.0
        edge_color = colormap(avg_elev)

        if "geometry" in data and isinstance(data["geometry"], LineString):
            coords = [(lat, lon) for lon, lat in data["geometry"].coords]
        else:
            u_node = graph.nodes[u]
            v_node = graph.nodes[v]
            coords = [(u_node["y"], u_node["x"]), (v_node["y"], v_node["x"])]

        landuse_tag = data.get("landuse")
        leisure_tag = data.get("leisure")

        tooltip_lines = [
            f"<b>{data.get('name', 'Path')}</b>",
            f"Highway: {data.get('highway', 'N/A')}",
            f"Surface: {data.get('surface', 'N/A')}",
        ]
        if landuse_tag:
            tooltip_lines.append(f"Landuse: {landuse_tag}")
        if leisure_tag:
            tooltip_lines.append(f"Leisure: {leisure_tag}")

        tooltip_lines.extend([
            f"Length: {data.get('length', 0.0):.1f} m",
            f"Avg Elevation: {avg_elev:.1f} m",
            f"Slope (Grade): {data.get('grade', 0.0) * 100:.1f}%",
            f"Elevation Change: {data.get('elevation_change', 0.0):+.1f} m",
        ])

        folium.PolyLine(
            locations=coords,
            color=edge_color,
            weight=3.5,
            opacity=0.85,
            tooltip="<br>".join(tooltip_lines),
        ).add_to(m)

    folium.Marker(
        [center.latitude, center.longitude],
        popup=f"Center Query: ({center.latitude}, {center.longitude})",
        icon=folium.Icon(color="red", icon="flag"),
    ).add_to(m)

    colormap.add_to(m)
    m.save(output_html)
    print(f"✅ Interactive elevation map saved to: {os.path.abspath(output_html)}")


def main():
    center = GeoPoint(latitude=50.45, longitude=23.435)
    radius_meters = 4000.0

    print(f"Building graph for point ({center.latitude}, {center.longitude}) with radius {radius_meters}m...")
    graph = GraphBuilder.build_graph(center, radius_meters)

    if graph is None or len(graph.nodes) == 0:
        print("❌ Graph is empty or failed to build.")
        return

    closest_node_id = ox.distance.nearest_nodes(graph, X=center.longitude, Y=center.latitude)

    print_graph_summary(graph, closest_node_id)

    output_html = "output_elevation_map.html"
    build_colored_elevation_map(graph, center, output_html)


if __name__ == "__main__":
    main()
