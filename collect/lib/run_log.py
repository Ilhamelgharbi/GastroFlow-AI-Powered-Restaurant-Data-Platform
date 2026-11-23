"""Append-only JSON-lines log: one event per table per run, auditable later."""

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path


def new_run_id() -> str:
    """Return a sortable UTC run id such as '20261123T101500Z'."""
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def append_event(path: Path, event: Mapping[str, object]) -> None:
    """Add a timestamp to the event, append it as one JSON line, create folders if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    record = dict(event)
    record["timestamp"] = (
        datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    )
    with path.open("a", encoding="utf-8", newline="\n") as log:
        log.write(json.dumps(record, sort_keys=True))
        log.write("\n")
