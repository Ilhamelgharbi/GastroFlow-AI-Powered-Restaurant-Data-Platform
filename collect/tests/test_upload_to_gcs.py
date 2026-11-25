from pathlib import Path
from unittest.mock import Mock

from collect.config import Settings
from collect.upload_to_gcs import main, upload_table


def test_upload_table_uses_original_source_file(tmp_path, monkeypatch):
    directory = tmp_path / "data" / "sample"
    source = directory / "users" / "users.csv"
    source.parent.mkdir(parents=True)
    original_bytes = (
        b",user_id,name,email,password,Age,Gender,Marital Status,Occupation,"
        b"Monthly Income,Educational Qualifications,Family size\r\n"
        b"0,1,Mock User,mock@example.test,dummy-password,30,Other,Single,"
        b"Analyst,Band,College,2\r\n"
    )
    source.write_bytes(original_bytes)
    settings = Settings(
        project_id="project-123",
        bucket="project-123-lake",
        raw_dataset="gastroflow_raw",
        gcs_prefix="raw/",
        ready_dir=Path("unused"),
        manifest_path=Path("unused"),
        log_path=Path("unused"),
    )
    client = Mock()
    upload = Mock(return_value=len(original_bytes))

    import collect.upload_to_gcs as uploader

    monkeypatch.setattr(uploader, "upload_file", upload)
    result = upload_table("users", directory, settings, client)

    assert result == len(original_bytes)
    upload.assert_called_once_with(
        client, "project-123-lake", source, "raw/users/users.csv"
    )
    assert source.read_bytes() == original_bytes


def test_main_accepts_directory_argument(tmp_path, monkeypatch):
    import collect.upload_to_gcs as uploader

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
    monkeypatch.setattr(uploader.Settings, "from_env", Mock(return_value=settings))
    monkeypatch.setattr(uploader, "make_client", Mock(return_value=Mock()))
    monkeypatch.setattr(
        uploader, "upload_file", Mock(return_value=source.stat().st_size)
    )

    assert main(["--directory", str(directory), "--tables", "food"]) == 0
