import pickle
from unittest.mock import patch

import networkx as nx
import pytest
from src.generate_routes.graph_builder.data.tile_pointer import TilePointer
from src.generate_routes.graph_builder.tile_cache_manager import TileCacheManager


@pytest.fixture
def mock_pointer():
    return TilePointer(x=9000, y=5400, z=14)


@pytest.fixture
def dummy_graph():
    G = nx.MultiDiGraph()
    G.add_node(1, x=21.0, y=52.0)
    return G


@pytest.fixture
def empty_graph():
    return nx.MultiDiGraph()


@patch(
    "src.generate_routes.graph_builder.tile_cache_manager.TileCacheManager._redis_client"
)
@patch(
    "src.generate_routes.graph_builder.tile_cache_manager.TileCacheManager._disk_cache"
)
@patch("src.generate_routes.graph_builder.tile_downloader.TileDownloader.download_tile")
class TestTileCacheManager:
    def test_l1_hit_returns_data_immediately(
        self, mock_download, mock_disk, mock_redis, mock_pointer, dummy_graph
    ):
        """L1 (Redis) hit should return immediately without checking L2 or API."""
        mock_redis.get.return_value = pickle.dumps(dummy_graph)

        result = TileCacheManager.get_tiles([mock_pointer])

        assert len(result) == 1
        mock_redis.get.assert_called_once_with(mock_pointer.id)
        mock_disk.get.assert_not_called()
        mock_download.assert_not_called()

    def test_l2_hit_promotes_to_l1(
        self, mock_download, mock_disk, mock_redis, mock_pointer, dummy_graph
    ):
        """L2 (Disk) hit should return data and promote it back to L1 (Redis)."""
        mock_redis.get.return_value = None
        mock_disk.get.return_value = dummy_graph

        result = TileCacheManager.get_tiles([mock_pointer])

        assert len(result) == 1
        mock_redis.get.assert_called_once_with(mock_pointer.id)
        mock_disk.get.assert_called_once_with(mock_pointer.id)
        mock_download.assert_not_called()
        mock_redis.setex.assert_called_once()

    def test_cache_miss_fetches_from_api_and_saves(
        self, mock_download, mock_disk, mock_redis, mock_pointer, dummy_graph
    ):
        """Cache miss should fetch from API and save to both L1 and L2."""
        mock_redis.get.return_value = None
        mock_disk.get.return_value = None
        mock_download.return_value = dummy_graph

        result = TileCacheManager.get_tiles([mock_pointer])

        assert len(result) == 1
        mock_download.assert_called_once_with(mock_pointer)
        mock_disk.set.assert_called_once_with(mock_pointer.id, dummy_graph)
        mock_redis.setex.assert_called_once()

    def test_empty_tiles_are_filtered_out(
        self, mock_download, mock_disk, mock_redis, mock_pointer, empty_graph
    ):
        """Empty graphs (e.g. water/no roads)
        should be cached but not returned in the final list."""
        mock_redis.get.return_value = None
        mock_disk.get.return_value = None
        mock_download.return_value = empty_graph

        result = TileCacheManager.get_tiles([mock_pointer])

        assert len(result) == 0
        mock_disk.set.assert_called_once_with(mock_pointer.id, empty_graph)
