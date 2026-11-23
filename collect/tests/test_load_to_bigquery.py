import json
from pathlib import Path
from unittest.mock import Mock

from collect.config import Settings
from collect.load_to_bigquery import load_table, main
from collect.schemas import RAW_COLUMNS


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        project_id="project-123",
        bucket="project-123-lake",
        raw_dataset="gastroflow_raw",
        gcs_prefix="raw/",
        ready_dir=tmp_path / "ready",
        manifest_path=tmp_path / "logs" / "manifest.json",
        log_path=tmp_path / "logs" / "ingestion.jsonl",
    )


def write_food_csv(settings: Settings) -> Path:
    settings.ready_dir.mkdir(parents=True, exist_ok=True)
    path = settings.local_csv("food")
    path.write_text(
        "f_id,item,veg_or_non_veg\nf1,meal,Veg\nf2,soup,Non-Veg\n",
        encoding="utf-8",
    )
    return path


def test_load_table_validates_loads_and_logs_row_count(tmp_path, monkeypatch):
    import collect.load_to_bigquery as loader

    settings = make_settings(tmp_path)
    write_food_csv(settings)
    client = Mock()
    load = Mock(return_value={"job_id": "job-1", "rows_loaded": 2, "bytes": 64})
    monkeypatch.setattr(loader.bq, "load_csv_from_gcs", load)

    event = load_table("food", settings, client, "run-1")

    load.assert_called_once_with(
        client,
        "gs://project-123-lake/raw/food/food.csv",
        "project-123.gastroflow_raw.food",
        RAW_COLUMNS["food"],
    )
    assert event["status"] == "ok"
    assert event["expected_rows"] == 2
    logged = json.loads(settings.log_path.read_text(encoding="utf-8").splitlines()[0])
    assert logged["status"] == "ok"


def test_load_table_reports_row_count_mismatch(tmp_path, monkeypatch):
    import collect.load_to_bigquery as loader

    settings = make_settings(tmp_path)
    write_food_csv(settings)
    monkeypatch.setattr(
        loader.bq,
        "load_csv_from_gcs",
        Mock(return_value={"job_id": "job-2", "rows_loaded": 1, "bytes": 32}),
    )

    event = load_table("food", settings, Mock(), "run-2")

    assert event["status"] == "row_count_mismatch"
    assert event["expected_rows"] == 2


def test_main_returns_failure_for_row_count_mismatch(tmp_path, monkeypatch):
    import collect.load_to_bigquery as loader

    settings = make_settings(tmp_path)
    monkeypatch.setattr(
        loader.Settings,
        "from_env",
        Mock(return_value=settings),
    )
    monkeypatch.setattr(loader.bq, "make_client", Mock(return_value=Mock()))
    monkeypatch.setattr(
        loader,
        "load_table",
        Mock(return_value={"table": "food", "status": "row_count_mismatch"}),
    )

    assert main(["--tables", "food"]) == 1
