# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "dem-stitcher",
#     "rasterio",
# ]
# ///

from dem_stitcher import stitch_dem
import rasterio

# Poland BBOX: [min_lon, min_lat, max_lon, max_lat]
POLAND_BBOX = [14.0, 49.0, 24.2, 55.0]
OUTPUT_FILE = "poland_dem.tif"


def download_dem():
    print(f"📥 Downloading and stitching Copernicus DEM 30m (GLO-30) for bbox {POLAND_BBOX}...")

    # Download tiles and merge in memory
    elevation_array, profile = stitch_dem(
        POLAND_BBOX,
        dem_name="glo_30",
        dst_ellipsoidal_height=False,
        dst_area_or_point="Point",
    )

    # Enable Deflate compression (reduces size from ~3GB to ~500MB)
    profile.update(compress="deflate", predictor=2, zlevel=9)

    print(f"💾 Saving compressed GeoTIFF to ./{OUTPUT_FILE}...")
    with rasterio.open(OUTPUT_FILE, "w", **profile) as dst:
        dst.write(elevation_array, 1)

    print(f"🎉 Done! File saved as ./{OUTPUT_FILE}")


if __name__ == "__main__":
    download_dem()
