# GastroFlow

GastroFlow is a restaurant- ai data platform that lands original CSV files in
Google Cloud Storage, loads them into BigQuery RAW, and transforms them with
dbt into staging views and analytical marts.

## Current data flow

```text
data/sample/<table>/<table>.csv
        |
        | collect_v2: upload original CSV bytes
        v
GCS: raw/<table>/<table>.csv
        |
        | collect_v2: explicit all-STRING schema, WRITE_TRUNCATE
        v
BigQuery: gastroflow_raw
        |
        | dbt
        v
gastroflow_staging -> gastroflow_marts
```

`collect_v2` is the current direct-source collection path. It preserves source
file bytes and cell values in GCS. BigQuery column identifiers are normalized
by position; values are loaded as strings, and a blank source header is mapped
to `source_index`. The older `collect/` package is retained as the legacy
sanitizing path and has not been changed.

The sample users CSV contains mock `email` and `password` fields. Only upload
synthetic data; never use real credentials or personal information.

## Repository layout

```text
collect/                 Legacy sanitized collection workflow
collect_v2/              Direct-source GCS upload and BigQuery RAW load
transformation/          dbt BigQuery project: staging, marts, and tests
terraform/               Google Cloud infrastructure
ai/                      AI application and enrichment code
app/                     Streamlit applications
airflow/                 Pipeline orchestration
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

Set `GCP_PROJECT_ID`, `GCS_BUCKET`, and other local settings in `.env`. Configure
the dbt `transformation` profile in `%USERPROFILE%\.dbt\profiles.yml` with
BigQuery OAuth, the project, dataset `gastroflow`, and location `europe-west1`.
Keep credentials and profiles out of Git.

## Collection commands

Run one table at a time:

```powershell
python -m collect_v2.upload_to_gcs --tables food
python -m collect_v2.load_to_bigquery --tables food
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
