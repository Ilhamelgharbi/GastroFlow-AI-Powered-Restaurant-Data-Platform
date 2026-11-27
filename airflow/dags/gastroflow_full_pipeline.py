"""GastroFlow full pipeline on Cloud Composer (no AI).

GCS raw files -> BigQuery raw -> dbt staging -> dbt marts -> dbt snapshots
"""

import os
from datetime import timedelta

import pendulum

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

# Same order as the load tasks.
TABLES = ["food", "menu", "restaurants", "users", "reviews", "orders", "order_items"]

# Install dbt in a temporary environment and copy the project to local disk.
DBT_SETUP = """
set -euo pipefail
python -m venv /tmp/gastroflow_dbt_venv
/tmp/gastroflow_dbt_venv/bin/pip install --no-cache-dir --quiet dbt-core==1.12.4 dbt-bigquery==1.12.4
rm -rf /tmp/gastroflow_dbt_project
cp -R /home/airflow/gcs/data/transformation /tmp/gastroflow_dbt_project
"""

DBT = "/tmp/gastroflow_dbt_venv/bin/dbt"
DBT_DIRS = "--project-dir /tmp/gastroflow_dbt_project --profiles-dir /home/airflow/gcs/data/dbt_profiles"


def check_gcs_files():
    """Stop before loading if any source file is missing or empty in GCS."""
    from google.cloud import storage

    bucket_name = os.environ["GASTROFLOW_GCS_BUCKET"]
    prefix = os.getenv("GASTROFLOW_GCS_PREFIX", "raw/").strip("/")
    bucket = storage.Client(project=os.environ["GASTROFLOW_PROJECT_ID"]).bucket(bucket_name)

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


with DAG(
    dag_id="gastroflow_full_pipeline",
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    schedule=None,  # manual trigger only
    catchup=False,
    max_active_runs=1,
    default_args={"owner": "gastroflow", "retries": 1, "retry_delay": timedelta(minutes=5)},
    tags=["gastroflow"],
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
        # cautious: skip tests that need marts, which are not built yet
        bash_command=f"{DBT_SETUP}{DBT} build {DBT_DIRS} --select staging --indirect-selection=cautious",
    )

    dbt_marts = BashOperator(
        task_id="dbt_marts",
        bash_command=f"{DBT_SETUP}{DBT} build {DBT_DIRS} --select marts --exclude tag:ai",
    )

    dbt_snapshots = BashOperator(
        task_id="dbt_snapshots",
        bash_command=f"{DBT_SETUP}{DBT} snapshot {DBT_DIRS} --select snap_restaurants snap_orders",
    )

    # Order: check -> 7 loads one by one -> staging -> marts -> snapshots
    previous = check_files
    for load_task in load_tasks:
        previous >> load_task
        previous = load_task

    previous >> dbt_staging >> dbt_marts >> dbt_snapshots