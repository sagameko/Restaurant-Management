"""Configuration loading for the restaurant operations platform.

Paths and simulation parameters are kept out of code so the same package
can run against different data directories or business-rule presets
without editing source.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
SEED_DIR = DATA_DIR / "seed"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
DATABASE_PATH = DATA_DIR / "database" / "restaurant.duckdb"


class ChannelConfig(BaseModel):
    probability: float = Field(ge=0, le=1)
    commission_rate: float = Field(ge=0, le=1)


class RestaurantConfig(BaseModel):
    name: str
    location: str
    seating_capacity: int = Field(gt=0)
    opening_hour: int = Field(ge=0, le=23)
    closing_hour: int = Field(ge=0, le=24)


class SimulationConfig(BaseModel):
    start_date: str
    number_of_days: int = Field(gt=0)
    random_seed: int
    average_daily_orders: int = Field(gt=0)


class SimulationSettings(BaseModel):
    restaurant: RestaurantConfig
    simulation: SimulationConfig
    channels: dict[str, ChannelConfig]

    def model_post_init(self, __context: object) -> None:
        total_probability = sum(c.probability for c in self.channels.values())
        if abs(total_probability - 1.0) > 1e-6:
            raise ValueError(f"Channel probabilities must sum to 1.0, got {total_probability:.4f}")


def load_simulation_settings(path: Path | None = None) -> SimulationSettings:
    """Load and validate `config/simulation.yaml` (or an override path)."""
    config_path = path or CONFIG_DIR / "simulation.yaml"
    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    return SimulationSettings.model_validate(raw)


@lru_cache(maxsize=1)
def get_simulation_settings() -> SimulationSettings:
    """Cached accessor for the default simulation settings."""
    return load_simulation_settings()


def load_business_rules(path: Path | None = None) -> dict:
    """Load `config/business_rules.yaml` as a plain dict.

    Unlike `SimulationSettings`, this isn't modelled as nested Pydantic
    classes: it's a flat set of tunable generator constants (demand
    multipliers, staffing placeholders, review templates, ...) that's
    consumed directly by `restaurant_ops.generation`, not by end users.
    """
    config_path = path or CONFIG_DIR / "business_rules.yaml"
    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


@lru_cache(maxsize=1)
def get_business_rules() -> dict:
    """Cached accessor for the default business-rules configuration."""
    return load_business_rules()
