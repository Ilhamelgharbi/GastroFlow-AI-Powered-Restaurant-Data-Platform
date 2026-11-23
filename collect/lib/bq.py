"""Thin wrapper over google-cloud-bigquery load jobs. No table-specific knowledge."""

from google.cloud import bigquery


def make_client(project_id: str) -> bigquery.Client:
    """Create a BigQuery client using Application Default Credentials."""
    return bigquery.Client(project=project_id)


def load_csv_from_gcs(
    client: bigquery.Client, uri: str, table_id: str, columns: list[str]
) -> dict[str, str | int | None]:
    """Load one CSV from GCS into a table and wait for the job.

    Config: all columns STRING (explicit schema, no autodetect), skip 1 header row,
    allow quoted newlines, max_bad_records=0, WRITE_TRUNCATE (full reload).
    Return {'job_id': ..., 'rows_loaded': ..., 'bytes': ...}; raise on job error.
    """
    job = client.load_table_from_uri(
        uri,
        table_id,
        job_config=bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.CSV,
            schema=[bigquery.SchemaField(column, "STRING") for column in columns],
            autodetect=False,
            skip_leading_rows=1,
            allow_quoted_newlines=True,
            max_bad_records=0,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        ),
    )
    job.result()
    rows_loaded = client.get_table(table_id).num_rows

    return {
        "job_id": job.job_id,
        "rows_loaded": rows_loaded,
        "bytes": job.output_bytes,
    }
