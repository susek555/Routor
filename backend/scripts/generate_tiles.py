import glob
import math
import os
import pickle
import time

import mercantile
import networkx as nx
import osmium

SPLIT_DIR = "./split_pbfs"
OUTPUT_DIR = "./tiles_data"
ZOOM_LEVEL = 12
DELETE_PART_AFTER_PROCESSING = False

WALKABLE_HIGHWAYS = {
    "footway",
    "pedestrian",
    "path",
    "track",
    "residential",
    "service",
    "living_street",
    "steps",
    "cycleway",
    "unclassified",
    "tertiary",
    "secondary",
    "primary",
}

FORBIDDEN_ACCESS = {"private", "no"}
ALLOWED_FOOT_OVERRIDE = {"yes", "designated", "permissive"}

FEATURE_TAGS = [
    "highway",
    "service",
    "surface",
    "smoothness",
    "tracktype",
    "footway",
    "sidewalk",
    "cycleway",
    "lit",
    "access",
    "foot",
    "sac_scale",
    "trail_visibility",
    "incline",
    "bridge",
    "tunnel",
    "covered",
    "leisure",
    "landuse",
    "name",
]


def haversine_dist(x1: float, y1: float, x2: float, y2: float) -> float:
    dx = (x2 - x1) * 111000 * math.cos(math.radians((y1 + y2) / 2))
    dy = (y2 - y1) * 111000
    return math.hypot(dx, dy)


class PartHandler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.needed_nodes = set()
        self.ways = []
        self.node_data = {}

    def way(self, w):
        highway = w.tags.get("highway")
        if highway in WALKABLE_HIGHWAYS:
            access = w.tags.get("access")
            foot = w.tags.get("foot")

            # Odrzucamy tylko ewidentnie prywatne/zamknięte, o ile nie mają jawnej zgody dla pieszych
            if access in FORBIDDEN_ACCESS and foot not in ALLOWED_FOOT_OVERRIDE:
                return

            nodes_list = [n.ref for n in w.nodes]
            if len(nodes_list) > 1:
                raw_tags = {tag: w.tags.get(tag) for tag in FEATURE_TAGS if tag in w.tags}
                self.ways.append((nodes_list, raw_tags))
                self.needed_nodes.update(nodes_list)

    def node(self, n):
        if n.id in self.needed_nodes:
            self.node_data[n.id] = {
                "x": n.location.lon,
                "y": n.location.lat,
                "highway": n.tags.get("highway"),
            }


def process_part(pbf_path: str, part_num: int, total_parts: int):
    print(f"🚀 Processing [{part_num}/{total_parts}]: {pbf_path}")
    t0 = time.time()

    if os.path.getsize(pbf_path) < 1000:
        print("  ⚠️ Empty file, skipping.")
        return

    handler = PartHandler()
    handler.apply_file(pbf_path)
    handler.apply_file(pbf_path, locations=True)

    if not handler.ways:
        print("  ⚠️ No walkable pathways found in this part, skipping.")
        return

    tiles_in_memory = {}
    for way_nodes, tags in handler.ways:
        for u, v in zip(way_nodes[:-1], way_nodes[1:]):
            if u in handler.node_data and v in handler.node_data:
                u_info = handler.node_data[u]
                v_info = handler.node_data[v]

                x1, y1 = u_info["x"], u_info["y"]
                x2, y2 = v_info["x"], v_info["y"]
                dist = haversine_dist(x1, y1, x2, y2)

                tile = mercantile.tile(x1, y1, ZOOM_LEVEL)
                key = f"{tile.z}_{tile.x}_{tile.y}"

                if key not in tiles_in_memory:
                    tiles_in_memory[key] = nx.MultiDiGraph()

                G = tiles_in_memory[key]

                if not G.has_node(u):
                    G.add_node(u, x=x1, y=y1, highway=u_info["highway"])
                if not G.has_node(v):
                    G.add_node(v, x=x2, y=y2, highway=v_info["highway"])

                # Krawędź w przód
                edge_data = {"length": dist, **tags}
                G.add_edge(u, v, **edge_data)

                # Krawędź w tył (ruch pieszy)
                oneway = tags.get("oneway")
                foot_oneway = tags.get("oneway:foot")
                if foot_oneway != "yes" and (
                    oneway != "yes" or tags.get("highway") in {"path", "footway", "pedestrian", "track", "service"}
                ):
                    G.add_edge(v, u, **edge_data)

    del handler

    # Zapis i łączenie kafli na dysku
    saved = 0
    for tile_key, new_graph in tiles_in_memory.items():
        if len(new_graph.nodes) == 0:
            continue

        filename = f"{OUTPUT_DIR}/{tile_key}.pkl"
        if os.path.exists(filename):
            with open(filename, "rb") as f:
                existing_graph = pickle.load(f)
            combined_graph = nx.compose(existing_graph, new_graph)
            with open(filename, "wb") as f:
                pickle.dump(combined_graph, f, protocol=pickle.HIGHEST_PROTOCOL)
        else:
            with open(filename, "wb") as f:
                pickle.dump(new_graph, f, protocol=pickle.HIGHEST_PROTOCOL)
        saved += 1

    if DELETE_PART_AFTER_PROCESSING:
        os.remove(pbf_path)
        print(f"  🗑️ Removed temporary file: {pbf_path}")

    print(f"  ✅ Saved/Updated {saved} tiles in {time.time() - t0:.1f}s")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    parts = sorted(glob.glob(f"{SPLIT_DIR}/*.osm.pbf"))

    if not parts:
        print(f"❌ No files found in {SPLIT_DIR}! Run 'split_map.py' first.")
        return

    total_start = time.time()
    for idx, part in enumerate(parts, start=1):
        process_part(part, idx, len(parts))

    print(f"\n🎉 ALL TILES COMPLETED in {time.time() - total_start:.1f}s! Data is stored in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
