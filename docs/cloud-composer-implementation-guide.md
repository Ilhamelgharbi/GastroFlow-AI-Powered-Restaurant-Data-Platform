# GastroFlow Cloud Composer Implementation Guide

## Purpose and scope

This guide documents the Google Cloud Composer deployment and operating steps
for GastroFlow. The food-only pilot and four-table staged pilot are complete.
The manual `gastroflow_batch` DAG now provides one end-to-end collection and
dbt transformation run. The source table list now includes all seven tables.
The deployed Composer DAG remains food-only until the Terraform DAG update is
applied.

## Current state

- `airflow/docker-compose.yaml` and `airflow/Dockerfile` run local Airflow 3.0.3.
- `airflow/dags/gastroflow_batch.py` preserves local mode and has a Composer
  mode that loads the configured GCS objects into RAW, then builds dbt models.
  Its source `COMPOSER_TABLES` setting now includes all seven tables.
- `collect/upload_to_gcs.py` and `collect/load_to_bigquery.py` are designed for
  local source files. The loader reads local files to validate headers and
  expected row counts. `collect/load_from_gcs.py` is the cloud loading path.
- `transformation/` contains the dbt models, snapshots, and schema macro.
- Terraform manages the lake bucket, BigQuery datasets, service accounts,
  Composer environment, and DAG/dbt artifact uploads.
- All seven sample CSVs are already in the project lake under
  `raw/<table>/<table>.csv`. The previously deployed DAG loads only `food`;
  the earlier collection-only run loaded `food`, `menu`, `restaurants`, and
  `users`.
- The deployed environment uses `composer-3-airflow-2.11.1-build.27` in
  `europe-west1`. Its name is `gastroflow-composer`.
- Airflow reports no DAG import errors. The manual food DAG run succeeded, and
  `gastroflow_raw.food`, `gastroflow_staging.stg_food`, and
  `gastroflow_marts.dim_food` each contain 371,561 rows.
- `gastroflow_collect` has successfully loaded the four light tables into RAW.
  `reviews`, `orders`, and `order_items` have not been loaded by Composer.
- `gastroflow_transform` has successfully built the four selected staging
  views, three dimensions, and their selected data tests. The run completed
  with `PASS=12`, `ERROR=0`, and `SKIP=0`. The first run also selected a
  cross-model test that queries `fct_orders`; the DAG now explicitly excludes
  that order-dependent test from future light-table runs.
- The source version lists all seven tables and their dependencies. Composer
  still runs the previously deployed food-only version until Terraform
  applies the DAG update.
- The integrated `gastroflow_batch` run
  `manual__food_full_pipeline_retry_20261125` completed successfully: both
  `load_raw_food` and `build_dbt_staging_and_marts` succeeded. The loader
  reported 371,561 RAW rows; dbt passed both selected models and built
  `stg_food` and `dim_food`.
- The all-table dbt selection was checked with `dbt ls` only. It has not been
  run against BigQuery; only the food-only E2E run has been executed in
  Composer.

The local Compose stack and Cloud Composer are separate environments. The
local Postgres metadata database is not part of Composer.

## Current end-to-end architecture

```text
GCS: raw/food/food.csv
                 |
                 v
gastroflow_batch loads gastroflow_raw.food
                 |
                 v
dbt builds stg_food and dim_food
                 |
                 v
gastroflow_staging.stg_food -> gastroflow_marts.dim_food
```

`gastroflow_batch` loads every table in its `COMPOSER_TABLES` tuple in
sequence, then runs the matching dbt selection. The source tuple now contains
all seven tables. `reviews` automatically adds its `restaurants` source;
`order_items` automatically adds `orders`. Composer continues to use the
previous food-only version until the updated DAG object is applied.

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
  one selected CSV from GCS and writes to its BigQuery RAW table using the
  existing all-STRING schema.
- The Composer end-to-end DAG in `airflow/dags/gastroflow_batch.py` collects
  its configured tables and then builds their dbt models in the same manual
  run. The source `COMPOSER_TABLES` tuple now includes all seven tables; the
  successful Composer proof run used the earlier food-only deployed version.
- Supported source names are `food`, `menu`, `restaurants`, `users`, `reviews`,
  `orders`, and `order_items`. If all seven are selected, the DAG runs dbt
  against the staging and marts folders, excludes the disabled AI mart, and
  excludes `assert_fct_orders_customer_exists` to avoid a query against an
  existing orders fact table.
- When a partial list is selected, dbt builds only models mapped to those
  tables. Selecting `reviews` also loads/transforms `restaurants`; selecting
  `order_items` also loads/transforms `orders`.
- The all-table dbt selection has only been checked with `dbt ls`; it has not
  run against BigQuery. Only the food-only E2E workflow has been executed in
  Composer.
- `gastroflow_collect` loads only `food`, `menu`, `restaurants`, and `users`.
  It runs sequentially and does not run dbt. It uses `WRITE_TRUNCATE`, so a
  manual rerun reloads those four RAW tables.
- `gastroflow_transform` runs dbt against the four loaded tables without
  running collection. It selects only `stg_food`, `stg_menu`,
  `stg_restaurants`, `stg_users`, `dim_food`, `dim_restaurants`, and
  `dim_customers`. It excludes the singular order/customer consistency test,
  which would otherwise query `fct_orders`.
- The successful collection loaded 371,561 food rows, 1,179,936 menu rows,
  148,541 restaurant rows, and 100,000 user rows into RAW.
- Do not make Composer depend on `data/sample`, a Windows path, a mounted ADC
  JSON file, or the local `.env`.

### Phase 3: Make the DAG and dbt execution portable

- The DAG has import compatibility for the standard Airflow 3 provider path
  and the Airflow 2 operator path. Verify it against the image actually
  selected for Composer.
- Composer DAGs use existing GCS objects; they do not depend on local files or
  perform local uploads. Use `gastroflow_batch` for the end-to-end collection
  and transformation. The separate `gastroflow_collect` and
  `gastroflow_transform` DAGs remain useful for isolated troubleshooting.
- Provide the `collect` package to Composer if the cloud loader reuses its
  schemas and BigQuery helpers. Keep it importable from the DAG folder and
  exclude the helper package from DAG discovery with `.airflowignore`.
- Upload the dbt project and an OAuth-based `profiles.yml` to the Composer
  bucket. The Composer service account supplies credentials through Google
  Cloud; do not upload ADC files or service-account keys.
- The Composer task creates a temporary virtual environment and pins
  `dbt-core` and `dbt-bigquery` to 1.12.4. Both the food-only build and the
  four-table staged transformation have passed.
- Keep `COMPOSER_TABLES` set to `("food",)` until the full-table query cost,
  schema compatibility, and model dependencies have been reviewed.

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
- Confirm the selected synthetic CSVs exist in the lake and the target
  BigQuery datasets match the configured names.
- Confirm `gastroflow_raw`, `gastroflow_staging`, and `gastroflow_marts` exist.
  Start with `food`; the current light-table phase adds `menu`, `restaurants`,
  and `users`, while deferring the three larger tables.
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
- Terraform's `fileset` uploads `airflow/dags/gastroflow_batch.py` and the dbt
  project automatically. No new Composer environment, service account, or
  dataset is needed to publish a change to the DAG's table list.
- The source version lists all seven tables, but the deployed Composer DAG
  remains food-only until the Terraform DAG-object update is applied. A plan
  alone does not publish the file or trigger a run.
- The DAG import check returned `No data found` (no import errors).
- The manual run `manual__food_pilot_2026_11_25` completed successfully. It
  loaded and built only the food pipeline:

  | Table | Rows |
  |---|---:|
  | `gastroflow_raw.food` | 371,561 |
  | `gastroflow_staging.stg_food` | 371,561 |
  | `gastroflow_marts.dim_food` | 371,561 |

- The new end-to-end DAG was run as
  `manual__food_full_pipeline_retry_20261125`. Both task states were
  successful: `load_raw_food` loaded 371,561 rows from the existing
  `raw/food/food.csv` object, then dbt passed `stg_food` and `dim_food`.
  The dimension build processed 14.7 MiB. This test did not upload any CSVs
  from the local machine and did not load the other six tables.
  - The separate collection run `manual__collect_light_tables_2026_11_25`
    completed successfully. It loaded `food`, `menu`, `restaurants`, and `users`
    from GCS into RAW, without invoking dbt.
  - The separate transform run
    `manual__lightweight_transform_fix_20261125` completed successfully with
    `PASS=12`, `WARN=0`, `ERROR=0`, and `SKIP=0`. It created the four staging
    views and three dimensions; the dimension tables contain 371,561 food rows,
    148,541 restaurant rows, and 100,000 customer rows. It did not reload any
    CSVs, run snapshots, or build order/review models. dbt did include the
    singular `assert_fct_orders_customer_exists` test, which queries the
    existing `fct_orders` model; the DAG now excludes that test from future
    light-table runs.
  - A first transform attempt exposed a schema-name mismatch in `stg_users`:
    the RAW column is `educational_qualifications`, not `education`. The model
    now aliases the real RAW column to `education`, and the final dbt run passed.
  - The first Terraform apply for this stage added only the transform DAG. The
    follow-up model fix updated only the uploaded `stg_users.sql` object; neither
    plan changed or destroyed the Composer environment or data resources.

- To check import errors:

  ```powershell
  gcloud composer environments run gastroflow-composer --project=zomato-data-engineering --location=europe-west1 dags list-import-errors
  ```

- To trigger another manual food run and inspect run state:

  ```powershell
  gcloud composer environments run gastroflow-composer --project=zomato-data-engineering --location=europe-west1 dags trigger '--' gastroflow_batch --run-id=manual__food_refresh
  gcloud composer environments run gastroflow-composer --project=zomato-data-engineering --location=europe-west1 dags list-runs '--' --dag-id gastroflow_batch
  ```

- The combined end-to-end DAG uses the same ID, `gastroflow_batch`. Its
  configured food run performs the GCS-to-BigQuery load before dbt; the earlier
  collection-only and transform-only DAGs remain available for troubleshooting.
- The all-table selection was dry-listed with `dbt ls`; it has not been
  executed against BigQuery. Applying the DAG object update does not trigger a
  run. Review the plan and full-run costs before applying, then manually
  trigger only when ready. The initial `fct_order_items` build is estimated at
  about 2.42 GB processed. Snapshots remain a separate operation.
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
| File access | Local mode reads `data/sample` | Composer reads pre-uploaded source objects from the project GCS lake |
| dbt runtime | Composer task pins dbt Core and BigQuery adapter 1.12.4 | Food build passed on the selected Composer image |
| Dataset names | Terraform, dbt macro, and source settings are configurable | Deployed with the `gastroflow` prefix; food models passed |
| Credentials | Local development can use ADC | Composer uses its dedicated runtime service account; no key files uploaded |
| IAM | Existing pipeline account includes broader permissions | Composer has a separate account with the required pilot access |
| Data writes | RAW load uses `WRITE_TRUNCATE` | The collection DAG is manual and replaces only its four selected RAW tables |
| Terraform safety | `force_destroy` defaults to `false` | Keep false and review plans for destructive changes |
| Cloud Function | Capstone uses one for its collection service | Not needed for static CSV input; add only for a real cloud collection use case |

## Completion checklist

- [x] Remote Terraform state is configured and recoverable.
- [x] `force_destroy` is false and all planned deletions/replacements are
      understood.
- [x] Dataset names and dbt schema generation agree.
- [x] All seven source CSVs are in the project lake bucket under
      `raw/<table>/<table>.csv`.
- [x] Composer load code does not depend on local files or Windows paths.
- [x] Composer image and dbt versions are pinned and tested.
- [x] Composer service account has the required pilot permissions.
- [x] Composer environment and DAG/dbt artifact uploads are managed by
      Terraform.
- [x] Airflow reports no DAG import errors.
- [x] The manual food-only load and `stg_food`/`dim_food` build pass.
- [x] The combined `gastroflow_batch` DAG loads food from GCS and then builds
      `stg_food`/`dim_food` in the same manual run.
- [x] The source configuration lists all seven source tables; the full dbt
      selection was dry-listed without running BigQuery jobs.
- [x] The separate light-table collection DAG loads food, menu, restaurants,
      and users without running dbt.
- [x] The separate transform DAG builds the four selected staging views and
      three dimensions without reloading CSVs; the run passed. The order-
      dependent singular test is excluded from future light-table runs.
- [ ] Apply the all-table DAG update and manually run the seven-table pipeline
      after reviewing source objects, dependencies, and query costs (especially
      the order-items mart).
- [ ] AI remains excluded until its input table and enrichment task exist.
- [ ] Cost and safe Composer shutdown procedures are understood.
