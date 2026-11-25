"""Single source of truth for settings and storage paths.

Every other module imports from here, so a bucket name, prefix or path is
defined exactly once. Nothing else in the package reads os.environ.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from collect.schemas import TABLES


@dataclass(frozen=True)
class Settings:
    """Immutable run settings, built once at program start."""

    project_id: str
    bucket: str
    raw_dataset: str
    gcs_prefix: str  # object prefix inside the bucket, e.g. "raw/"
    ready_dir: Path  # folder with the sanitized CSVs
    manifest_path: Path  # SHA-256 fingerprints of uploaded files
    log_path: Path  # JSON-lines run log

    @classmethod
    def from_env(cls) -> "Settings":
        """Read environment variables (after loading .env) and return Settings.

        Required: GCP_PROJECT_ID, GCS_BUCKET.
        Optional with defaults: BQ_RAW_DATASET=gastroflow_raw, GCS_PREFIX=raw/,
        READY_DIR=data/ready, MANIFEST_PATH=logs/manifest.json,
        LOG_PATH=logs/ingestion_log.jsonl.
        Fail fast with one clear error listing every missing required variable.
        """
        load_dotenv()

        required = {
            "GCP_PROJECT_ID": os.getenv("GCP_PROJECT_ID", "").strip(),
            "GCS_BUCKET": os.getenv("GCS_BUCKET", "").strip(),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            names = ", ".join(missing)
            raise ValueError(f"Missing required environment variable(s): {names}")

        prefix = (os.getenv("GCS_PREFIX", "").strip() or "raw/").strip("/")
        if prefix:
            prefix += "/"

        return cls(
            project_id=required["GCP_PROJECT_ID"],
            bucket=required["GCS_BUCKET"],
            raw_dataset=os.getenv("BQ_RAW_DATASET", "").strip() or "gastroflow_raw",
            gcs_prefix=prefix,
            ready_dir=Path(os.getenv("READY_DIR", "").strip() or "data/ready"),
            manifest_path=Path(
                os.getenv("MANIFEST_PATH", "").strip() or "logs/manifest.json"
            ),
            log_path=Path(
                os.getenv("LOG_PATH", "").strip() or "logs/ingestion_log.jsonl"
            ),
        )

    @staticmethod
    def _validate_table(table: str) -> None:
        if table not in TABLES:
            raise ValueError(f"Unknown table: {table}")

    def object_name(self, table: str) -> str:
        """Return the object path in the bucket: '<prefix><table>/<table>.csv'.

        The uploader and the loader both call this, so they can never disagree
        about where a file lives.
        """
        self._validate_table(table)
        return f"{self.gcs_prefix}{table}/{table}.csv"

    def gcs_uri(self, table: str) -> str:
        """Return 'gs://<bucket>/<object_name(table)>'."""
        return f"gs://{self.bucket}/{self.object_name(table)}"

    def local_csv(self, table: str) -> Path:
        """Return the path of the sanitized local CSV for a table."""
        self._validate_table(table)
        return self.ready_dir / f"{table}.csv"

    def table_id(self, table: str) -> str:
        """Return the fully qualified BigQuery id '<project>.<raw_dataset>.<table>'."""
        self._validate_table(table)
        return f"{self.project_id}.{self.raw_dataset}.{table}"
