"""Load a configured source CSV from GCS into its BigQuery RAW table."""

from collect.lib.bq import load_csv_from_gcs, make_client
from collect.schemas import RAW_COLUMNS


def load_table_from_gcs(
    table: str,
    project_id: str,
    bucket: str,
    gcs_prefix: str,
    raw_dataset: str,
) -> dict[str, str | int | None]:
    """Load one known source table from GCS, replacing its RAW table."""
    if table not in RAW_COLUMNS:
        raise ValueError(f"Unknown table: {table}")

    required = {
        "project_id": project_id,
        "bucket": bucket,
        "raw_dataset": raw_dataset,
    }
    missing = [name for name, value in required.items() if not value.strip()]
    if missing:
        raise ValueError(f"Missing required setting(s): {', '.join(missing)}")

    prefix = gcs_prefix.strip("/")
    object_name = f"{prefix}/{table}/{table}.csv" if prefix else f"{table}/{table}.csv"
    uri = f"gs://{bucket}/{object_name}"
    table_id = f"{project_id}.{raw_dataset}.{table}"
    result = load_csv_from_gcs(
        make_client(project_id),
        uri,
        table_id,
        RAW_COLUMNS[table],
    )
    print(f"Loaded {table}: {result['rows_loaded']:,} rows into {table_id}")
    return result
