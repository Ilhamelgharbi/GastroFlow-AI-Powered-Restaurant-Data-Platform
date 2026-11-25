# GastroFlow

GastroFlow is a restaurant data platform that lands original CSV files in
Google Cloud Storage, loads them into BigQuery RAW, and transforms them with
dbt into staging views and analytical marts. Airflow orchestrates the local
development pipeline.

## Current data flow

```text
data/sample/<table>/<table>.csv
        |
        | collect: upload original CSV bytes
        v
GCS: raw/<table>/<table>.csv
        |
        | collect: explicit all-STRING schema, WRITE_TRUNCATE
        v
BigQuery: gastroflow_raw
        |
        | dbt
        v
gastroflow_staging -> gastroflow_marts
```

`collect/` is the direct-source collection path. It preserves source file bytes
in GCS and loads all source columns into BigQuery RAW as strings. Column names
are normalized by position, and a blank source header is mapped to
`source_index`.

The sample users CSV contains mock `email` and `password` fields. Only upload
synthetic data; never use real credentials or personal information.

## Repository layout

```text
collect/                 Direct-source GCS upload and BigQuery RAW load
transformation/          dbt BigQuery project: staging, marts, and tests
terraform/               Google Cloud infrastructure
airflow/                 Local Docker Compose orchestration
data/sample/             Local source CSVs (ignored by Git)
```

## Local setup

Use the project virtual environment and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `GCP_PROJECT_ID`, `GCP_REGION`, `GCS_BUCKET`, and other local settings in
`.env`. Authenticate local Google Cloud access with Application Default
Credentials using `gcloud auth application-default login`. Keep credentials
and profiles out of Git.

## Collection commands

Run one table at a time:

```powershell
python -m collect.upload_to_gcs --tables food
python -m collect.load_to_bigquery --tables food
```

Omit `--tables ...` to process all seven tables. Both commands default to
`data/sample`. Loading uses `WRITE_TRUNCATE`: reruns replace the matching
GCS object and BigQuery RAW table.

## dbt commands

Run from the repository root:

```powershell
.\.venv\Scripts\dbt.exe debug --project-dir transformation
.\.venv\Scripts\dbt.exe test --project-dir transformation
.\.venv\Scripts\dbt.exe build --project-dir transformation --select staging marts
.\.venv\Scripts\dbt.exe snapshot --project-dir transformation --select snap_restaurants snap_orders
```

## Local Airflow

The local Airflow DAG is manual-triggered and runs the pipeline in order:
upload source CSVs to GCS, load BigQuery RAW, build dbt staging and marts, then
run the two dbt snapshots. AI enrichment is deferred; the AI-dependent mart is
disabled and excluded from the DAG.

After setting up `.env` and Google Application Default Credentials, start the
stack from the repository root:

```powershell
docker compose --env-file .env -f airflow/docker-compose.yaml up --build -d
docker compose --env-file .env -f airflow/docker-compose.yaml ps
```

Open `http://localhost:8080` and trigger `gastroflow_batch`. The local-only
default login is `admin` / `admin`; set `AIRFLOW_ADMIN_PASSWORD` in `.env` to
change it. `GCP_ADC_FILE` can point to the ADC JSON file; if blank, Compose uses
the standard Windows ADC location under `%APPDATA%\gcloud`.

The DAG is manual because its BigQuery load uses `WRITE_TRUNCATE`. Stop the
local services with:

```powershell
docker compose --env-file .env -f airflow/docker-compose.yaml down
```

This branch sets up local Airflow only; Cloud Composer Terraform is deferred.

The review-insights mart remains disabled until its AI-enriched review source
table is created. The current local dbt profile has a 2 GB per-query billing
cap; the initial `fct_order_items` build requires about 2.42 GB, so that
specific build needs an explicitly approved higher cap.

The two dbt snapshots use the `check` strategy to preserve restaurant attribute
history and order status/amount history in `gastroflow_snapshots`. They capture
a baseline on the first run; to see another version, a tracked value must change
in a non-production source before rerunning the snapshot command.

## Git and generated files

Feature work belongs on a feature branch and should be pushed for review before
merging into `develop`. Keep `main` for verified releases. `.gitignore` excludes
local data, Claude planning files, `.env`, dbt profiles, compiled targets,
packages, and logs.

```powershell
git switch -c feature/your-feature
# make and validate changes
git add <files>
git commit -m "Describe the change"
git push -u origin feature/your-feature
```
