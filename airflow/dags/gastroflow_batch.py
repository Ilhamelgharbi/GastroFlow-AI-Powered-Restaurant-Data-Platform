from datetime import timedelta

import pendulum

from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator

DBT = "/opt/airflow/dbt_venv/bin/dbt"
PROJECT_DIR = "/opt/airflow/project"
DATA_DIR = f"{PROJECT_DIR}/data/sample"
DBT_PROJECT_DIR = f"{PROJECT_DIR}/transformation"
DBT_PROFILES_DIR = "/opt/airflow/dbt"

with DAG(
    dag_id="gastroflow_batch",
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "gastroflow",
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["gastroflow", "gcs", "bigquery", "dbt"],
    doc_md=__doc__,
) as dag:
    upload_originals = BashOperator(
        task_id="upload_originals_to_gcs",
        bash_command=(
            "python -m collect.upload_to_gcs "
            f"--directory {DATA_DIR}"
        ),
    )

    load_raw = BashOperator(
        task_id="load_raw_to_bigquery",
        bash_command=(
            "python -m collect.load_to_bigquery "
            f"--directory {DATA_DIR}"
        ),
    )

    build_dbt_models = BashOperator(
        task_id="build_dbt_staging_and_marts",
        bash_command=(
            f"{DBT} build --project-dir {DBT_PROJECT_DIR} "
            f"--profiles-dir {DBT_PROFILES_DIR} "
            "--select staging marts --exclude tag:ai"
        ),
    )

    run_snapshots = BashOperator(
        task_id="run_dbt_snapshots",
        bash_command=(
            f"{DBT} snapshot --project-dir {DBT_PROJECT_DIR} "
            f"--profiles-dir {DBT_PROFILES_DIR} "
            "--select snap_restaurants snap_orders"
        ),
    )

    # AI enrichment is intentionally deferred until the core pipeline is validated.
    upload_originals >> load_raw >> build_dbt_models >> run_snapshots
