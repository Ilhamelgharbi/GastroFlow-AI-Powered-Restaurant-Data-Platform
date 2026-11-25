"""File fingerprints: detect unchanged files so they are never uploaded twice."""

import hashlib
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    """Return the hex SHA-256 of a file, reading it in chunks.

    Chunked reading keeps memory flat even for the 1+ GB orders file.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")

    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Manifest:
    """Small JSON file mapping table -> last uploaded fingerprint and metadata."""

    def __init__(self, path: Path) -> None:
        """Load the manifest if the file exists, otherwise start empty."""
        self.path = path
        self.entries: dict[str, dict[str, object]] = {}

        if not self.path.exists():
            return

        loaded = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise TypeError(f"Manifest must contain a JSON object: {self.path}")

        for table, entry in loaded.items():
            if (
                not isinstance(table, str)
                or not isinstance(entry, dict)
                or not isinstance(entry.get("sha256"), str)
                or any(not isinstance(key, str) for key in entry)
            ):
                raise ValueError(f"Invalid manifest entry for table {table!r}")
            self.entries[table] = {key: value for key, value in entry.items()}

    def is_unchanged(self, table: str, digest: str) -> bool:
        """True when this table was already uploaded with the same digest."""
        entry = self.entries.get(table)
        return entry is not None and entry.get("sha256") == digest

    def record(self, table: str, digest: str, **metadata) -> None:
        """Store digest plus metadata (bytes, gcs_uri, run_id, uploaded_at)."""
        if "sha256" in metadata:
            raise ValueError("'sha256' is reserved manifest metadata")

        entry: dict[str, object] = dict(metadata)
        entry["sha256"] = digest
        entry.setdefault(
            "uploaded_at",
            datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        )
        self.entries[table] = entry

    def save(self) -> None:
        """Write the manifest to disk (create parent folders if needed)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                json.dump(self.entries, temporary, indent=2, sort_keys=True)
                temporary.write("\n")

            os.replace(temporary_path, self.path)
            temporary_path = None
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
