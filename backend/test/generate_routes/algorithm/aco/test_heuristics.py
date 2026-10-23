import math
from dataclasses import FrozenInstanceError

import pytest
from src.generate_routes.algorithm.aco.utils.heuristics import BudgetParams


class TestBudgetParams:
    def test_default_values_and_types(self):
        """Verifies default parameter values, ranges, and types."""
        params = BudgetParams()

        # Slack damping and clamping constants
        assert isinstance(params.slack_damping_factor, float)
        assert params.slack_damping_factor == pytest.approx(0.5)
        assert isinstance(params.slack_clamp_ratio, float)
        assert params.slack_clamp_ratio == pytest.approx(0.25)

        # Budget surplus threshold
        assert isinstance(params.ratio_to_detour_threshold, float)
        assert params.ratio_to_detour_threshold == pytest.approx(1.2)

        # Progress and stability offsets
        assert isinstance(params.deficit_progress_boost, float)
        assert params.deficit_progress_boost == pytest.approx(5.0)
        assert isinstance(params.epsilon_offset, float)
        assert params.epsilon_offset == pytest.approx(1.0)

        # Detour constants
        assert isinstance(params.detour_length_scale, float)
        assert params.detour_length_scale == pytest.approx(50.0)
        assert isinstance(params.max_detour_bonus, float)
        assert params.max_detour_bonus == pytest.approx(2.5)

        # Alignment directional weights
        assert isinstance(params.forward_alignment_weight, float)
        assert params.forward_alignment_weight == pytest.approx(1.2)
        assert isinstance(params.backward_alignment_weight, float)
        assert params.backward_alignment_weight == pytest.approx(0.6)

    def test_turn_angles_and_penalty_hierarchy(self):
        """Ensures turn thresholds and weights preserve monotonic penalty progression."""
        params = BudgetParams()

        # Check angular thresholds in radians
        assert params.shallow_turn_max_rad == pytest.approx(math.radians(45.0))
        assert params.right_angle_turn_max_rad == pytest.approx(math.radians(105.0))
        assert 0.0 < params.shallow_turn_max_rad < params.right_angle_turn_max_rad < math.pi

        # Sharp turns should receive stronger penalties (lower weights) than grid right angles
        assert params.sharp_turn_weight == pytest.approx(0.20)
        assert params.right_angle_turn_weight == pytest.approx(0.60)
        assert params.sharp_turn_weight < params.right_angle_turn_weight < 1.0

        # Forward movement must be prioritized over backward alignment
        assert params.backward_alignment_weight < params.forward_alignment_weight

    def test_custom_values_instantiation(self):
        """Verifies that custom parameters can be supplied on initialization."""
        custom_params = BudgetParams(
            slack_damping_factor=0.8,
            ratio_to_detour_threshold=1.5,
            sharp_turn_weight=0.1,
        )

        assert custom_params.slack_damping_factor == pytest.approx(0.8)
        assert custom_params.ratio_to_detour_threshold == pytest.approx(1.5)
        assert custom_params.sharp_turn_weight == pytest.approx(0.1)
        # Untouched fields must preserve their defaults
        assert custom_params.max_detour_bonus == pytest.approx(2.5)

    def test_immutability_frozen_dataclass(self):
        """Ensures dataclass is frozen and mutating any field raises FrozenInstanceError."""
        params = BudgetParams()

        with pytest.raises(FrozenInstanceError):
            params.slack_damping_factor = 0.9  # type: ignore[misc]

        with pytest.raises(FrozenInstanceError):
            params.ratio_to_detour_threshold = 2.0  # type: ignore[misc]
