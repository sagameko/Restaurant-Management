# Development log

Meaningful development decisions and problems encountered while building
the platform, in the format recommended by the project spec.

## 2026-07-22

Problem:
`MenuItem.model_validate` raised a `ValidationError` on `source_url` even
though the CSV loader replaced missing cells with `None` via
`df.where(pd.notnull(df), None)`.

Cause:
`pandas.read_csv(..., dtype=str)` on pandas >= 3.0 produces columns backed
by the new `StringDtype`, not plain `object`. Assigning `None` into a
`StringDtype` column via `.where` silently keeps the missing value as
`NaN` (a Python `float`) instead of `None`, so Pydantic saw a float where
`str | None` was expected.

Resolution:
Cast the DataFrame to `object` dtype (`.astype(object)`) before calling
`.where(pd.notnull(df), None)` in `restaurant_ops.ingestion.loader._read_seed_csv`.
This forces missing cells to become real `None` values that Pydantic
accepts for optional fields.

Lesson:
Don't assume `dtype=str` in pandas behaves like plain Python strings —
on pandas 3.x it opts into `StringDtype`, which has different null
semantics. Cast to `object` explicitly whenever downstream code
(here, Pydantic validation) needs `None` rather than pandas' native NA
marker.
