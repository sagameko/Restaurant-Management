"""Tests for configuration loading."""

from __future__ import annotations

import pytest

from restaurant_ops.config import SimulationSettings, load_simulation_settings


def test_default_simulation_config_loads():
    settings = load_simulation_settings()
    assert settings.restaurant.name
    assert settings.simulation.number_of_days > 0
    assert 0 < len(settings.channels) < 10


def test_channel_probabilities_must_sum_to_one():
    with pytest.raises(ValueError, match="must sum to 1.0"):
        SimulationSettings.model_validate(
            {
                "restaurant": {
                    "name": "Test",
                    "location": "Melbourne",
                    "seating_capacity": 50,
                    "opening_hour": 11,
                    "closing_hour": 21,
                },
                "simulation": {
                    "start_date": "2025-07-01",
                    "number_of_days": 30,
                    "random_seed": 1,
                    "average_daily_orders": 50,
                },
                "channels": {
                    "dine_in": {"probability": 0.5, "commission_rate": 0.0},
                    "pickup": {"probability": 0.2, "commission_rate": 0.0},
                },
            }
        )
