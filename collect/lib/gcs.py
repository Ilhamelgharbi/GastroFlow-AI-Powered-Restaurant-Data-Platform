"""Thin wrapper over google-cloud-storage. Knows nothing about tables or manifests."""

from pathlib import Path

from google.cloud import storage


def make_client(project_id: str) -> storage.Client:
    """Create a client that authenticates with Application Default Credentials.

    Never use a downloaded JSON key file.
    """
    return storage.Client(project=project_id)


def upload_file(
    client: storage.Client, bucket: str, local_path: Path, object_name: str
) -> int:
    """Upload one file and return its size in bytes.

    Use resumable uploads (the library default for large files) and let the
    library raise on failure; callers decide how to log it.
    """
    size_bytes = local_path.stat().st_size
    blob = client.bucket(bucket).blob(object_name)
    blob.upload_from_filename(str(local_path))
    return size_bytes
