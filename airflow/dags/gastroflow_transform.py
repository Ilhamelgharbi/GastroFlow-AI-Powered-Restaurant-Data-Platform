import os
from datetime import timedelta

import pendulum

from airflow import DAG

try:
    from airflow.providers.standard.operators.bash import BashOperator
except ImportError:
    from airflow.operators.bash import BashOperator

GASTROFLOW_ENV = os.getenv("GASTROFLOW_ENV", "local")


def composer_dbt_command() -> str:
    dbt_venv = "/tmp/gastroflow_dbt_venv"
    dbt_project = "/tmp/gastroflow_dbt_project"
    profile_dir = "/home/airflow/gcs/data/dbt_profiles"
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
                "--select stg_food stg_menu stg_restaurants stg_users "
                "dim_food dim_restaurants dim_customers "
                "--exclude assert_fct_orders_customer_exists"
            ),
        ]
    )


if GASTROFLOW_ENV == "composer":
    with DAG(
        dag_id="gastroflow_transform",
        start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
        schedule=None,
        catchup=False,
        max_active_runs=1,
        default_args={
            "owner": "gastroflow",
            "retries": 1,
            "retry_delay": timedelta(minutes=5),
        },
        tags=["gastroflow", "dbt", "transform"],
    ) as dag:
        build_lightweight_models = BashOperator(
            task_id="build_lightweight_models",
            bash_command=composer_dbt_command(),
        )
