import json
import re
from datetime import datetime

from collect.lib.run_log import append_event, new_run_id


def test_new_run_id_is_utc_and_sortable():
    run_id = new_run_id()

    assert re.fullmatch(r"\d{8}T\d{6}Z", run_id)
    datetime.strptime(run_id, "%Y%m%dT%H%M%SZ")


def test_append_event_creates_parent_and_appends_json_lines(tmp_path):
    path = tmp_path / "logs" / "ingestion.jsonl"
    event = {"table": "orders", "status": "ok"}

    append_event(path, event)
    append_event(path, {"table": "reviews", "status": "error"})

    records = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(records) == 2
    assert records[0]["table"] == "orders"
    assert records[1]["table"] == "reviews"
    assert all(record["timestamp"].endswith("Z") for record in records)
    assert "timestamp" not in event
