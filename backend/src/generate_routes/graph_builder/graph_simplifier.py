import networkx as nx
import numpy as np
import osmnx as ox
from scipy.spatial import cKDTree

from src.generate_routes.graph_builder.data.map import Map


class GraphSimplifier:
    DEFAULT_TOLERANCE_METERS = 15.0

    @classmethod
    def simplify(cls, graph: Map, tolerance_meters: float = DEFAULT_TOLERANCE_METERS) -> Map:
        """Redukuje wielopasmowe arterie i wykonuje finalne uproszczenie topologiczne."""
        if graph is None or len(graph.nodes) == 0:
            return graph

        # 1. Rzutowanie do metrycznego układu UTM
        g_proj = ox.project_graph(graph)

        nodes = list(g_proj.nodes(data=True))
        node_ids = [n[0] for n in nodes]
        coords = np.array([[n[1]["x"], n[1]["y"]] for n in nodes])

        # 2. Drzewo KD do klastrowania węzłów w zadanym promieniu
        tree = cKDTree(coords)
        clusters = tree.query_ball_tree(tree, r=tolerance_meters)

        visited = set()
        node_mapping = {}

        for idx, cluster in enumerate(clusters):
            if idx in visited:
                continue
            rep_id = node_ids[idx]
            for member_idx in cluster:
                if member_idx not in visited:
                    visited.add(member_idx)
                    node_mapping[node_ids[member_idx]] = rep_id

        # 3. Budowa grafu ze zredukowanymi węzłami
        g_collapsed = nx.MultiDiGraph()
        g_collapsed.graph = g_proj.graph.copy()

        for n, data in g_proj.nodes(data=True):
            if n in node_mapping and node_mapping[n] == n:
                g_collapsed.add_node(n, **data)

        for u, v, _, data in g_proj.edges(keys=True, data=True):
            new_u = node_mapping.get(u, u)
            new_v = node_mapping.get(v, v)
            if new_u != new_v and not g_collapsed.has_edge(new_u, new_v):
                g_collapsed.add_edge(new_u, new_v, **data)

        g_collapsed.remove_nodes_from(list(nx.isolates(g_collapsed)))

        # 4. Powrót do WGS84 i finalne ściągnięcie prostych krawędzi
        g_wgs84 = ox.project_graph(g_collapsed, to_crs="epsg:4326")
        g_wgs84.graph["simplified"] = False
        return ox.simplify_graph(g_wgs84)
