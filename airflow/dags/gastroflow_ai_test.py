
import os
import subprocess
import sys

import pendulum

from airflow import DAG
from airflow.operators.python import PythonOperator

AI_ENABLED = (
    os.getenv("GASTROFLOW_ENABLE_AI", "false").lower() == "true")
AI_MAX_COMMENTS = int(os.getenv("GASTROFLOW_AI_MAX_COMMENTS", "5"))


def enrich_reviews():
    """Run Gemini enrichment only."""

    if not AI_ENABLED:
        print("AI enrichment is disabled.", flush=True)
        return

    print(f"Starting Gemini enrichment (limit={AI_MAX_COMMENTS})", flush=True)

    venv = "/tmp/gastroflow_ai_venv"
    python = f"{venv}/bin/python"

    subprocess.run(
        [sys.executable, "-m", "venv", venv],
        check=True,
    )

    subprocess.run(
        [
            python, "-m", "pip", "install",
            "--no-cache-dir",
            "google-genai",
            "google-cloud-bigquery",
            "pydantic",
        ],
        check=True,
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = "/home/airflow/gcs/dags"

    result = subprocess.run(
        [
            python, "-m", "ai.enrich_reviews",
            "--limit", str(AI_MAX_COMMENTS),
        ],
        cwd="/home/airflow/gcs/dags",
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    print(result.stdout or "No output captured.", flush=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"Gemini enrichment failed: exit code {result.returncode}"
        )

    print("Gemini enrichment completed successfully.", flush=True)


with DAG(
    dag_id="gastroflow_ai_enrichment_test",
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    tags=["gastroflow", "ai", "test"],
) as dag:

    ai_enrichment = PythonOperator(
        task_id="enrich_reviews_with_gemini_test",
        python_callable=enrich_reviews,
        retries=0,
    )
