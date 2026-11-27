"""Enrich review comments with sentiment / topic / key issue (Gemini on Vertex AI).

Why it is cheap: reviews repeat a lot. The data audit found only 294 distinct
comments among 300,000 reviews. So we classify each DISTINCT comment once
(gastroflow_ai.comment_enrichment) and join the result back to every review
(gastroflow_ai.review_enriched, the table dbt reads as source('ai', ...)).

Run locally (needs `gcloud auth application-default login`):
    python -m ai.enrich_reviews --dry-run      # count + cost estimate, no LLM calls
    python -m ai.enrich_reviews --limit 20     # try 20 comments first
    python -m ai.enrich_reviews                # everything pending (capped)
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Literal, Optional

from google.cloud import bigquery
from pydantic import BaseModel

from ai import llm

TOPICS = ["food quality", "delivery", "pricing", "service", "packaging", "other"]
DEFAULT_MAX_COMMENTS = 2000  # safety cap per run (protects against surprise cost)
MAX_FAILURE_RATE = 0.2

SYSTEM_PROMPT = f"""You classify customer reviews for a food delivery app.

For the review you are given, return:
- sentiment_label: positive, negative, or neutral
- sentiment_score: a number between -1.0 (very negative) and 1.0 (very positive)
- topic: one of {TOPICS}
- key_issue: a short phrase of 6 words or less describing the main issue,
  or null if the review contains no issue
"""

SCHEMA_FIELDS = [
    bigquery.SchemaField("comment", "STRING"),
    bigquery.SchemaField("sentiment_label", "STRING"),
    bigquery.SchemaField("sentiment_score", "FLOAT64"),
    bigquery.SchemaField("topic", "STRING"),
    bigquery.SchemaField("key_issue", "STRING"),
    bigquery.SchemaField("model", "STRING"),
    bigquery.SchemaField("enriched_at", "TIMESTAMP"),
]


class ReviewLabels(BaseModel):
    sentiment_label: Literal["positive", "negative", "neutral"]
    sentiment_score: float
    topic: Literal[
        "food quality", "delivery", "pricing", "service", "packaging", "other"
    ]
    key_issue: Optional[str] = None


def normalize(labels: ReviewLabels) -> dict:
    """Clamp / clean the model output before it is stored."""
    score = max(-1.0, min(1.0, float(labels.sentiment_score)))
    issue = (labels.key_issue or "").strip()
    if issue.lower() in {"", "null", "none", "n/a"}:
        issue = ""
    return {
        "sentiment_label": labels.sentiment_label,
        "sentiment_score": round(score, 3),
        "topic": labels.topic,
        "key_issue": issue[:100] or None,
    }


def tables(project: str, raw_ds: str, ai_ds: str) -> dict[str, str]:
    return {
        "raw_reviews": f"`{project}.{raw_ds}.reviews`",
        "comments": f"`{project}.{ai_ds}.comment_enrichment`",
        "review_enriched": f"`{project}.{ai_ds}.review_enriched`",
    }


def ensure_comment_table(bq: bigquery.Client, t: dict[str, str]) -> None:
    bq.query(
        f"""
        CREATE TABLE IF NOT EXISTS {t['comments']} (
          comment STRING,
          sentiment_label STRING,
          sentiment_score FLOAT64,
          topic STRING,
          key_issue STRING,
          model STRING,
          enriched_at TIMESTAMP
        )
        """
    ).result()


PENDING_WHERE = """
  r.comment IS NOT NULL AND TRIM(r.comment) != ''
  AND NOT EXISTS (SELECT 1 FROM {comments} e WHERE e.comment = r.comment)
"""


def count_pending(bq: bigquery.Client, t: dict[str, str]) -> int:
    sql = f"""
        SELECT COUNT(DISTINCT r.comment) AS n
        FROM {t['raw_reviews']} r
        WHERE {PENDING_WHERE.format(comments=t['comments'])}
    """
    return int(next(iter(bq.query(sql).result())).n)


def fetch_pending(bq: bigquery.Client, t: dict[str, str], limit: int) -> list[str]:
    sql = f"""
        SELECT DISTINCT r.comment AS comment
        FROM {t['raw_reviews']} r
        WHERE {PENDING_WHERE.format(comments=t['comments'])}
        ORDER BY comment
        LIMIT {int(limit)}
    """
    return [row.comment for row in bq.query(sql).result()]


def classify(client, comment: str) -> dict:
    labels = llm.generate_json(client, SYSTEM_PROMPT, comment, ReviewLabels)
    return normalize(labels)


def classify_all(
    comments: list[str], workers: int
) -> tuple[list[dict], list[tuple[str, str]]]:
    client = llm.make_chat_client()
    model = llm.chat_model()
    now = datetime.now(timezone.utc).isoformat()
    rows: list[dict] = []
    failures: list[tuple[str, str]] = []

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(classify, client, c): c for c in comments}
        for i, future in enumerate(as_completed(futures), start=1):
            comment = futures[future]
            try:
                rows.append(
                    {"comment": comment, **future.result(), "model": model,
                     "enriched_at": now}
                )
            except Exception as exc:
                failures.append((comment, str(exc)))
            if i % 50 == 0 or i == len(comments):
                print(f"  classified {i}/{len(comments)}")
    return rows, failures


def save_rows(bq: bigquery.Client, t: dict[str, str], rows: list[dict]) -> None:
    if not rows:
        return
    table_id = t["comments"].strip("`")
    job = bq.load_table_from_json(
        rows,
        table_id,
        job_config=bigquery.LoadJobConfig(
            schema=SCHEMA_FIELDS,
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        ),
    )
    job.result()  # load jobs are free


def rebuild_review_enriched(bq: bigquery.Client, t: dict[str, str]) -> int:
    bq.query(
        f"""
        CREATE OR REPLACE TABLE {t['review_enriched']} AS
        WITH latest AS (
          SELECT * FROM {t['comments']}
          QUALIFY ROW_NUMBER() OVER (
            PARTITION BY comment ORDER BY enriched_at DESC) = 1
        )
        SELECT r.review_id, l.sentiment_label, l.sentiment_score, l.topic,
               l.key_issue, l.model, l.enriched_at
        FROM {t['raw_reviews']} r
        JOIN latest l ON r.comment = l.comment
        """
    ).result()
    row = next(iter(bq.query(f"SELECT COUNT(*) AS n FROM {t['review_enriched']}").result()))
    return int(row.n)


def estimate(comments: list[str]) -> str:
    in_tokens = sum(len(c) // 4 + 200 for c in comments)  # ~200-token prompt
    out_tokens = len(comments) * 60
    return (
        f"~{in_tokens:,} input tokens, ~{out_tokens:,} output tokens "
        f"for {len(comments):,} comments (check the Vertex AI pricing page "
        f"for the {llm.chat_model()} rate)"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, help="max distinct comments this run")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--dry-run", action="store_true",
                        help="count pending comments and estimate tokens only")
    args = parser.parse_args(argv)

    project = llm.project_id()
    raw_ds = llm.env("GASTROFLOW_BQ_RAW_DATASET", "BQ_RAW_DATASET",
                     default="gastroflow_raw")
    ai_ds = llm.env("GASTROFLOW_BQ_AI_DATASET", "BQ_AI_DATASET",
                    default="gastroflow_ai")
    cap = int(llm.env("GASTROFLOW_AI_MAX_COMMENTS", default=str(DEFAULT_MAX_COMMENTS)))
    limit = min(args.limit, cap) if args.limit else cap

    bq = bigquery.Client(project=project)
    t = tables(project, raw_ds, ai_ds)
    ensure_comment_table(bq, t)

    pending_total = count_pending(bq, t)
    comments = fetch_pending(bq, t, limit)
    print(f"Pending distinct comments: {pending_total:,}; this run: {len(comments):,}")
    if pending_total > len(comments):
        print(f"WARNING: capped at {limit:,} comments per run "
              "(raise GASTROFLOW_AI_MAX_COMMENTS deliberately if needed).")

    if args.dry_run:
        print(estimate(comments))
        return 0

    failures: list[tuple[str, str]] = []
    if comments:
        print(f"Classifying with {llm.chat_model()} ({args.workers} workers)...")
        rows, failures = classify_all(comments, args.workers)
        save_rows(bq, t, rows)
        print(f"Saved {len(rows):,} comment classifications.")
        for comment, error in failures[:5]:
            print(f"  FAILED: {comment[:60]!r}: {error[:200]}")

    total = rebuild_review_enriched(bq, t)
    print(f"review_enriched rebuilt: {total:,} reviews.")

    if comments and len(failures) / len(comments) > MAX_FAILURE_RATE:
        print(f"Too many failures ({len(failures)}/{len(comments)}).")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
