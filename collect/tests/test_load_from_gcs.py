from unittest.mock import Mock

import pytest

import collect.load_from_gcs as loader
from collect.schemas import RAW_COLUMNS


def test_load_table_from_gcs_uses_configured_prefix_and_schema(monkeypatch):
    client = Mock()
    result = {"job_id": "job-1", "rows_loaded": 12, "bytes": 256}
    make_client = Mock(return_value=client)
    load = Mock(return_value=result)
    monkeypatch.setattr(loader, "make_client", make_client)
    monkeypatch.setattr(loader, "load_csv_from_gcs", load)

    assert loader.load_table_from_gcs(
        "food",
        "project-123",
        "project-123-lake",
        "/landing/raw/",
        "gastroflow_raw",
    ) == result

    make_client.assert_called_once_with("project-123")
    load.assert_called_once_with(
        client,
        "gs://project-123-lake/landing/raw/food/food.csv",
        "project-123.gastroflow_raw.food",
        RAW_COLUMNS["food"],
    )


def test_load_table_from_gcs_rejects_unknown_table_before_client_creation(
    monkeypatch,
):
    make_client = Mock()
    monkeypatch.setattr(loader, "make_client", make_client)

    with pytest.raises(ValueError, match="Unknown table"):
        loader.load_table_from_gcs(
            "unknown", "project-123", "bucket", "raw/", "gastroflow_raw"
        )

    make_client.assert_not_called()


def test_load_table_from_gcs_requires_cloud_settings():
    with pytest.raises(ValueError, match="bucket"):
        loader.load_table_from_gcs(
            "food", "project-123", " ", "raw/", "gastroflow_raw"
        )
