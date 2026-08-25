import os
import networkx as nx
import osmnx as ox
from scipy.spatial import cKDTree
import numpy as np

from src.database.geo_point import GeoPoint
from src.generate_routes.graph_builder.graph_builder import GraphBuilder
from src.generate_routes.graph_builder.tile_loader import TileLoader

ox.settings.use_cache = False


def collapse_multilane_intersections(G: nx.MultiDiGraph, tolerance_meters: float = 15.0) -> nx.MultiDiGraph:
    """
    Scala węzły dróg wielopasmowych i złożonych skrzyżowań leżące bliżej niż `tolerance_meters`.
    Nie używa zabugowanego rebuild_graph z OSMnx.
    """
    # 1. Rzutowanie grafu na układ metryczny UTM
    g_proj = ox.project_graph(G)

    nodes = list(g_proj.nodes(data=True))
    node_ids = [n[0] for n in nodes]
    coords = np.array([[n[1]["x"], n[1]["y"]] for n in nodes])

    # 2. Budowa drzewa KD do szybkiego wyszukiwania sąsiadów w promieniu tolerance_meters
    tree = cKDTree(coords)
    clusters = tree.query_ball_tree(tree, r=tolerance_meters)

    # 3. Wyznaczenie mapowania stary_node -> reprezentant_klastra
    visited = set()
    node_mapping = {}

    for idx, cluster in enumerate(clusters):
        if idx in visited:
            continue
        # Reprezentantem staje się pierwszy napotkany węzeł w grupie
        rep_id = node_ids[idx]
        for member_idx in cluster:
            if member_idx not in visited:
                visited.add(member_idx)
                node_mapping[node_ids[member_idx]] = rep_id

    # 4. Budowa nowego, uproszczonego grafu
    g_collapsed = nx.MultiDiGraph()
    g_collapsed.graph = g_proj.graph.copy()

    # Przepisanie węzłów-reprezentantów
    for n, data in g_proj.nodes(data=True):
        if n in node_mapping and node_mapping[n] == n:
            g_collapsed.add_node(n, **data)

    # Przepisanie krawędzi z uwzględnieniem scalonych punktów
    for u, v, k, data in g_proj.edges(keys=True, data=True):
        new_u = node_mapping.get(u, u)
        new_v = node_mapping.get(v, v)

        # Ignorujemy pętle własne (krawędzie wewnątrz tego samego skrzyżowania/pasa)
        if new_u != new_v:
            # Sprawdzamy czy taka krawędź już istnieje, aby nie powielać równoległych pasów
            if not g_collapsed.has_edge(new_u, new_v):
                g_collapsed.add_edge(new_u, new_v, **data)

    # 5. Usunięcie odizolowanych punktów
    g_collapsed.remove_nodes_from(list(nx.isolates(g_collapsed)))

    # 6. Powrót do WGS84
    return ox.project_graph(g_collapsed, to_crs="epsg:4326")


def main():
    center = GeoPoint(latitude=52.2297, longitude=21.0122)
    radius_meters = 1000.0

    print(f"Szukam kafelków w: {os.path.abspath(TileLoader.TILES_DIR)}")

    # 1. Baza
    g_base = GraphBuilder.build_graph(center, radius_meters)
    if not g_base or len(g_base.nodes) == 0:
        print("[BŁĄD] Nie udało się zbudować grafu.")
        return

    print(f"\n[1] Baza (surowy): {len(g_base.nodes)} węzłów, {len(g_base.edges)} krawędzi")

    # 2. Redukcja wielopasmowości (promień scalania 15 metrów)
    g_reduced = collapse_multilane_intersections(g_base, tolerance_meters=15.0)
    print(f"[2] Po redukcji wielopasmowości (15m): {len(g_reduced.nodes)} węzłów, {len(g_reduced.edges)} krawędzi")

    # 3. Zmiękczenie topologiczne OSMnx po zredukowaniu pasów
    g_reduced.graph["simplified"] = False
    g_final = ox.simplify_graph(g_reduced)
    print(f"[3] Po końcowym simplify_graph: {len(g_final.nodes)} węzłów, {len(g_final.edges)} krawędzi")

    # Zapis obrazu
    output_png = "collapsed_multilane_map.png"
    ox.plot_graph(
        g_final,
        node_size=10,
        node_color="crimson",
        edge_color="#444444",
        edge_linewidth=1.0,
        filepath=output_png,
        save=True,
        show=False,
        close=True,
    )
    print(f"\n[SUKCES] Zapisano podgląd do: {os.path.abspath(output_png)}")


if __name__ == "__main__":
    main()
