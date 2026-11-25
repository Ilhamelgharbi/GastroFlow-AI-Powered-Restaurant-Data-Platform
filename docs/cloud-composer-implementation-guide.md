# GastroFlow Cloud Composer Implementation Guide

## Purpose and scope

This guide documents the Google Cloud Composer deployment and operating steps
for GastroFlow. The environment is provisioned and the first food-only run has
been validated in the live GCP project.

The first Composer proof run is intentionally limited to the `food` CSV:
upload it to GCS, load `gastroflow_raw.food`, then build `stg_food` and
`dim_food`. Other models, snapshots, and AI enrichment are deferred until
their input tables are available.

## Current state

- `airflow/docker-compose.yaml` and `airflow/Dockerfile` run local Airflow 3.0.3.
- `airflow/dags/gastroflow_batch.py` preserves local mode and has a Composer
  mode that loads the pre-uploaded `food` object and builds its two dbt models.
- `collect/upload_to_gcs.py` and `collect/load_to_bigquery.py` are designed for
  local source files. The loader reads local files to validate headers and
  expected row counts. `collect/load_from_gcs.py` is the cloud loading path.
- `transformation/` contains the dbt models, snapshots, and schema macro.
- Terraform manages the lake bucket, BigQuery datasets, service accounts,
  Composer environment, and DAG/dbt artifact uploads.
- The food source object is already in the project lake at
  `raw/food/food.csv`; the other sample CSVs have not been added to this pilot.
- The deployed environment uses `composer-3-airflow-2.11.1-build.27` in
  `europe-west1`. Its name is `gastroflow-composer`.
- Airflow reports no DAG import errors. The manual food DAG run succeeded, and
  `gastroflow_raw.food`, `gastroflow_staging.stg_food`, and
  `gastroflow_marts.dim_food` each contain 371,561 rows.

The local Compose stack and Cloud Composer are separate environments. The
local Postgres metadata database is not part of Composer.

## Target first-release architecture

```text
Synthetic food CSV in data/sample/food/food.csv
                 |
                 v
Local collector uploads it to the existing GCS lake
                 |
                 v
Cloud Composer: load into gastroflow_raw.food
                 |
                 v
       dbt stg_food -> dim_food
```

Composer has its own managed bucket for DAGs and supporting files. Keep it
separate from the project lake bucket that stores the source CSVs.

For static sample files, upload them to the lake before triggering the DAG.
Do not add a Cloud Function just to move these files; the capstone used one
because it had a separate collection service. Revisit a Cloud Run function or
job only if GastroFlow later needs cloud-hosted data collection.

## Decisions and safeguards

1. **Keep the first DAG manual.** The current BigQuery load uses
   `WRITE_TRUNCATE`, so a schedule could replace data unexpectedly.
2. **Use synthetic data only.** The users sample includes mock email and
   password columns; never upload real credentials or personal data.
3. **Keep the AI step disabled.** Do not add a Vertex AI task, API key, or
   AI-dependent dbt model to the first Composer release.
4. **Protect existing data.** Terraform defaults `force_destroy` to `false`.
   Keep it false and inspect every plan for dataset or bucket
   deletion/replacement.
5. **Choose and pin versions.** Select an available Composer image for the
   target region, then pin a dbt version compatible with its Python runtime.
   The local image uses dbt BigQuery 1.12.4; an older dbt version in a guide
   example is not an implicit version decision.

## Implementation sequence

### Phase 1: Prepare Terraform state and naming

- Create the Terraform state bucket once, outside the application resources.
- Configure the existing GCS backend with a gitignored backend config file and
  initialize Terraform with it.
- Fill in `terraform/terraform.tfvars` with the intended project and region.
  Keep the initial prefix as `gastroflow` unless the dbt naming is updated at
  the same time.
- `force_destroy` now defaults to `false`; keep it false for deployment.
- Confirm GCS, BigQuery, and Composer will use a compatible region.
- Run `terraform fmt`, `terraform validate`, and `terraform plan`. Resolve
  unexpected replacements before applying.

From `terraform/`, the intended initialization and base validation sequence is:

```powershell
terraform init -backend-config=backend.hcl
terraform fmt -check
terraform validate
terraform plan
```

### Phase 2: Make ingestion work without local files

- Upload the synthetic CSVs to the existing lake bucket using the local
  collector or an approved upload process. Keep the existing object layout:
  `raw/<table>/<table>.csv`.
- For the current local workflow, the upload command is
  `python -m collect.upload_to_gcs --directory data/sample --tables food` from
  the repository root, after `.env` and local Google credentials are
  configured. This creates `raw/food/food.csv` in the lake bucket.
- The Composer load path is implemented in `collect/load_from_gcs.py`. It reads
  each CSV from GCS and writes to its BigQuery RAW table using the existing
  all-STRING schema.
- The cloud loader records the BigQuery load result and loaded row count. The
  live food run loaded 371,561 rows into `gastroflow_raw.food`.
- Do not make Composer depend on `data/sample`, a Windows path, a mounted ADC
  JSON file, or the local `.env`.

### Phase 3: Make the DAG and dbt execution portable

- The DAG has import compatibility for the standard Airflow 3 provider path
  and the Airflow 2 operator path. Verify it against the image actually
  selected for Composer.
- Composer mode skips the local-only upload task, loads the pre-uploaded food
  object, then builds only `stg_food` and `dim_food`. It does not run snapshots.
- Provide the `collect` package to Composer if the cloud loader reuses its
  schemas and BigQuery helpers. Keep it importable from the DAG folder and
  exclude the helper package from DAG discovery with `.airflowignore`.
- Upload the dbt project and an OAuth-based `profiles.yml` to the Composer
  bucket. The Composer service account supplies credentials through Google
  Cloud; do not upload ADC files or service-account keys.
- The Composer task creates a temporary virtual environment and pins
  `dbt-core` and `dbt-bigquery` to 1.12.4. The live food build passed.
- The initial Composer DAG is deliberately restricted to `food`; dbt builds
  `stg_food` and `dim_food` only. Do not run snapshots or all staging/mart
  models until their other RAW source tables have been loaded.

### Phase 4: Add Composer infrastructure and IAM

- Terraform now enables `composer.googleapis.com`, defines a Composer image
  version variable, and gates the environment on `enable_composer`.
- Terraform now creates a dedicated Composer runtime service account and
  grants the roles
  required to run the DAG:
  - Composer worker permissions for the environment.
  - BigQuery job creation and dataset access for RAW, staging, and marts.
  - Read access to the project lake objects when Composer only loads data.
- Terraform adds the Composer service-agent permissions and managed uploads
  for:
  - DAG Python files.
  - The required `collect` Python sources and `.airflowignore`.
  - dbt project files, excluding generated `target`, `logs`,
    `dbt_packages`, and local configuration.
  - The dbt profile, published as `profiles.yml`.
- Terraform exposes the Composer environment URI and managed bucket as
  outputs.
- Keep source CSVs in the project lake bucket, not in the Composer DAG bucket.

The existing pipeline service account has broad GCS/BigQuery permissions and
Vertex AI access. Reusing it may be expedient for a short-lived demo, but a
dedicated Composer identity is the preferred implementation. Do not grant
Vertex AI access for the first release.

### Phase 5: Validate the base cloud pipeline (complete)

- The Terraform configuration already defines the RAW, staging, marts,
  snapshots, and AI datasets. If those resources have been applied, reuse them;
  do not create duplicate datasets. Apply the base bucket and service-account
  resources with `enable_composer = false` only if they are not already
  provisioned and in the active Terraform state.
- Confirm the synthetic CSVs exist in the lake and the target BigQuery
  datasets match the configured names.
- Confirm `gastroflow_raw`, `gastroflow_staging`, and `gastroflow_marts` exist.
  Upload and validate only the `food` source for this first run.
- Run the existing local dbt parse/checks against the same GCP project where
  practical, then verify the `stg_food` and `dim_food` models.
- Check query billing limits before the first full dbt build. The project
  README notes that the initial `fct_order_items` build needs about 2.42 GB
  while the local profile's current per-query cap is 2 GB; approve and adjust
  the limit deliberately rather than silently raising it.

### Phase 6: Provision Composer and deploy the DAG (complete)

- The environment `gastroflow-composer` is running in
  `zomato-data-engineering/europe-west1` on
  `composer-3-airflow-2.11.1-build.27`. Terraform state tracks it and its
  uploads.
- The ignored `terraform/terraform.tfvars` keeps
  `enable_composer = true` and the pinned image version. Preserve these values
  when planning or applying; the code default is `false`, which would plan to
  remove Composer if the local setting is omitted.
- The DAG and dbt project are uploaded to the Composer-managed bucket. The
  source CSV remains in the separate project lake bucket.
- The DAG import check returned `No data found` (no import errors).
- The manual run `manual__food_pilot_2026_11_25` completed successfully. It
  loaded and built only the food pipeline:

  | Table | Rows |
  |---|---:|
  | `gastroflow_raw.food` | 371,561 |
  | `gastroflow_staging.stg_food` | 371,561 |
  | `gastroflow_marts.dim_food` | 371,561 |

- To check import errors:

  ```powershell
  gcloud composer environments run gastroflow-composer --project=zomato-data-engineering --location=europe-west1 dags list-import-errors
  ```

- To trigger another manual food run and inspect run state:

  ```powershell
  gcloud composer environments run gastroflow-composer --project=zomato-data-engineering --location=europe-west1 dags trigger '--' gastroflow_batch --run-id=manual__food_refresh
  gcloud composer environments run gastroflow-composer --project=zomato-data-engineering --location=europe-west1 dags list-runs '--' --dag-id gastroflow_batch
  ```

- Review task logs in the Airflow UI or Cloud Logging. Expand the DAG to other
  tables only after adding and validating their GCS inputs; run snapshots
  after the restaurants and orders source tables are ready.
- Keep `schedule=None` until overwrite and refresh behavior are explicitly
  approved.

### Phase 7: Control costs and clean up safely

- The Composer environment is currently running and incurs ongoing cloud costs
  even when no DAG is running. Monitor project billing.
- To remove only Composer after testing, set `enable_composer = false` and
  apply the plan after confirming it removes only Composer resources and
  Composer-bucket artifacts.
- Do not use a whole-project `terraform destroy` as a Composer shutdown
  procedure. Keep the state bucket and lake/data resources unless intentionally
  decommissioning the project.

### Phase 8: Add AI later, as a separate change

- Define the review-enrichment input/output contract and populate the
  `gastroflow_ai.review_enriched` table before enabling the dependent mart.
- Add a dedicated AI task, required Vertex AI permissions, and Secret Manager
  resources only if the chosen AI service requires them.
- Validate the AI output and failure/retry behavior independently, then remove
  the `tag:ai` exclusion only when the source table and model are ready.

## Known compatibility conflicts to resolve

| Area | Current state | Composer action |
|---|---|---|
| Airflow version | Local image is Airflow 3.0.3; Composer runs Airflow 2.11.1 | Both operator import paths are supported; Composer import check passed |
| File access | Local mode reads `data/sample` | Composer reads the food object from the project GCS lake |
| dbt runtime | Composer task pins dbt Core and BigQuery adapter 1.12.4 | Food build passed on the selected Composer image |
| Dataset names | Terraform, dbt macro, and source settings are configurable | Deployed with the `gastroflow` prefix; food models passed |
| Credentials | Local development can use ADC | Composer uses its dedicated runtime service account; no key files uploaded |
| IAM | Existing pipeline account includes broader permissions | Composer has a separate account with the required pilot access |
| Data writes | RAW load uses `WRITE_TRUNCATE` | Keep manual until replacement behavior is approved |
| Terraform safety | `force_destroy` defaults to `false` | Keep false and review plans for destructive changes |
| Cloud Function | Capstone uses one for its collection service | Not needed for static CSV input; add only for a real cloud collection use case |

## Completion checklist

- [x] Remote Terraform state is configured and recoverable.
- [x] `force_destroy` is false and all planned deletions/replacements are
      understood.
- [x] Dataset names and dbt schema generation agree.
- [x] `food/food.csv` is in the project lake bucket at `raw/food/food.csv`.
- [x] Composer load code does not depend on local files or Windows paths.
- [x] Composer image and dbt versions are pinned and tested.
- [x] Composer service account has the required pilot permissions.
- [x] Composer environment and DAG/dbt artifact uploads are managed by
      Terraform.
- [x] Airflow reports no DAG import errors.
- [x] The manual food load and `stg_food`/`dim_food` build pass.
- [ ] Remaining source tables are loaded before expanding to all dbt models
      and snapshots.
- [ ] AI remains excluded until its input table and enrichment task exist.
- [ ] Cost and safe Composer shutdown procedures are understood.
