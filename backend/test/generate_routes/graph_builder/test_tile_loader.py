import os
import pickle
from unittest.mock import MagicMock, mock_open, patch

import networkx as nx
import pytest
from src.generate_routes.graph_builder.data.tile_pointer import TilePointer
from src.generate_routes.graph_builder.tile_loader import TileLoader


@pytest.fixture
def mock_pointer():
    pointer = MagicMock(spec=TilePointer)
    pointer.id = "12_2300_1400"
    return pointer


class TestTileLoader:
    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    @patch("pickle.load")
    def test_load_from_disk_success(
        self, mock_pickle_load, mock_file, mock_exists, mock_pointer
    ):
        """Verifies that a valid pickle file is loaded and returned."""
        mock_exists.return_value = True
        mock_graph = MagicMock()
        mock_pickle_load.return_value = mock_graph

        result = TileLoader._load_from_disk(mock_pointer)

        expected_path = os.path.join(TileLoader.TILES_DIR, f"{mock_pointer.id}.pkl")
        mock_file.assert_called_once_with(expected_path, "rb")
        mock_pickle_load.assert_called_once_with(mock_file())
        assert result == mock_graph

    @patch("os.path.exists")
    def test_load_from_disk_file_not_found(self, mock_exists, mock_pointer):
        """
        Verifies that an empty MultiDiGraph is returned when the file does not exist.
        """
        mock_exists.return_value = False

        result = TileLoader._load_from_disk(mock_pointer)

        assert isinstance(result, nx.MultiDiGraph)
        assert len(result.nodes) == 0

    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    @patch("pickle.load")
    def test_load_from_disk_handles_corrupted_file(
        self, mock_pickle_load, mock_file, mock_exists, mock_pointer
    ):
        """
        Verifies that unpickling errors are caught and return an empty MultiDiGraph.
        """
        mock_exists.return_value = True
        mock_pickle_load.side_effect = pickle.UnpicklingError("Corrupted file")

        result = TileLoader._load_from_disk(mock_pointer)

        assert isinstance(result, nx.MultiDiGraph)
        assert len(result.nodes) == 0

    @patch.object(TileLoader, "_load_from_disk")
    def test_get_tiles_filters_out_empty_tiles(self, mock_load):
        """Verifies that get_tiles only includes tiles with nodes > 0."""
        # 1. Poprawny kafelek z węzłami
        valid_tile = MagicMock()
        valid_tile.nodes = [1, 2, 3]

        # 2. Pusty kafelek (0 węzłów)
        empty_tile = MagicMock()
        empty_tile.nodes = []

        pointer_1 = MagicMock(spec=TilePointer, id="tile_1")
        pointer_2 = MagicMock(spec=TilePointer, id="tile_2")

        mock_load.side_effect = [valid_tile, empty_tile]

        results = TileLoader.get_tiles([pointer_1, pointer_2])

        assert results == [valid_tile]
        assert len(results) == 1
        assert mock_load.call_count == 2

    @patch.object(TileLoader, "_load_from_disk")
    def test_get_tiles_empty_input(self, mock_load):
        """Verifies that passing an empty list returns an empty list immediately."""
        results = TileLoader.get_tiles([])

        assert results == []
        mock_load.assert_not_called()
