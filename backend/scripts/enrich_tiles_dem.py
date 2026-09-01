import glob
import os
import pickle
import rasterio
from tqdm import tqdm

TILES_DIR = "./tiles_data"
DEM_RASTER_PATH = "./poland_dem.tif"


def enrich_tiles():
    if not os.path.exists(DEM_RASTER_PATH):
        print(f"❌ DEM file not found at: {DEM_RASTER_PATH}")
        return

    tile_files = sorted(glob.glob(f"{TILES_DIR}/*.pkl"))
    if not tile_files:
        print(f"❌ No tile files found in {TILES_DIR}!")
        return

    print(f"🏔️ Enriching {len(tile_files)} tiles with raw elevation attributes...")

    with rasterio.open(DEM_RASTER_PATH) as dem:
        for filepath in tqdm(tile_files, desc="Processing tiles"):
            with open(filepath, "rb") as f:
                G = pickle.load(f)

            if len(G.nodes) == 0:
                continue

            # 1. Fetch elevation for each node
            node_ids = list(G.nodes)
            coords = [(G.nodes[n]["x"], G.nodes[n]["y"]) for n in node_ids]
            sampled_elevations = [val[0] for val in dem.sample(coords)]

            for node_id, elev in zip(node_ids, sampled_elevations):
                G.nodes[node_id]["elevation"] = float(elev) if elev is not None and elev > -100 else 0.0

            # 2. Compute directional physical slope and elevation differences for edges
            for u, v, k, data in G.edges(keys=True, data=True):
                elev_u = G.nodes[u].get("elevation", 0.0)
                elev_v = G.nodes[v].get("elevation", 0.0)
                length = max(data.get("length", 1.0), 0.1)

                elev_diff = elev_v - elev_u

                # Raw physical features (ML-ready)
                data["elevation_change"] = round(elev_diff, 2)
                data["grade"] = round(elev_diff / length, 4)

            with open(filepath, "wb") as f:
                pickle.dump(G, f, protocol=pickle.HIGHEST_PROTOCOL)

    print("🎉 All tiles now contain complete raw feature vectors ready for ML/GNN pipelines!")


if __name__ == "__main__":
    enrich_tiles()
