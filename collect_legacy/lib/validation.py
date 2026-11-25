"""Pre-flight checks on local CSVs, using DuckDB (no full file load into memory).

Used by BOTH the uploader and the loader, so the privacy rule and the
schema check live in one place.
"""

import csv
from pathlib import Path

import duckdb

from collect.schemas import FORBIDDEN_COLUMNS, RAW_COLUMNS


def csv_columns(path: Path) -> list[str]:
    """Return the header names of a CSV, read as text, lower-cased and stripped."""
    _require_csv(path)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        columns = next(csv.reader(stream), None)

    if not columns or any(not column.strip() for column in columns):
        raise ValueError(f"CSV has an empty or invalid header: {path}")

    return [column.strip().lower() for column in columns]


def assert_no_sensitive_columns(path: Path) -> None:
    """Raise ValueError if the CSV header contains any FORBIDDEN_COLUMNS name.

    This is the last line of defence before a file leaves the laptop.
    """
    forbidden = FORBIDDEN_COLUMNS.intersection(csv_columns(path))
    if forbidden:
        names = ", ".join(sorted(forbidden))
        raise ValueError(f"{path}: forbidden column(s): {names}")


def assert_matches_schema(table: str, path: Path) -> None:
    """Raise ValueError if the CSV column count differs from RAW_COLUMNS[table].

    Columns are matched by position, so a count mismatch means a wrong load.
    """
    if table not in RAW_COLUMNS:
        raise ValueError(f"Unknown table: {table}")

    actual_count = len(csv_columns(path))
    expected_count = len(RAW_COLUMNS[table])
    if actual_count != expected_count:
        raise ValueError(
            f"{path}: {table} has {actual_count} columns; "
            f"the RAW schema expects {expected_count}"
        )


def count_rows(path: Path) -> int:
    """Return the number of data rows (header excluded), counted with DuckDB.

    Quoted multi-line values (long reviews) must count as ONE row.
    """
    _require_csv(path)
    connection = duckdb.connect()
    try:
        result = connection.execute(
            "SELECT count(*) FROM read_csv(?, header=true, all_varchar=true, sample_size=-1)",
            [str(path)],
        ).fetchone()
    finally:
        connection.close()

    if result is None:
        raise RuntimeError(f"DuckDB returned no row count for {path}")
    return int(result[0])


def _require_csv(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"CSV file not found: {path}")
