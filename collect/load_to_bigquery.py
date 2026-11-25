"""Load original GCS CSVs into BigQuery RAW without changing cell values.

Example: python -m collect.load_to_bigquery --tables food users
"""

import argparse
from pathlib import Path

from google.cloud import bigquery

from collect.config import Settings
from collect.lib.bq import load_csv_from_gcs, make_client
from collect.lib.validation import count_rows
from collect.schemas import (
    RAW_COLUMNS,
    TABLES,
    assert_source_header,
    source_csv_path,
)


def load_table(
    table: str,
    directory: Path,
    settings: Settings,
    client: bigquery.Client,
) -> bool:
    """Load one source CSV as STRING fields and compare its row count."""
    path = source_csv_path(directory, table)
    assert_source_header(table, path)
    expected_rows = count_rows(path)
    result = load_csv_from_gcs(
        client,
        settings.gcs_uri(table),
        settings.table_id(table),
        RAW_COLUMNS[table],
    )

    rows_loaded = result["rows_loaded"]
    if rows_loaded != expected_rows:
        print(f"ERROR {table}: loaded {rows_loaded} rows; expected {expected_rows}")
        return False

    print(f"Loaded {table}: {rows_loaded:,} rows into {settings.table_id(table)}")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("data/sample"))
    parser.add_argument(
        "--tables",
        nargs="+",
        choices=TABLES,
        help="Tables to load; defaults to all seven.",
    )
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    client = make_client(settings.project_id)
    failures = 0

    for table in args.tables or TABLES:
        try:
            if not load_table(table, args.directory, settings, client):
                failures += 1
        except Exception as exc:  # noqa: BLE001 - report this table and continue.
            failures += 1
            print(f"ERROR {table}: {type(exc).__name__}: {exc}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
