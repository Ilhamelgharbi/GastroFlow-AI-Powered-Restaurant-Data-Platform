"""Upload sanitized CSVs to GCS, skipping files with unchanged fingerprints.

Run with ``python -m collect.upload_to_gcs``. Use ``--tables`` to select a
subset, for example ``--tables orders reviews``.
"""

import argparse
import json

from google.cloud import storage

from collect.config import Settings
from collect.lib import gcs, run_log, validation
from collect.lib.manifest import Manifest, sha256_file
from collect.schemas import TABLES


def upload_table(
    table: str,
    settings: Settings,
    client: storage.Client,
    manifest: Manifest,
    run_id: str,
) -> str:
    """Validate, then upload one table unless its fingerprint is unchanged."""
    local_path = settings.local_csv(table)
    validation.assert_no_sensitive_columns(local_path)
    validation.assert_matches_schema(table, local_path)

    digest = sha256_file(local_path)
    gcs_uri = settings.gcs_uri(table)
    if manifest.is_unchanged(table, digest):
        status = "unchanged"
        size_bytes = local_path.stat().st_size
    else:
        size_bytes = gcs.upload_file(
            client,
            settings.bucket,
            local_path,
            settings.object_name(table),
        )
        manifest.record(
            table,
            digest,
            bytes=size_bytes,
            gcs_uri=gcs_uri,
            run_id=run_id,
        )
        status = "uploaded"

    event = {
        "run_id": run_id,
        "table": table,
        "status": status,
        "sha256": digest,
        "bytes": size_bytes,
        "gcs_uri": gcs_uri,
    }
    run_log.append_event(settings.log_path, event)
    print(json.dumps(event, sort_keys=True))
    return status


def main(argv: list[str] | None = None) -> int:
    """Upload selected tables, log per-table failures, and save the manifest."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tables",
        nargs="+",
        choices=TABLES,
        help="Tables to upload; defaults to all raw tables.",
    )
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    client = gcs.make_client(settings.project_id)
    manifest = Manifest(settings.manifest_path)
    run_id = run_log.new_run_id()
    failures = 0

    for table in args.tables or TABLES:
        try:
            upload_table(table, settings, client, manifest, run_id)
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

    manifest.save()
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
