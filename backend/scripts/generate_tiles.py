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
DELETE_PART_AFTER_PROCESSING = (
    False  # Zmień na True, jeśli masz mało miejsca na dysku!
)

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
}


def haversine_dist(x1, y1, x2, y2):
  dx = (x2 - x1) * 111000 * math.cos(math.radians((y1 + y2) / 2))
  dy = (y2 - y1) * 111000
  return math.hypot(dx, dy)


class PartHandler(osmium.SimpleHandler):

  def __init__(self):
    super().__init__()
    self.needed_nodes = set()
    self.ways = []
    self.node_coords = {}

  def way(self, w):
    highway = w.tags.get("highway")
    if highway in WALKABLE_HIGHWAYS:
      nodes_list = [n.ref for n in w.nodes]
      if len(nodes_list) > 1:
        self.ways.append(nodes_list)
        self.needed_nodes.update(nodes_list)

  def node(self, n):
    if n.id in self.needed_nodes:
      self.node_coords[n.id] = (n.location.lon, n.location.lat)


def process_part(pbf_path, part_num, total_parts):
  print(f"🚀 Przetwarzanie [{part_num}/{total_parts}]: {pbf_path}")
  t0 = time.time()

  # Pomijamy puste części (np. Bałtyk poza granicą)
  if os.path.getsize(pbf_path) < 1000:
    print(f"  ⚠️ Pusty plik, pomijam.")
    return

  handler = PartHandler()
  handler.apply_file(pbf_path)
  handler.apply_file(pbf_path, locations=True)

  if not handler.ways:
    print(f"  ⚠️ Brak tras pieszych w tej części, pomijam.")
    return

  # Podział na kafelki w pamięci dla tej jednej części
  tiles_in_memory = {}
  for way in handler.ways:
    for u, v in zip(way[:-1], way[1:]):
      if u in handler.node_coords and v in handler.node_coords:
        x1, y1 = handler.node_coords[u]
        x2, y2 = handler.node_coords[v]
        dist = haversine_dist(x1, y1, x2, y2)

        tile = mercantile.tile(x1, y1, ZOOM_LEVEL)
        key = f"{tile.z}_{tile.x}_{tile.y}"

        if key not in tiles_in_memory:
          tiles_in_memory[key] = nx.MultiDiGraph()

        G = tiles_in_memory[key]
        G.add_node(u, x=x1, y=y1)
        G.add_node(v, x=x2, y=y2)
        G.add_edge(u, v, length=dist)
        G.add_edge(v, u, length=dist)

  del handler  # Zwolnienie pamięci RAM

  # Zapis na dysk (z łączeniem grafów na granicach)
  saved = 0
  for tile_key, new_graph in tiles_in_memory.items():
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
    print(f"  🗑️ Usunięto tymczasowy plik: {pbf_path}")

  print(
      f"  ✅ Zapisano/zaktualizowano {saved} kafelków w {time.time() - t0:.1f}s"
  )


def main():
  os.makedirs(OUTPUT_DIR, exist_ok=True)
  parts = sorted(glob.glob(f"{SPLIT_DIR}/*.osm.pbf"))

  if not parts:
    print(
        f"❌ Brak plików w {SPLIT_DIR}! Uruchom najpierw"
        " 'scripts/split_map.py'."
    )
    return

  total_start = time.time()
  for idx, part in enumerate(parts, start=1):
    process_part(part, idx, len(parts))

  print(
      f"\n🎉 WSZYSTKIE KAFELKI GOTOWE w {time.time() - total_start:.1f}s! Dane są"
      f" w {OUTPUT_DIR}"
  )


if __name__ == "__main__":
  main()