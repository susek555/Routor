import networkx as nx
import numpy as np
import osmnx as ox
from scipy.spatial import cKDTree
from shapely.geometry import LineString

from src.generate_routes.graph_builder.data.map import Map


class GraphSimplifier:
    DEFAULT_TOLERANCE_METERS = 15.0

    @classmethod
    def simplify(cls, graph: Map, tolerance_meters: float = DEFAULT_TOLERANCE_METERS) -> Map:
        if graph is None or len(graph.nodes) == 0:
            return graph

        g_proj = ox.project_graph(graph)

        nodes = list(g_proj.nodes(data=True))
        node_ids = [n[0] for n in nodes]
        coords = np.array([[n[1]["x"], n[1]["y"]] for n in nodes])

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

        g_wgs84 = ox.project_graph(g_collapsed, to_crs="epsg:4326")

        return cls._materialize_bend_nodes(g_wgs84)

    @classmethod
    def _materialize_bend_nodes(cls, G: nx.MultiDiGraph) -> nx.MultiDiGraph:
        STRAIGHT_LINE_COORDS_COUNT = 2

        g_dense = nx.MultiDiGraph()
        g_dense.graph = G.graph.copy()

        for n, data in G.nodes(data=True):
            g_dense.add_node(n, **data)

        synthetic_node_counter = 100_000_000

        for u, v, _, data in G.edges(keys=True, data=True):
            geom = data.get("geometry")
            if geom and isinstance(geom, LineString) and len(geom.coords) > STRAIGHT_LINE_COORDS_COUNT:
                coords = list(geom.coords)
                prev_node = u
                total_points = len(coords)

                for _, (x, y) in enumerate(coords[1:-1], start=1):
                    mid_node_id = synthetic_node_counter
                    synthetic_node_counter += 1

                    g_dense.add_node(mid_node_id, x=x, y=y, street_count=2)

                    sub_data = data.copy()
                    sub_data.pop("geometry", None)
                    sub_data["length"] = data.get("length", 1.0) / (total_points - 1)
                    g_dense.add_edge(prev_node, mid_node_id, **sub_data)
                    prev_node = mid_node_id

                sub_data = data.copy()
                sub_data.pop("geometry", None)
                sub_data["length"] = data.get("length", 1.0) / (total_points - 1)
                g_dense.add_edge(prev_node, v, **sub_data)
            else:
                clean_data = data.copy()
                clean_data.pop("geometry", None)
                g_dense.add_edge(u, v, **clean_data)

        return g_dense
