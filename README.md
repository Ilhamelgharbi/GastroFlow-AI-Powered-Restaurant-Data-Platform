# GastroFlow

Restaurant data engineering platform built on Google Cloud. GastroFlow takes
seven CSV sources through a reproducible pipeline into a GCS data lake and a
BigQuery warehouse, then uses dbt to create tested analytical models.

## Architecture

```text
Local CSV sources
    |
    | audit, validate, remove sensitive fields
    v
Sanitized files
    |
    | upload with checksums
    v
Google Cloud Storage (raw/<table>/)
    |
    | explicit-schema load jobs
    v
BigQuery RAW -> dbt staging -> dbt marts and snapshots
                                      |
                 +--------------------+--------------------+
                 |                    |                    |
            Power BI           Review enrichment      RAG / Text-to-SQL

Terraform provisions cloud resources. Airflow orchestrates later pipeline runs.
```

### Technology

| Area | Technology |
|---|---|
| Data lake | Google Cloud Storage |
| Warehouse | BigQuery |
| Transformations and tests | dbt Core with `dbt-bigquery` |
| Infrastructure | Terraform |
| Local profiling | DuckDB |
| Review enrichment and language applications | Vertex AI / Gemini |
| Orchestration | Apache Airflow |
| Dashboards and applications | Power BI and Streamlit |

## Repository layout

```text
collect/                 Local data preparation and GCS/BigQuery ingestion
terraform/               Google Cloud infrastructure
dbt/                     Staging, marts, snapshots, and data tests
ai/                      Review enrichment and retrieval
app/                     Streamlit applications
airflow/dags/             Pipeline orchestration
docs/data_dictionary/     Data definitions and quality notes
tests/                    Python tests
```

Local source data, generated data, credentials, Terraform state, and planning
notes are intentionally excluded from Git. See `.gitignore`.

## Delivery phases

1. **Source audit and sanitize:** profile the seven CSVs, verify keys and
   relationships, and produce sanitized files without `_idx`, `email`, or
   `password`.
2. **Cloud foundation:** provision a private GCS bucket, BigQuery datasets,
   APIs, and least-privilege service accounts with Terraform.
3. **GCS and BigQuery RAW:** upload sanitized CSVs with SHA-256 checksums and
   load them into explicit-schema, all-STRING BigQuery raw tables.
4. **dbt staging:** clean and type the raw data; add schema and relationship
   tests.
5. **Marts and snapshots:** build analytical facts, dimensions, and history.
6. **AI, applications, orchestration, and dashboards:** add these only after
   the core data pipeline passes its checks.

Complete and verify one phase before beginning the next. Start with a sample
before loading the full dataset.

## Privacy and security

- Remove `_idx`, `email`, and `password` locally before any cloud upload.
- Never commit source data, `.env`, credentials, Terraform state, or
  `profiles.yml`.
- Use least-privilege IAM and read-only access for analytical query tools.
- Set a cloud billing alert before provisioning resources.

## Development workflow

Use `develop` for integration and create a feature branch for each phase or
independently reviewable change. Keep `main` for verified releases.

```powershell
git switch develop
git switch -c feature/phase-1-source-audit
# make and test changes
git add <files>
git commit -m "Add source audit and sanitization"
git push -u origin feature/phase-1-source-audit
```

Merge completed feature branches into `develop` after review and validation.
Promote a verified release from `develop` to `main`.

## Local setup

Python 3.11 or newer is recommended.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Fill in `.env` locally; do not commit it. Cloud authentication and the GCP
project are configured during the cloud-foundation phase.
