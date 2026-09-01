import os
import subprocess
import time

PBF_SOURCE = "poland-latest.osm.pbf"
SPLIT_DIR = "./split_pbfs"
GRID_SIZE = 4  # 4x4 = 16 bounding box parts
POLAND_BBOX = [14.0, 49.0, 24.2, 55.0]  # [min_lon, min_lat, max_lon, max_lat]


def split_map():
    os.makedirs(SPLIT_DIR, exist_ok=True)
    min_lon, min_lat, max_lon, max_lat = POLAND_BBOX

    lon_step = (max_lon - min_lon) / GRID_SIZE
    lat_step = (max_lat - min_lat) / GRID_SIZE

    print(f"🔪 Starting to split {PBF_SOURCE} into {GRID_SIZE * GRID_SIZE} bounding box tiles...")
    start_time = time.time()
    part_index = 1

    for i in range(GRID_SIZE):
        for j in range(GRID_SIZE):
            b_min_lon = round(min_lon + i * lon_step, 4)
            b_max_lon = round(min_lon + (i + 1) * lon_step, 4)
            b_min_lat = round(min_lat + j * lat_step, 4)
            b_max_lat = round(min_lat + (j + 1) * lat_step, 4)

            # ~1km buffer to prevent cutting ways on boundary borders
            buf = 0.01
            bbox_str = f"{b_min_lon - buf},{b_min_lat - buf},{b_max_lon + buf},{b_max_lat + buf}"
            output_part = f"{SPLIT_DIR}/part_{part_index:02d}.osm.pbf"

            if os.path.exists(output_part):
                print(f"  ⏭️ [Part {part_index:02d}/16] Already exists, skipping: {output_part}")
            else:
                print(f"  ✂️ [Part {part_index:02d}/16] Extracting BBOX: {bbox_str}...")
                cmd = [
                    "osmium",
                    "extract",
                    "-b",
                    bbox_str,
                    PBF_SOURCE,
                    "-o",
                    output_part,
                    "--overwrite",
                ]
                subprocess.run(cmd, check=True)

            part_index += 1

    print(f"\n🎉 Finished in {time.time() - start_time:.1f}s! PBF files are located in: {SPLIT_DIR}")


if __name__ == "__main__":
    split_map()
