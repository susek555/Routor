import math
import random

import numpy as np

from src.database.geo_point import GeoPoint


class CheckpointsGenerator:
    """
    Generates intermediate waypoints for a running loop route
    based on an elliptical cloud sampling with angular-sweep sequencing.
    """

    EARTH_RADIUS = 6_371_000.0  # Earth radius in meters

    @classmethod
    def _sample_fat_tail(cls, df: float = 3.0) -> float:
        """
        Samples a positive value from a heavy-tailed distribution (Student's t, df=3),
        normalized within a typical range around 1.0.
        """
        val = abs(np.random.standard_t(df=df))
        return float(np.clip(val, 0.2, 2.5))

    @classmethod
    def _meters_to_geopoint(cls, center: GeoPoint, dx: float, dy: float) -> GeoPoint:
        """
        Converts meter offsets (dx: east/west, dy: north/south) into a GeoPoint.
        """
        d_lat = (dy / cls.EARTH_RADIUS) * (180.0 / math.pi)
        lat_rad = math.radians(center.latitude)
        d_lon = (dx / (cls.EARTH_RADIUS * math.cos(lat_rad))) * (180.0 / math.pi)
        return GeoPoint(latitude=center.latitude + d_lat, longitude=center.longitude + d_lon)

    @classmethod
    def generate_checkpoints(cls, center: GeoPoint, radius: float) -> list[GeoPoint]:
        """
        Generates 3 intermediate checkpoints creating an open, non-self-intersecting loop framework.
        """
        # ==========================================
        # Step I: Cloud center direction angle [0, 2pi]
        # ==========================================
        theta_center = random.uniform(0, 2 * math.pi)  # noqa: S311 not a cryptographic purpose

        # ==========================================
        # Step II: Cloud center distance from start
        # Placed around 0.45 - 0.65 of radius to leave ample room for opening up
        # ==========================================
        d_scale = 0.50 * radius
        noise = (cls._sample_fat_tail(df=3.0) - 1.0) * 0.2
        d_center = np.clip(d_scale * (1.0 + noise), 0.35 * radius, 0.70 * radius)

        cx = d_center * math.cos(theta_center)
        cy = d_center * math.sin(theta_center)

        # ==========================================
        # Step III & IV: Orientation & Aspect ratio
        # Kept closer to 1.0 - 1.35 to avoid collapse into a narrow stick
        # ==========================================
        alpha_cloud = random.uniform(0, math.pi)  # noqa: S311 not a cryptographic purpose
        aspect_ratio = random.uniform(1.0, 1.35)  # noqa: S311 not a cryptographic purpose

        # ==========================================
        # Step V: Cloud dimensions (generous size to form a wide loop)
        # ==========================================
        b = max(radius * 0.28, (radius - d_center) * 0.60)
        a = b * aspect_ratio

        # ==========================================
        # Step VI & VII: Sector partition and sampling
        # 3 sectors of 120 deg ensuring 2D dispersion
        # ==========================================
        base_sector_angle = random.uniform(0, (2.0 / 3.0) * math.pi)  # noqa: S311 not a cryptographic purpose
        raw_cloud_points: list[tuple[float, float]] = []

        for i in range(3):
            sector_start = base_sector_angle + i * (2.0 / 3.0 * math.pi)
            sector_span = 2.0 / 3.0 * math.pi

            # Angle within third: uniform or shifted via heavy tail
            angle_offset = random.uniform(0.15 * sector_span, 0.85 * sector_span)  # noqa: S311 not a cryptographic purpose
            angle = sector_start + angle_offset

            # Radial distance from cloud center
            r_norm = np.clip(cls._sample_fat_tail(df=3.0) * 0.55, 0.35, 1.0)

            # Local coordinates on rotated ellipse
            lx = r_norm * a * math.cos(angle)
            ly = r_norm * b * math.sin(angle)

            cos_a = math.cos(alpha_cloud)
            sin_a = math.sin(alpha_cloud)
            rx = lx * cos_a - ly * sin_a
            ry = lx * sin_a + ly * cos_a

            px = cx + rx
            py = cy + ry
            raw_cloud_points.append((px, py))

        # ==========================================
        # Step IX: Centroid-based Angular Sweep Ordering
        # Prevents self-intersections and pinched returns by sorting all four
        # vertices (start + 3 checkpoints) cyclically around their common centroid.
        # ==========================================
        start_point_offset = (0.0, 0.0)
        loop_vertices = [start_point_offset] + raw_cloud_points

        # 1. Calculate common geometric centroid of the loop vertices
        centroid_x = sum(p[0] for p in loop_vertices) / 4.0
        centroid_y = sum(p[1] for p in loop_vertices) / 4.0

        # 2. Sort all 4 vertices by polar angle around the centroid (counter-clockwise)
        sorted_by_angle = sorted(
            loop_vertices,
            key=lambda p: math.atan2(p[1] - centroid_y, p[0] - centroid_x),
        )

        # 3. Cyclically align list to ensure start point (0, 0) remains at index 0
        start_index = sorted_by_angle.index(start_point_offset)
        ordered_cycle = [sorted_by_angle[(start_index + i) % 4] for i in range(4)]

        # 4. Randomize traversal orientation: keep counter-clockwise or reverse to clockwise
        if random.randint(0, 1) == 1:  # noqa: S311 not a cryptographic purpose
            ordered_cycle = [ordered_cycle[0], ordered_cycle[3], ordered_cycle[2], ordered_cycle[1]]

        # Exclude the start point to return only the 3 sequential intermediate checkpoints
        ordered_points = ordered_cycle[1:]

        return [cls._meters_to_geopoint(center, px, py) for px, py in ordered_points]
