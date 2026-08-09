import time

import osmnx as ox
from src.database.geo_point import GeoPoint
from src.generate_routes.graph_builder.graph_builder import GraphBuilder
from src.generate_routes.graph_builder.tile_cache_manager import TileCacheManager

# docker exec -it routor_api uv run python -m test.docker_scenarios.test_cache_flow


def run_test():
    # Przykładowy punkt (np. centrum Warszawy)
    center = GeoPoint(latitude=52.2297, longitude=21.0118)
    radius = 2000  # 3 km

    print("\n=== PRÓBA 1: CACHE MISS (API -> L2 -> L1) ===")
    start = time.time()
    graph1 = GraphBuilder.build_graph(center, radius)
    print(f"⏱️ Czas: {time.time() - start:.2f} s | Węzły: {len(graph1.nodes)}")

    print("\n💾 Zapisywanie grafu do pliku PNG...")
    fig, ax = ox.plot_graph(
        graph1,
        node_size=0,
        edge_color="#22d3ee",
        edge_linewidth=0.5,
        bgcolor="#111827",
        show=False,
        close=False,
    )
    fig.savefig("/app/mapa.png", dpi=300, bbox_inches="tight")
    print("✅ Zapisano jako mapa.png w głównym folderze kontenera!")

    print("\n=== PRÓBA 2: L1 HIT (Redis RAM) ===")
    start = time.time()
    graph2 = GraphBuilder.build_graph(center, radius)
    print(f"⏱️ Czas: {time.time() - start:.2f} s | Węzły: {len(graph2.nodes)}")

    print("\n=== PRÓBA 3: L2 HIT (Dysk -> Promocja do L1) ===")
    # Symulujemy wyrzucenie danych z Redisa (np. przez brak RAMu)
    print("🧹 Czyszczenie Redisa (symulacja utraty RAM)...")
    TileCacheManager._redis_client.flushdb()

    start = time.time()
    graph3 = GraphBuilder.build_graph(center, radius)
    print(f"⏱️ Czas: {time.time() - start:.2f} s | Węzły: {len(graph3.nodes)}")


if __name__ == "__main__":
    run_test()
