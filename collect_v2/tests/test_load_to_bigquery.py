from pathlib import Path
from unittest.mock import Mock

from collect.config import Settings
from collect_v2.load_to_bigquery import load_table, main
from collect_v2.schemas import RAW_COLUMNS


def test_load_table_uses_original_header_order_and_string_schema(tmp_path, monkeypatch):
    import collect_v2.load_to_bigquery as loader

    directory = tmp_path / "data" / "sample"
    source = directory / "users" / "users.csv"
    source.parent.mkdir(parents=True)
    source.write_text(
        ",user_id,name,email,password,Age,Gender,Marital Status,Occupation,"
        "Monthly Income,Educational Qualifications,Family size\n"
        "0,1,Mock User,mock@example.test,dummy-password,30,Other,Single,"
        "Analyst,Band,College,2\n",
        encoding="utf-8",
    )
    settings = Settings(
        project_id="project-123",
        bucket="project-123-lake",
        raw_dataset="gastroflow_raw",
        gcs_prefix="raw/",
        ready_dir=Path("unused"),
        manifest_path=Path("unused"),
        log_path=Path("unused"),
    )
    load = Mock(return_value={"job_id": "job-1", "rows_loaded": 1, "bytes": 128})
    monkeypatch.setattr(loader, "load_csv_from_gcs", load)

    assert load_table("users", directory, settings, Mock())
    args = load.call_args.args
    assert args[1:] == (
        "gs://project-123-lake/raw/users/users.csv",
        "project-123.gastroflow_raw.users",
        RAW_COLUMNS["users"],
    )


def test_main_accepts_directory_argument(tmp_path, monkeypatch):
    import collect_v2.load_to_bigquery as loader

    directory = tmp_path / "sample"
    source = directory / "food" / "food.csv"
    source.parent.mkdir(parents=True)
    source.write_text(",f_id,item,veg_or_non_veg\n0,f1,Meal,Veg\n", encoding="utf-8")
    settings = Settings(
        project_id="project-123",
        bucket="project-123-lake",
        raw_dataset="gastroflow_raw",
        gcs_prefix="raw/",
        ready_dir=tmp_path / "ready",
        manifest_path=tmp_path / "manifest.json",
        log_path=tmp_path / "log.jsonl",
    )
    monkeypatch.setattr(loader.Settings, "from_env", Mock(return_value=settings))
    monkeypatch.setattr(loader, "make_client", Mock(return_value=Mock()))
    monkeypatch.setattr(
        loader,
        "load_csv_from_gcs",
        Mock(return_value={"job_id": "job-1", "rows_loaded": 1, "bytes": 128}),
    )

    assert main(["--directory", str(directory), "--tables", "food"]) == 0
