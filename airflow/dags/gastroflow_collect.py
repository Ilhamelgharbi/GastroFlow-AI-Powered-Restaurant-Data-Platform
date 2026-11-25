import os
from datetime import timedelta
from itertools import pairwise

import pendulum

from airflow import DAG

try:
    from airflow.providers.standard.operators.python import PythonOperator
except ImportError:
    from airflow.operators.python import PythonOperator

GASTROFLOW_ENV = os.getenv("GASTROFLOW_ENV", "local")
COLLECTION_TABLES = ("food", "menu", "restaurants", "users")


def load_table_from_gcs(table: str) -> dict[str, str | int | None]:
    from collect.load_from_gcs import load_table_from_gcs as load

    return load(
        table=table,
        project_id=os.environ["GASTROFLOW_PROJECT_ID"],
        bucket=os.environ["GASTROFLOW_GCS_BUCKET"],
        gcs_prefix=os.getenv("GASTROFLOW_GCS_PREFIX", "raw/"),
        raw_dataset=os.getenv("GASTROFLOW_BQ_RAW_DATASET", "gastroflow_raw"),
    )


if GASTROFLOW_ENV == "composer":
    with DAG(
        dag_id="gastroflow_collect",
        start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
        schedule=None,
        catchup=False,
        max_active_runs=1,
        default_args={
            "owner": "gastroflow",
            "retries": 1,
            "retry_delay": timedelta(minutes=5),
        },
        tags=["gastroflow", "gcs", "bigquery", "collect"],
    ) as dag:
        load_tasks = [
            PythonOperator(
                task_id=f"load_raw_{table}",
                python_callable=load_table_from_gcs,
                op_kwargs={"table": table},
            )
            for table in COLLECTION_TABLES
        ]

        for previous_task, next_task in pairwise(load_tasks):
            previous_task >> next_task
