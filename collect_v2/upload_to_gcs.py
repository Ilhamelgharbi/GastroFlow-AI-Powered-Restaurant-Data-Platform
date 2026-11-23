"""Upload original CSV files from data/sample to the configured GCS bucket.

Example: python -m collect_v2.upload_to_gcs --tables food users
"""

import argparse
from pathlib import Path

from google.cloud import storage

from collect.config import Settings
from collect.lib.gcs import make_client, upload_file
from collect_v2.schemas import TABLES, assert_source_header, source_csv_path


def upload_table(
    table: str, directory: Path, settings: Settings, client: storage.Client
) -> int:
    """Upload one original CSV without changing its bytes or header."""
    path = source_csv_path(directory, table)
    assert_source_header(table, path)
    size_bytes = upload_file(
        client,
        settings.bucket,
        path,
        settings.object_name(table),
    )
    print(f"Uploaded {table}: {size_bytes:,} bytes to {settings.gcs_uri(table)}")
    return size_bytes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("data/sample"))
    parser.add_argument(
        "--tables",
        nargs="+",
        choices=TABLES,
        help="Tables to upload; defaults to all seven.",
    )
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    client = make_client(settings.project_id)
    failures = 0

    for table in args.tables or TABLES:
        try:
            upload_table(table, args.directory, settings, client)
        except Exception as exc:  # noqa: BLE001 - report this table and continue.
            failures += 1
            print(f"ERROR {table}: {type(exc).__name__}: {exc}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
