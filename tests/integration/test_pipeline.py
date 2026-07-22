"""End-to-end pipeline test: generate -> load into DuckDB -> dbt build.

Covers the project spec's integration-test checklist: seed data loads
(covered by tests/unit/test_recipe_costs.py), synthetic data generates,
raw data loads into DuckDB, dbt models run, dbt tests pass, required
marts exist, and Streamlit-style queries return data.

Runs the real CLI commands via subprocess rather than importing
functions directly — this is what actually needs to keep working, not
just the underlying Python. Uses a small dataset for speed, matching
what CI runs. Note: this overwrites data/raw/*.csv and
data/database/restaurant.duckdb with that small dataset as a side
effect, same as running the generator or CI's smoke-test step directly.
"""

from __future__ import annotations

import subprocess
import sys

import duckdb
import pytest

from restaurant_ops.config import DATABASE_PATH, PROJECT_ROOT

_REQUIRED_MARTS = [
    "mart_daily_performance",
    "mart_menu_engineering",
    "mart_channel_profitability",
    "mart_labour_productivity",
    "mart_service_quality",
    "mart_inventory_risk",
    "mart_review_analysis",
]


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=120)


@pytest.fixture(scope="module")
def pipeline_result():
    generate = _run(
        [
            sys.executable,
            "scripts/generate_data.py",
            "--start-date",
            "2025-07-01",
            "--days",
            "14",
            "--average-orders",
            "20",
            "--seed",
            "42",
        ]
    )
    assert generate.returncode == 0, generate.stdout + generate.stderr

    load = _run([sys.executable, "scripts/load_raw_data.py"])
    assert load.returncode == 0, load.stdout + load.stderr

    dbt_build = _run(
        [
            "uv",
            "run",
            "dbt",
            "build",
            "--project-dir",
            "dbt_restaurant",
            "--profiles-dir",
            "dbt_restaurant",
            "--full-refresh",
        ]
    )
    assert dbt_build.returncode == 0, dbt_build.stdout + dbt_build.stderr
    return generate, load, dbt_build


def test_generate_load_and_dbt_build_all_succeed(pipeline_result):
    for result in pipeline_result:
        assert result.returncode == 0


def test_required_marts_exist_and_have_rows(pipeline_result):
    con = duckdb.connect(str(DATABASE_PATH), read_only=True)
    try:
        for mart in _REQUIRED_MARTS:
            row_count = con.execute(f"SELECT count(*) FROM marts.{mart}").fetchone()[0]
            assert row_count > 0, f"{mart} exists but has no rows"
    finally:
        con.close()


def test_star_schema_query_returns_data(pipeline_result):
    """A representative cross-mart query, the kind the Streamlit app will run."""
    con = duckdb.connect(str(DATABASE_PATH), read_only=True)
    try:
        result = con.execute(
            """
            select channel, sum(net_sales) as net_sales
            from marts.mart_channel_profitability
            group by channel
            order by net_sales desc
            """
        ).fetchdf()
    finally:
        con.close()
    assert len(result) == 4
    assert result["net_sales"].sum() > 0
