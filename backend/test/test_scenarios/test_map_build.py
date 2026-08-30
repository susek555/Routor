import os

import contextily as cx
import folium
import osmnx as ox
from src.database.geo_point import GeoPoint
from src.generate_routes.graph_builder.graph_builder import GraphBuilder
from src.generate_routes.graph_builder.tile_loader import TileLoader

ox.settings.use_cache = False


def main():
    # center = GeoPoint(latitude=52.2297, longitude=21.0122)
    center = GeoPoint(latitude=50.45, longitude=23.435)
    # radius_meters = 1000.0
    radius_meters = 5000.0

    print(f"Szukam kafelków w katalogu: {os.path.abspath(TileLoader.TILES_DIR)}")
    print(f"Budowanie grafu dla punktu ({center.latitude}, {center.longitude}) o promieniu {radius_meters}m...")

    graph = GraphBuilder.build_graph(center, radius_meters)

    if graph is None or len(graph.nodes) == 0:
        print("\n[BŁĄD] Nie udało się zbudować grafu.")
        return

    print("\n[SUKCES] Graf zbudowany pomyślnie!")
    print(f"Liczba węzłów (nodes): {len(graph.nodes)}")
    print(f"Liczba krawędzi (edges): {len(graph.edges)}")

    # 1. INTERAKTYWNY WIDOK SATELITARNY (HTML / Folium)
    try:
        output_html = "output_satellite_map.html"

        # Tworzymy mapę Folium ze zdefiniowanym podkładem satelitarnym Esri
        m = folium.Map(
            location=[center.latitude, center.longitude],
            zoom_start=15,
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri World Imagery",
        )

        # Dodajemy krawędzie i węzły grafu
        folium_map = ox.folium.plot_graph_folium(
            graph,
            folium_map=m,
            color="#00ffff",  # Jasny cyjan doskonale widoczny na zdjęciach satelitarnych
            weight=2,
            opacity=0.8,
        )

        folium_map.save(output_html)
        print(f"[SUKCES] Zapisano interaktywną mapę satelitarną: {os.path.abspath(output_html)}")
    except Exception as e:
        print(f"Błąd generowania mapy HTML: {e}")

    # 2. STATYCZNY ZAPIS Z PODKŁADEM MAPOWYM (PNG + Contextily)
    try:
        output_png = "output_basemap.png"
        print(f"\nGenerowanie PNG z podkładem kafelkowym...")

        # Rzutujemy do Web Mercator (EPSG:3857) – wymagane dla podkładów kafelkowych
        g_mercator = ox.project_graph(graph, to_crs="epsg:3857")

        fig, ax = ox.plot_graph(
            g_mercator,
            node_size=8,
            node_color="crimson",
            edge_color="#00ffff",
            edge_linewidth=1.2,
            show=False,
            close=False,
        )

        # Dodanie podkładu satelitarnego (Esri World Imagery)
        cx.add_basemap(
            ax,
            source=cx.providers.Esri.WorldImagery,
            crs=g_mercator.graph["crs"],
        )

        fig.savefig(output_png, dpi=300, bbox_inches="tight")
        print(f"[SUKCES] Zapisano statyczny podgląd z satelitą: {os.path.abspath(output_png)}")
    except Exception as e:
        print(f"Pominięto generowanie statycznego podkładu PNG (brak contextily?): {e}")


if __name__ == "__main__":
    main()
