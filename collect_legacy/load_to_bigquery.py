"""Load selected GCS CSVs into BigQuery RAW and compare row counts.

Run with ``python -m collect.load_to_bigquery``. Use ``--tables`` to select a
subset, for example ``--tables orders reviews``.
"""

import argparse
import json

from google.cloud import bigquery

from collect.config import Settings
from collect.lib import bq, run_log, validation
from collect.schemas import RAW_COLUMNS, TABLES


def load_table(
    table: str,
    settings: Settings,
    client: bigquery.Client,
    run_id: str,
) -> dict[str, object]:
    """Validate and load one table, recording whether its row count matches."""
    local_path = settings.local_csv(table)
    validation.assert_no_sensitive_columns(local_path)
    validation.assert_matches_schema(table, local_path)
    expected_rows = validation.count_rows(local_path)

    load_result = bq.load_csv_from_gcs(
        client,
        settings.gcs_uri(table),
        settings.table_id(table),
        RAW_COLUMNS[table],
    )
    rows_loaded = load_result["rows_loaded"]
    status = "ok" if rows_loaded == expected_rows else "row_count_mismatch"
    event: dict[str, object] = {
        "run_id": run_id,
        "table": table,
        "status": status,
        "expected_rows": expected_rows,
        **load_result,
    }
    run_log.append_event(settings.log_path, event)
    print(json.dumps(event, sort_keys=True))
    return event


def main(argv: list[str] | None = None) -> int:
    """Load selected tables, log per-table failures, and return a failure code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tables",
        nargs="+",
        choices=TABLES,
        help="Tables to load; defaults to all raw tables.",
    )
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    client = bq.make_client(settings.project_id)
    run_id = run_log.new_run_id()
    failures = 0

    for table in args.tables or TABLES:
        try:
            event = load_table(table, settings, client, run_id)
            if event["status"] != "ok":
                failures += 1
        except Exception as exc:  # noqa: BLE001 - log this table and continue the batch.
            failures += 1
            event = {
                "run_id": run_id,
                "table": table,
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
            }
            run_log.append_event(settings.log_path, event)
            print(json.dumps(event, sort_keys=True))

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
