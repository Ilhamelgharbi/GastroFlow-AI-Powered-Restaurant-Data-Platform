import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from collect.config import Settings
from collect.lib.manifest import Manifest, sha256_file
from collect.upload_to_gcs import main, upload_table


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


def write_food_csv(
    settings: Settings, header: str = "f_id,item,veg_or_non_veg"
) -> Path:
    settings.ready_dir.mkdir(parents=True, exist_ok=True)
    path = settings.local_csv("food")
    path.write_text(f"{header}\nf1,meal,Veg\n", encoding="utf-8")
    return path


def test_upload_table_validates_uploads_and_records_manifest(tmp_path, monkeypatch):
    settings = make_settings(tmp_path)
    path = write_food_csv(settings)
    manifest = Manifest(settings.manifest_path)
    client = Mock()
    upload = Mock(return_value=path.stat().st_size)
    monkeypatch.setattr("collect.upload_to_gcs.gcs.upload_file", upload)

    status = upload_table("food", settings, client, manifest, "run-1")

    assert status == "uploaded"
    upload.assert_called_once_with(client, settings.bucket, path, "raw/food/food.csv")
    assert manifest.is_unchanged("food", sha256_file(path))
    event = json.loads(settings.log_path.read_text(encoding="utf-8").splitlines()[0])
    assert event["status"] == "uploaded"
    assert event["gcs_uri"] == "gs://project-123-lake/raw/food/food.csv"


def test_upload_table_skips_unchanged_file(tmp_path, monkeypatch):
    settings = make_settings(tmp_path)
    path = write_food_csv(settings)
    manifest = Manifest(settings.manifest_path)
    manifest.record("food", sha256_file(path))
    upload = Mock()
    monkeypatch.setattr("collect.upload_to_gcs.gcs.upload_file", upload)

    status = upload_table("food", settings, Mock(), manifest, "run-2")

    assert status == "unchanged"
    upload.assert_not_called()


def test_upload_table_rejects_sensitive_columns_before_upload(tmp_path, monkeypatch):
    settings = make_settings(tmp_path)
    write_food_csv(settings, "f_id,email,veg_or_non_veg")
    upload = Mock()
    monkeypatch.setattr("collect.upload_to_gcs.gcs.upload_file", upload)

    with pytest.raises(ValueError, match="forbidden column"):
        upload_table(
            "food", settings, Mock(), Manifest(settings.manifest_path), "run-3"
        )

    upload.assert_not_called()


def test_main_continues_after_table_failure_and_returns_failure(tmp_path, monkeypatch):
    import collect.upload_to_gcs as uploader

    settings = make_settings(tmp_path)
    monkeypatch.setattr(
        uploader.Settings,
        "from_env",
        Mock(return_value=settings),
    )
    monkeypatch.setattr(uploader.gcs, "make_client", Mock(return_value=Mock()))
    processed = []

    def upload_selected_table(table, *_args):
        processed.append(table)
        if table == "orders":
            raise RuntimeError("simulated failure")
        return "uploaded"

    monkeypatch.setattr(uploader, "upload_table", upload_selected_table)

    assert main(["--tables", "orders", "reviews"]) == 1
    assert processed == ["orders", "reviews"]
    records = [
        json.loads(line)
        for line in settings.log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(records) == 1
    assert records[0]["table"] == "orders"
    assert records[0]["status"] == "error"
