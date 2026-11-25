"""CSV row-count helpers using DuckDB without loading entire files into memory."""

from pathlib import Path

import duckdb


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