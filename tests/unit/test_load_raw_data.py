"""Tests for the raw-layer DuckDB loader."""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from load_raw_data import _load_table, _row_hash  # noqa: E402


def test_row_hash_is_deterministic():
    row = pd.Series({"a": 1, "b": "x", "c": 2.5})
    assert _row_hash(row) == _row_hash(row.copy())


def test_row_hash_differs_for_different_content():
    row_a = pd.Series({"a": 1, "b": "x"})
    row_b = pd.Series({"a": 1, "b": "y"})
    assert _row_hash(row_a) != _row_hash(row_b)


def test_load_table_adds_metadata_columns(tmp_path):
    csv_path = tmp_path / "widgets.csv"
    pd.DataFrame({"widget_id": ["W1", "W2"], "quantity": [3, 5]}).to_csv(csv_path, index=False)

    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA raw")
    row_count = _load_table(con, "widgets", csv_path, batch_id="test-batch")

    assert row_count == 2
    result = con.execute("SELECT * FROM raw.widgets ORDER BY widget_id").fetchdf()
    assert list(result["widget_id"]) == ["W1", "W2"]
    assert (result["batch_id"] == "test-batch").all()
    assert (result["source_file"] == "widgets.csv").all()
    assert result["loaded_at"].notna().all()
    assert result["record_hash"].nunique() == 2


def test_load_table_hash_ignores_metadata_but_reflects_content(tmp_path):
    csv_path = tmp_path / "widgets.csv"
    pd.DataFrame({"widget_id": ["W1"], "quantity": [3]}).to_csv(csv_path, index=False)

    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA raw")
    _load_table(con, "widgets", csv_path, batch_id="batch-1")
    hash_from_batch_1 = con.execute("SELECT record_hash FROM raw.widgets").fetchone()[0]

    _load_table(con, "widgets", csv_path, batch_id="batch-2")
    hash_from_batch_2 = con.execute("SELECT record_hash FROM raw.widgets").fetchone()[0]

    assert hash_from_batch_1 == hash_from_batch_2


@pytest.fixture(autouse=True, scope="module")
def _cleanup_sys_path():
    yield
    scripts_path = str(Path(__file__).resolve().parents[2] / "scripts")
    if scripts_path in sys.path:
        sys.path.remove(scripts_path)
