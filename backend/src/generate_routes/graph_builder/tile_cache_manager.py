import pickle

import diskcache
import redis

from src.generate_routes.graph_builder.data.map_tile import MapTile
from src.generate_routes.graph_builder.data.tile_pointer import TilePointer
from src.generate_routes.graph_builder.tile_downloader import TileDownloader


class TileCacheManager:
    # L1 CACHE (RAM)
    # db=1 to avoid conflicts with Celery tasks on db=0
    _redis_client = redis.Redis(host="routor_redis", port=6379, db=1)

    # TTL = 30 days to utilize redis volatile-lru!
    _CACHE_TTL = 60 * 60 * 24 * 30

    # L2 CACHE (DYSK)
    _disk_cache = diskcache.Cache(
        directory="/app/cache/tiles",
        size_limit=5 * 1024 * 1024 * 1024,  # Disk space limit: 5 GB)
        eviction_policy="least-recently-used",  # LRU on disk
    )

    @classmethod
    def get_tiles(cls, tile_pointers: list[TilePointer]) -> list[MapTile]:
        tiles = []
        for pointer in tile_pointers:
            tile = cls._get_or_fetch_tile(pointer)

            # Exclude empty tiles
            if len(tile.nodes) > 0:
                tiles.append(tile)

        return tiles

    @classmethod
    def _get_or_fetch_tile(cls, pointer: TilePointer) -> MapTile:
        # ---------------------------------------------------------
        # 1: L1 Cache (Redis - RAM)
        # ---------------------------------------------------------
        cached_in_ram = cls._redis_client.get(pointer.id)
        if cached_in_ram:
            print(f"[L1 CACHE] Hit for tile: {pointer.id}")
            # Should not be a security hotspot as those files source is not external
            return pickle.loads(cached_in_ram)  # noqa: S301

        # ---------------------------------------------------------
        # 2: L2 Cache (Shared disk)
        # ---------------------------------------------------------
        cached_on_disk = cls._disk_cache.get(pointer.id)
        if cached_on_disk:
            print(f"[L2 CACHE] Hit for tile: {pointer.id}")

            # Promote to L1 cache
            binary_graph = pickle.dumps(
                cached_on_disk, protocol=pickle.HIGHEST_PROTOCOL
            )
            # setex - set with expiration
            cls._redis_client.setex(pointer.id, cls._CACHE_TTL, binary_graph)

            return cached_on_disk

        # ---------------------------------------------------------
        # 3: Download from API (Cache Miss)
        # ---------------------------------------------------------
        print(f"[API] Downloading new tile from OSM: {pointer.id}")

        tile = TileDownloader.download_tile(pointer)

        # Save to L2
        cls._disk_cache.set(pointer.id, tile)

        # Save to L1
        binary_graph = pickle.dumps(tile, protocol=pickle.HIGHEST_PROTOCOL)
        cls._redis_client.setex(pointer.id, cls._CACHE_TTL, binary_graph)

        return tile
