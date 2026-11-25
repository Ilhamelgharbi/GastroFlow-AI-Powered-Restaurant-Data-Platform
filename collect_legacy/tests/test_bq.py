from unittest.mock import Mock

import pytest
from google.cloud import bigquery

from collect.lib.bq import load_csv_from_gcs, make_client


def test_make_client_uses_project_and_default_credentials(monkeypatch):
    client = Mock()
    constructor = Mock(return_value=client)
    monkeypatch.setattr("collect.lib.bq.bigquery.Client", constructor)

    assert make_client("project-123") is client
    constructor.assert_called_once_with(project="project-123")


def test_load_csv_uses_explicit_string_schema_and_full_reload():
    client = Mock()
    job = Mock(job_id="job-123", output_bytes=1024)
    client.load_table_from_uri.return_value = job
    client.get_table.return_value.num_rows = 17
    columns = ["order_id", "order_timestamp"]

    result = load_csv_from_gcs(
        client,
        "gs://lake/raw/orders/orders.csv",
        "project-123.gastroflow_raw.orders",
        columns,
    )

    job_config = client.load_table_from_uri.call_args.kwargs["job_config"]
    assert client.load_table_from_uri.call_args.args == (
        "gs://lake/raw/orders/orders.csv",
        "project-123.gastroflow_raw.orders",
    )
    assert [field.name for field in job_config.schema] == columns
    assert all(field.field_type == "STRING" for field in job_config.schema)
    assert job_config.source_format == bigquery.SourceFormat.CSV
    assert job_config.autodetect is False
    assert job_config.skip_leading_rows == 1
    assert job_config.allow_quoted_newlines is True
    assert job_config.max_bad_records == 0
    assert job_config.write_disposition == bigquery.WriteDisposition.WRITE_TRUNCATE
    job.result.assert_called_once_with()
    client.get_table.assert_called_once_with("project-123.gastroflow_raw.orders")
    assert result == {"job_id": "job-123", "rows_loaded": 17, "bytes": 1024}


def test_load_job_errors_are_propagated():
    client = Mock()
    job = Mock()
    job.result.side_effect = RuntimeError("load failed")
    client.load_table_from_uri.return_value = job

    with pytest.raises(RuntimeError, match="load failed"):
        load_csv_from_gcs(client, "gs://lake/raw/food/food.csv", "p.raw.food", ["f_id"])

    client.get_table.assert_not_called()
