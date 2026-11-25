import os
from datetime import timedelta
from itertools import pairwise

import pendulum

from airflow import DAG

try:
    from airflow.providers.standard.operators.bash import BashOperator
    from airflow.providers.standard.operators.python import PythonOperator
except ImportError:
    from airflow.operators.bash import BashOperator
    from airflow.operators.python import PythonOperator

DBT = "/opt/airflow/dbt_venv/bin/dbt"
PROJECT_DIR = "/opt/airflow/project"
DATA_DIR = f"{PROJECT_DIR}/data/sample"
DBT_PROJECT_DIR = f"{PROJECT_DIR}/transformation"
DBT_PROFILES_DIR = "/opt/airflow/dbt"
GASTROFLOW_ENV = os.getenv("GASTROFLOW_ENV", "local")
COMPOSER_TABLES = ("food",)
PIPELINE_TABLE_ORDER = (
    "food",
    "menu",
    "restaurants",
    "users",
    "reviews",
    "orders",
    "order_items",
)
TABLE_DEPENDENCIES = {
    "reviews": ("restaurants",),
    "order_items": ("orders",),
}
DBT_MODELS_BY_TABLE = {
    "food": ("stg_food", "dim_food"),
    "menu": ("stg_menu",),
    "restaurants": ("stg_restaurants", "dim_restaurants"),
    "users": ("stg_users", "dim_customers"),
    "reviews": ("stg_reviews",),
    "orders": ("stg_orders", "fct_orders"),
    "order_items": ("stg_order_items", "fct_order_items"),
}

if GASTROFLOW_ENV not in {"local", "composer"}:
    raise ValueError(f"Unsupported GASTROFLOW_ENV: {GASTROFLOW_ENV}")


def load_table_from_gcs(table: str) -> dict[str, str | int | None]:
    from collect.load_from_gcs import load_table_from_gcs as load

    return load(
        table=table,
        project_id=os.environ["GASTROFLOW_PROJECT_ID"],
        bucket=os.environ["GASTROFLOW_GCS_BUCKET"],
        gcs_prefix=os.getenv("GASTROFLOW_GCS_PREFIX", "raw/"),
        raw_dataset=os.getenv("GASTROFLOW_BQ_RAW_DATASET", "gastroflow_raw"),
    )


def composer_tables_to_load(tables: tuple[str, ...]) -> tuple[str, ...]:
    if not tables:
        raise ValueError("COMPOSER_TABLES must contain at least one table")
    if len(set(tables)) != len(tables):
        raise ValueError("COMPOSER_TABLES must not contain duplicate tables")

    unknown_tables = set(tables).difference(PIPELINE_TABLE_ORDER)
    if unknown_tables:
        raise ValueError(
            f"Unsupported Composer table(s): {', '.join(sorted(unknown_tables))}"
        )

    required_tables = set(tables)
    for table in tables:
        required_tables.update(TABLE_DEPENDENCIES.get(table, ()))

    return tuple(
        table for table in PIPELINE_TABLE_ORDER if table in required_tables
    )


def composer_dbt_command(tables: tuple[str, ...]) -> str:
    dbt_venv = "/tmp/gastroflow_dbt_venv"
    dbt_project = "/tmp/gastroflow_dbt_project"
    profile_dir = "/home/airflow/gcs/data/dbt_profiles"
    if set(tables) == set(PIPELINE_TABLE_ORDER):
        selection = (
            "--select staging marts "
            "--exclude tag:ai assert_fct_orders_customer_exists"
        )
    else:
        models = tuple(
            dict.fromkeys(
                model
                for table in tables
                for model in DBT_MODELS_BY_TABLE[table]
            )
        )
        selection = (
            f"--select {' '.join(models)} "
            "--exclude assert_fct_orders_customer_exists"
        )

    return "\n".join(
        [
            "set -euo pipefail",
            f"python -m venv {dbt_venv}",
            (
                f"{dbt_venv}/bin/pip install --no-cache-dir "
                "'dbt-core==1.12.4' 'dbt-bigquery==1.12.4'"
            ),
            f"rm -rf {dbt_project}",
            f"cp -R /home/airflow/gcs/data/transformation {dbt_project}",
            (
                f"{dbt_venv}/bin/dbt build --project-dir {dbt_project} "
                f"--profiles-dir {profile_dir} "
                f"{selection}"
            ),
        ]
    )

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
    if GASTROFLOW_ENV == "composer":
        composer_tables = composer_tables_to_load(COMPOSER_TABLES)
        load_tasks = [
            PythonOperator(
                task_id=f"load_raw_{table}",
                python_callable=load_table_from_gcs,
                op_kwargs={"table": table},
            )
            for table in composer_tables
        ]
        build_dbt_models = BashOperator(
            task_id="build_dbt_staging_and_marts",
            bash_command=composer_dbt_command(composer_tables),
        )
        for previous_task, next_task in pairwise(load_tasks):
            previous_task >> next_task
        load_tasks[-1] >> build_dbt_models
    else:
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

        upload_originals >> load_raw >> build_dbt_models >> run_snapshots
