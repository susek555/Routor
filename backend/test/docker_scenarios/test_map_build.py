import os

import osmnx as ox
from src.database.geo_point import GeoPoint
from src.generate_routes.graph_builder.graph_builder import GraphBuilder
from src.generate_routes.graph_builder.tile_loader import TileLoader

ox.settings.use_cache = False


def main():
    center = GeoPoint(latitude=52.2297, longitude=21.0122)
    radius_meters = 1000.0

    print(f"Szukam kafelków w katalogu: {os.path.abspath(TileLoader.TILES_DIR)}")
    print(f"Budowanie grafu dla punktu ({center.latitude}, {center.longitude}) o promieniu {radius_meters}m...")

    graph = GraphBuilder.build_graph(center, radius_meters)

    if graph is None or len(graph.nodes) == 0:
        print("\n[BŁĄD] Nie udało się zbudować grafu.")
        print("Upewnij się, że:")
        print(f"1. W '{TileLoader.TILES_DIR}' znajdują się odpowiednie pliki .pkl dla tych współrzędnych.")
        print("2. Identyfikatory w nazwach plików odpowiadają formatowi pointer.id.")
        return

    print("\n[SUKCES] Graf zbudowany pomyślnie z plików na dysku!")
    print(f"Liczba węzłów (nodes): {len(graph.nodes)}")
    print(f"Liczba krawędzi (edges): {len(graph.edges)}")

    output_png = "output_map.png"
    print(f"\nZapisywanie mapy do pliku {output_png}...")
    fig, ax = ox.plot_graph(
        graph,
        node_size=5,
        node_color="crimson",
        edge_color="#555555",
        edge_linewidth=0.8,
        filepath=output_png,
        save=True,
        show=False,
        close=True,
    )
    print(f"[SUKCES] Zapisano podgląd PNG: {os.path.abspath(output_png)}")

    try:
        output_html = "output_map.html"
        folium_map = ox.plot_graph_folium(graph, color="#3388ff", weight=2)
        folium_map.save(output_html)
        print(f"[SUKCES] Zapisano interaktywną mapę HTML: {os.path.abspath(output_html)}")
    except Exception as e:
        print(f"Pominięto generowanie pliku HTML: {e}")


if __name__ == "__main__":
    main()
