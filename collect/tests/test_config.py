from pathlib import Path

import pytest

from collect.config import Settings


@pytest.fixture
def isolated_environment(monkeypatch):
    monkeypatch.setattr("collect.config.load_dotenv", lambda: False)
    for name in (
        "GCP_PROJECT_ID",
        "GCS_BUCKET",
        "BQ_RAW_DATASET",
        "GCS_PREFIX",
        "READY_DIR",
        "MANIFEST_PATH",
        "LOG_PATH",
    ):
        monkeypatch.delenv(name, raising=False)


def test_from_env_requires_project_and_bucket(isolated_environment):
    with pytest.raises(ValueError, match="GCP_PROJECT_ID, GCS_BUCKET"):
        Settings.from_env()


def test_from_env_uses_defaults_and_normalizes_prefix(
    isolated_environment, monkeypatch
):
    monkeypatch.setenv("GCP_PROJECT_ID", "project-123")
    monkeypatch.setenv("GCS_BUCKET", "project-123-lake")
    monkeypatch.setenv("GCS_PREFIX", " /sample/// ")

    settings = Settings.from_env()

    assert settings.raw_dataset == "gastroflow_raw"
    assert settings.gcs_prefix == "sample/"
    assert settings.ready_dir == Path("data/ready")
    assert settings.manifest_path == Path("logs/manifest.json")
    assert settings.log_path == Path("logs/ingestion_log.jsonl")


def test_paths_and_cloud_ids_use_shared_settings(isolated_environment, monkeypatch):
    monkeypatch.setenv("GCP_PROJECT_ID", "project-123")
    monkeypatch.setenv("GCS_BUCKET", "project-123-lake")

    settings = Settings.from_env()

    assert settings.gcs_prefix == "raw/"
    assert settings.object_name("orders") == "raw/orders/orders.csv"
    assert settings.gcs_uri("orders") == "gs://project-123-lake/raw/orders/orders.csv"
    assert settings.local_csv("orders") == Path("data/ready/orders.csv")
    assert settings.table_id("orders") == "project-123.gastroflow_raw.orders"


def test_unknown_tables_are_rejected(isolated_environment, monkeypatch):
    monkeypatch.setenv("GCP_PROJECT_ID", "project-123")
    monkeypatch.setenv("GCS_BUCKET", "project-123-lake")
    settings = Settings.from_env()

    with pytest.raises(ValueError, match="Unknown table: other"):
        settings.object_name("other")
