from unittest.mock import Mock

import pytest

from collect.lib.gcs import (
    UPLOAD_CHUNK_SIZE_BYTES,
    UPLOAD_TIMEOUT_SECONDS,
    make_client,
    upload_file,
)


def test_make_client_uses_project_and_default_credentials(monkeypatch):
    client = Mock()
    constructor = Mock(return_value=client)
    monkeypatch.setattr("collect.lib.gcs.storage.Client", constructor)

    assert make_client("project-123") is client
    constructor.assert_called_once_with(project="project-123")


def test_upload_file_uploads_to_bucket_and_returns_size(tmp_path):
    path = tmp_path / "food.csv"
    path.write_bytes(b"f_id,item\n1,meal\n")
    client = Mock()

    size_bytes = upload_file(client, "lake-bucket", path, "raw/food/food.csv")

    assert size_bytes == path.stat().st_size
    client.bucket.assert_called_once_with("lake-bucket")
    client.bucket.return_value.blob.assert_called_once_with("raw/food/food.csv")
    blob = client.bucket.return_value.blob.return_value
    assert blob.chunk_size == UPLOAD_CHUNK_SIZE_BYTES
    blob.upload_from_filename.assert_called_once()
    upload_args, upload_kwargs = blob.upload_from_filename.call_args
    assert upload_args == (str(path),)
    assert upload_kwargs["timeout"] == UPLOAD_TIMEOUT_SECONDS
    assert upload_kwargs["retry"].deadline == UPLOAD_TIMEOUT_SECONDS


def test_upload_file_propagates_upload_errors(tmp_path):
    path = tmp_path / "food.csv"
    path.write_text("f_id,item\n1,meal\n", encoding="utf-8")
    blob = Mock()
    blob.upload_from_filename.side_effect = OSError("upload failed")
    client = Mock()
    client.bucket.return_value.blob.return_value = blob

    with pytest.raises(OSError, match="upload failed"):
        upload_file(client, "lake-bucket", path, "raw/food/food.csv")
