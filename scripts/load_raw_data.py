#!/usr/bin/env python
"""Load seed CSVs and generated CSVs into DuckDB's `raw` schema.

Preserves source fields with minimal modification (per the project spec's
raw-layer design) and adds load metadata: `loaded_at`, `source_file`,
`batch_id` (one UUID per run of this script, shared across every table
loaded), and `record_hash` (an md5 of the original column values, before
metadata is added — a change/dedup signal, not affected by re-running
the loader with the same source data).

Usage:
    uv run python scripts/load_raw_data.py
"""

from __future__ import annotations

import hashlib
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd

from restaurant_ops.config import DATABASE_PATH, RAW_DIR, SEED_DIR
from restaurant_ops.logging_config import get_logger

logger = get_logger(__name__)

_RAW_SCHEMA = "raw"

_SEED_TABLES = {
    "menu_items": SEED_DIR / "menu_items.csv",
    "ingredients": SEED_DIR / "ingredients.csv",
    "suppliers": SEED_DIR / "suppliers.csv",
    "recipes": SEED_DIR / "recipes.csv",
    "employees": SEED_DIR / "employees.csv",
}
_GENERATED_TABLES = {
    "daily_context": RAW_DIR / "daily_context.csv",
    "orders": RAW_DIR / "orders.csv",
    "order_items": RAW_DIR / "order_items.csv",
    "reviews": RAW_DIR / "reviews.csv",
    "employee_shifts": RAW_DIR / "employee_shifts.csv",
    "inventory_movements": RAW_DIR / "inventory_movements.csv",
}


def _row_hash(row: pd.Series) -> str:
    return hashlib.md5("|".join(str(v) for v in row.to_numpy()).encode()).hexdigest()


def _load_table(
    con: duckdb.DuckDBPyConnection, table_name: str, csv_path: Path, batch_id: str
) -> int:
    df = pd.read_csv(csv_path)
    df["record_hash"] = df.apply(_row_hash, axis=1)
    df["loaded_at"] = datetime.now(UTC)
    df["source_file"] = csv_path.name
    df["batch_id"] = batch_id

    con.execute(f"CREATE OR REPLACE TABLE {_RAW_SCHEMA}.{table_name} AS SELECT * FROM df")
    return len(df)


def main() -> int:
    all_tables = {**_SEED_TABLES, **_GENERATED_TABLES}
    missing = [str(path) for path in all_tables.values() if not path.exists()]
    if missing:
        print("Missing source files, run the generator first:", file=sys.stderr)
        for path in missing:
            print(f"  {path}", file=sys.stderr)
        return 1

    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    batch_id = str(uuid.uuid4())
    logger.info("Loading raw tables into %s (batch_id=%s)", DATABASE_PATH, batch_id)

    con = duckdb.connect(str(DATABASE_PATH))
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {_RAW_SCHEMA}")

    total_rows = 0
    for table_name, csv_path in all_tables.items():
        row_count = _load_table(con, table_name, csv_path, batch_id)
        total_rows += row_count
        print(f"Loaded {row_count:,} rows into {_RAW_SCHEMA}.{table_name}")
    con.close()

    print(f"DuckDB load completed: {len(all_tables)} tables, {total_rows:,} total rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
