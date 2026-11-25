FROM apache/airflow:3.0.3-python3.12

ARG AIRFLOW_VERSION=3.0.3
ARG PYTHON_VERSION=3.12

RUN pip install --no-cache-dir \
      --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt" \
      apache-airflow-providers-fab \
      apache-airflow-providers-standard \
      duckdb \
      google-cloud-bigquery \
      google-cloud-storage \
      python-dotenv

RUN python -m venv /opt/airflow/dbt_venv && \
    /opt/airflow/dbt_venv/bin/pip install --no-cache-dir "dbt-bigquery==1.12.4"
