"""GastroFlow full pipeline on Cloud Composer.

GCS raw files -> BigQuery raw -> dbt staging -> dbt marts
-> Gemini review enrichment -> dbt AI marts -> dbt snapshots
"""

import os
import subprocess
import sys
from datetime import timedelta

import pendulum

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

TABLES = ["food", "menu", "restaurants", "users", "reviews", "orders", "order_items"]

DBT_SETUP = """
set -euo pipefail
python -m venv /tmp/gastroflow_dbt_venv
/tmp/gastroflow_dbt_venv/bin/pip install --no-cache-dir --quiet dbt-core==1.12.4 dbt-bigquery==1.12.4
rm -rf /tmp/gastroflow_dbt_project
cp -R /home/airflow/gcs/data/transformation /tmp/gastroflow_dbt_project
"""

DBT = "/tmp/gastroflow_dbt_venv/bin/dbt"
DBT_DIRS = "--project-dir /tmp/gastroflow_dbt_project --profiles-dir /home/airflow/gcs/data/dbt_profiles"

# AI configuration
AI_ENABLED = os.getenv("GASTROFLOW_ENABLE_AI", "false").lower() == "true"
# Default 20. At least 1, because the script treats 0 as "use its own cap".
AI_MAX_COMMENTS = max(1, int(os.getenv("GASTROFLOW_AI_MAX_COMMENTS", "20")))


def check_gcs_files():
    """Stop before loading if any source file is missing or empty in GCS."""
    from google.cloud import storage

    bucket_name = os.environ["GASTROFLOW_GCS_BUCKET"]
    prefix = os.getenv("GASTROFLOW_GCS_PREFIX", "raw/").strip("/")
    bucket = storage.Client(
        project=os.environ["GASTROFLOW_PROJECT_ID"]
    ).bucket(bucket_name)

    problems = []
    for table in TABLES:
        name = "/".join(part for part in [prefix, table, f"{table}.csv"] if part)
        blob = bucket.get_blob(name)

        if blob is None or not blob.size:
            problems.append(name)
        else:
            print(f"OK gs://{bucket_name}/{name}: {blob.size:,} bytes")

    if problems:
        raise ValueError(f"Missing or empty files: {', '.join(problems)}")


def load_to_bigquery(table):
    """Replace one raw BigQuery table with its CSV from GCS."""
    from collect.load_from_gcs import load_table_from_gcs

    load_table_from_gcs(
        table=table,
        project_id=os.environ["GASTROFLOW_PROJECT_ID"],
        bucket=os.environ["GASTROFLOW_GCS_BUCKET"],
        gcs_prefix=os.getenv("GASTROFLOW_GCS_PREFIX", "raw/"),
        raw_dataset=os.getenv("GASTROFLOW_BQ_RAW_DATASET", "gastroflow_raw"),
    )

def enrich_reviews():
    """Run Gemini enrichment or skip it when AI is disabled."""

    if not AI_ENABLED:
        print("SKIP: GastroFlow AI enrichment is disabled.", flush=True)
        return

    print(
        f"Starting Gemini enrichment (limit={AI_MAX_COMMENTS})",
        flush=True,
    )

    venv = "/tmp/gastroflow_ai_venv"
    python = f"{venv}/bin/python"

    # 1. Create virtual environment
    print("STEP 1: Creating AI virtual environment...", flush=True)

    subprocess.run(
        [sys.executable, "-m", "venv", venv],
        check=True,
    )

    # 2. Install dependencies
    print("STEP 2: Installing AI dependencies...", flush=True)

    subprocess.run(
        [
            python,
            "-m",
            "pip",
            "install",
            "--no-cache-dir",
            "google-genai",
            "google-cloud-bigquery",
            "pydantic",
        ],
        check=True,
    )

    # 3. Configure environment
    env = os.environ.copy()
    env["PYTHONPATH"] = "/home/airflow/gcs/dags"

    # 4. Run Gemini enrichment
    print("STEP 3: Running Gemini enrichment...", flush=True)

    result = subprocess.run(
        [
            python,
            "-m",
            "ai.enrich_reviews",
            "--limit",
            str(AI_MAX_COMMENTS),
        ],
        cwd="/home/airflow/gcs/dags",
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    print("=== GEMINI ENRICHMENT OUTPUT ===", flush=True)
    print(result.stdout or "No output captured.", flush=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"Gemini enrichment failed with exit code "
            f"{result.returncode}"
        )

    print("Gemini enrichment completed successfully.", flush=True)



with DAG(
    dag_id="gastroflow_full_pipeline_ai",
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "gastroflow",
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["gastroflow", "ai"],
) as dag:

    check_files = PythonOperator(
        task_id="check_gcs_files",
        python_callable=check_gcs_files,
    )

    load_tasks = [
        PythonOperator(
            task_id=f"load_raw_{table}",
            python_callable=load_to_bigquery,
            op_args=[table],
        )
        for table in TABLES
    ]

    dbt_staging = BashOperator(
        task_id="dbt_staging",
        bash_command=(
            f"{DBT_SETUP}{DBT} build {DBT_DIRS} "
            "--select staging --indirect-selection=cautious"
        ),
    )

    dbt_marts = BashOperator(
        task_id="dbt_marts",
        bash_command=(
            f"{DBT_SETUP}{DBT} build {DBT_DIRS} "
            "--select marts --exclude tag:ai"
        ),
    )

    # Gemini enrichment: runs or prints SKIP depending on AI_ENABLED.
    ai_enrichment = PythonOperator(
        task_id="enrich_reviews_with_gemini",
        python_callable=enrich_reviews,
        retries=0,
        execution_timeout=timedelta(minutes=45),
    )

    # AI models are enabled explicitly through the dbt variable.
    dbt_ai = BashOperator(
        task_id="dbt_ai",
        bash_command=(
            f"{DBT_SETUP}{DBT} build {DBT_DIRS} "
            "--select tag:ai --vars '{enable_ai: true}'"
            if AI_ENABLED
            else "echo 'SKIP: AI is disabled, AI mart not rebuilt.'"
        ),
    )

    dbt_snapshots = BashOperator(
        task_id="dbt_snapshots",
        bash_command=(
            f"{DBT_SETUP}{DBT} snapshot {DBT_DIRS} "
            "--select snap_restaurants snap_orders"
        ),
    )

    # Sequential raw loading, then the complete transformation pipeline.
    previous = check_files

    for load_task in load_tasks:
        previous >> load_task
        previous = load_task

    previous >> dbt_staging >> dbt_marts
    dbt_marts >> ai_enrichment >> dbt_ai >> dbt_snapshots