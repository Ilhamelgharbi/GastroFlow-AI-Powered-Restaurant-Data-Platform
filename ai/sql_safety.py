"""Guard rails for LLM-generated SQL (pure Python, easy to test)."""

from __future__ import annotations

import re

MARTS_DATASET = "gastroflow_marts"

# Whole-word matches only, so column names like "updated_at" are not blocked.
FORBIDDEN = (
    "drop", "delete", "truncate", "alter", "update", "insert", "merge",
    "create", "grant", "revoke", "call", "execute", "export", "load",
    "declare", "begin", "email", "password",
)
BLOCKED_DATASETS = (
    "gastroflow_raw", "gastroflow_staging", "gastroflow_snapshots",
    "gastroflow_ai", "information_schema",
)


def strip_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return re.sub(r"--[^\n]*", " ", sql)


def clean_sql(sql: str) -> str:
    """Remove comments, trailing semicolons and surrounding whitespace."""
    return strip_comments(sql).strip().rstrip(";").strip()


def is_safe(sql: str) -> tuple[bool, str]:
    """Return (ok, reason). Only one read-only SELECT/WITH over the marts."""
    cleaned = clean_sql(sql)
    lowered = cleaned.lower()

    if not lowered:
        return False, "Empty query."
    if not (lowered.startswith("select") or lowered.startswith("with")):
        return False, "Only SELECT queries are allowed."
    if ";" in cleaned:
        return False, "Only one statement is allowed."

    for word in FORBIDDEN:
        if re.search(rf"\b{word}\b", lowered):
            return False, f"Forbidden keyword: {word}"
    for dataset in BLOCKED_DATASETS:
        if dataset in lowered:
            return False, f"Dataset not allowed: {dataset}"

    # Any fully-qualified `project.dataset.table` must point at the marts.
    for ref in re.findall(r"`([^`]+)`", cleaned):
        if "." in ref and MARTS_DATASET not in ref.lower():
            return False, f"Only {MARTS_DATASET} tables are allowed."
    return True, "ok"
