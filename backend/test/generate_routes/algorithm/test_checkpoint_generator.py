import math
from unittest.mock import patch

import pytest
from src.database.geo_point import GeoPoint
from src.generate_routes.algorithm.checkpoints_generator import CheckpointsGenerator

MODULE_PATH = CheckpointsGenerator.__module__


@pytest.fixture
def center_point():
    return GeoPoint(latitude=52.2297, longitude=21.0122)


class TestCheckpointsGeneratorExecutionFlow:
    @patch.object(CheckpointsGenerator, "_meters_to_geopoint")
    @patch(f"{MODULE_PATH}.random.randint")
    @patch(f"{MODULE_PATH}.random.uniform")
    @patch.object(CheckpointsGenerator, "_sample_fat_tail")
    def test_generate_checkpoints_execution_flow_counter_clockwise(
        self,
        mock_sample_fat_tail,
        mock_random_uniform,
        mock_random_randint,
        mock_meters_to_geopoint,
        center_point,
    ):
        """Verifies deterministic math steps, centroid sorting, and forward cycle traversal."""
        mock_sample_fat_tail.return_value = 1.0  # noise = 0.0, r_norm = 0.55
        # 1. theta_center, 2. alpha_cloud, 3. aspect_ratio, 4. base_sector_angle, 5-7. sector angle_offsets
        mock_random_uniform.side_effect = [
            0.0,  # theta_center -> east
            0.0,  # alpha_cloud -> 0 rad
            1.0,  # aspect_ratio -> circle
            0.0,  # base_sector_angle
            0.0,  # sector 0 offset
            0.0,  # sector 1 offset
            0.0,  # sector 2 offset
        ]
        mock_random_randint.return_value = 0  # Preserve CCW direction

        mock_geopoints = [
            GeoPoint(latitude=52.23, longitude=21.01),
            GeoPoint(latitude=52.24, longitude=21.02),
            GeoPoint(latitude=52.25, longitude=21.03),
        ]
        mock_meters_to_geopoint.side_effect = mock_geopoints

        radius = 1000.0
        results = CheckpointsGenerator.generate_checkpoints(center_point, radius)

        assert mock_sample_fat_tail.call_count == 4  # 1 for center distance + 3 for sector radii
        assert mock_random_uniform.call_count == 7
        assert mock_meters_to_geopoint.call_count == 3
        assert len(results) == 3
        assert results == mock_geopoints

    @patch(f"{MODULE_PATH}.random.randint")
    @patch(f"{MODULE_PATH}.random.uniform")
    @patch.object(CheckpointsGenerator, "_sample_fat_tail")
    def test_generate_checkpoints_reverses_order_when_clockwise(
        self,
        mock_sample_fat_tail,
        mock_random_uniform,
        mock_random_randint,
        center_point,
    ):
        """Verifies that selecting randint=1 reverses the traversal sequence (clockwise)."""
        mock_sample_fat_tail.return_value = 1.0
        mock_random_uniform.side_effect = [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0]

        # First run: CCW order (randint = 0)
        mock_random_randint.return_value = 0
        ccw_results = CheckpointsGenerator.generate_checkpoints(center_point, radius=1000.0)

        # Second run: CW order (randint = 1)
        mock_random_uniform.side_effect = [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0]
        mock_random_randint.return_value = 1
        cw_results = CheckpointsGenerator.generate_checkpoints(center_point, radius=1000.0)

        assert len(ccw_results) == 3
        assert len(cw_results) == 3
        # In a 4-vertex cycle [0, A, B, C], reversing yields [0, C, B, A] -> slice [1:] yields [C, B, A]
        assert cw_results[0].latitude == pytest.approx(ccw_results[2].latitude)
        assert cw_results[0].longitude == pytest.approx(ccw_results[2].longitude)
        assert cw_results[1].latitude == pytest.approx(ccw_results[1].latitude)
        assert cw_results[1].longitude == pytest.approx(ccw_results[1].longitude)
        assert cw_results[2].latitude == pytest.approx(ccw_results[0].latitude)
        assert cw_results[2].longitude == pytest.approx(ccw_results[0].longitude)


class TestCheckpointsGeneratorUnitAndIntegration:
    def test_meters_to_geopoint_cardinal_offsets(self, center_point):
        """Tests meter offset calculations to north and east directions."""
        # Shift 1000m North (dx=0, dy=1000)
        point_north = CheckpointsGenerator._meters_to_geopoint(center_point, dx=0.0, dy=1000.0)
        expected_lat_diff = (1000.0 / CheckpointsGenerator.EARTH_RADIUS) * (180.0 / math.pi)
        assert point_north.latitude == pytest.approx(center_point.latitude + expected_lat_diff, rel=1e-6)
        assert point_north.longitude == pytest.approx(center_point.longitude, rel=1e-6)

        # Shift 1000m East (dx=1000, dy=0)
        point_east = CheckpointsGenerator._meters_to_geopoint(center_point, dx=1000.0, dy=0.0)
        lat_rad = math.radians(center_point.latitude)
        expected_lon_diff = (1000.0 / (CheckpointsGenerator.EARTH_RADIUS * math.cos(lat_rad))) * (180.0 / math.pi)
        assert point_east.latitude == pytest.approx(center_point.latitude, rel=1e-6)
        assert point_east.longitude == pytest.approx(center_point.longitude + expected_lon_diff, rel=1e-6)

    def test_sample_fat_tail_bounds(self):
        """Verifies that fat tail sampling remains strictly clipped within [0.2, 2.5]."""
        samples = [CheckpointsGenerator._sample_fat_tail(df=3.0) for _ in range(100)]
        assert all(0.2 <= s <= 2.5 for s in samples)
        assert all(isinstance(s, float) for s in samples)

    def test_generate_checkpoints_real_coords_integration(self, center_point):
        """Integration test validating output shape, types, and distance envelopes."""
        radius = 1500.0
        results = CheckpointsGenerator.generate_checkpoints(center_point, radius)

        assert isinstance(results, list)
        assert len(results) == 3
        assert all(isinstance(pt, GeoPoint) for pt in results)

        # Ensure all waypoints are distinct and not coincident with start
        unique_points = {(pt.latitude, pt.longitude) for pt in results}
        assert len(unique_points) == 3
        assert (center_point.latitude, center_point.longitude) not in unique_points

        # Verify that coordinates stay within reasonable geographical bounds around center
        lat_rad = math.radians(center_point.latitude)
        for pt in results:
            dy = math.radians(pt.latitude - center_point.latitude) * CheckpointsGenerator.EARTH_RADIUS
            dx = (
                math.radians(pt.longitude - center_point.longitude)
                * CheckpointsGenerator.EARTH_RADIUS
                * math.cos(lat_rad)
            )
            dist_from_center = math.hypot(dx, dy)
            # The generated loop cloud is bounded within roughly 2 * radius
            assert dist_from_center <= radius * 2.2
            assert dist_from_center > 0.0
