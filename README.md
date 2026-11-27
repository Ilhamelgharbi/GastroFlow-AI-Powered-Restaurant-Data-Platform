# GastroFlow AI Data Platform

A restaurant data platform on Google Cloud. It takes 7 CSV files from raw storage
to analytics tables, then adds AI features on top of the reviews and the marts.

**Stack:** Python, Cloud Storage, BigQuery, dbt, Airflow (Cloud Composer),
Terraform, Gemini API, Streamlit.

## Business problem

Restaurant activity is spread across separate files (restaurants, menus, food,
users, orders, order items, reviews). GastroFlow brings them together to follow
sales, restaurant performance, deliveries and customer feedback.

## Architecture

```text
CSV files
   |  Python upload
   v
Cloud Storage        raw/<table>/<table>.csv
   |  BigQuery load job (all STRING, replaces the table)
   v
gastroflow_raw       ------------------> AI enrichment (Gemini)
   |  dbt                                       |
   v                                            v
gastroflow_staging   typed and cleaned views   gastroflow_ai
   |                                            |
   v                                            |
gastroflow_marts     dimensions, facts, marts <-+
   |
gastroflow_snapshots history of orders and restaurants
```

The layers follow a Medallion-like pattern: raw (Bronze), staging (Silver),
marts (Gold).

## Walkthrough

### 1. Collect (`collect/`)

- Uploads the original CSV files to Cloud Storage without changing them.
- Loads them into BigQuery with an explicit all-`STRING` schema.
- Loads use `WRITE_TRUNCATE`: each run **replaces** the raw table.

### 2. Transform (`transformation/`)

- **Staging:** views that clean and prepare the raw columns.
- **Dimensions:** customers, restaurants, food and date.
- **Facts:** `fct_orders` and `fct_order_items`, incremental with `merge`.
- **Marts:** city revenue, monthly sales, restaurant performance, food
  performance, customer order summary and delivery SLA.
- **Snapshots:** `snap_orders` and `snap_restaurants` use the `check` strategy
  to keep earlier versions when tracked values change.
- **Tests:** dbt data tests run as part of `dbt build`.

### 3. Orchestrate (`airflow/dags/`)

DAGs run on Cloud Composer. The main flow is:

```text
check files in GCS -> load raw tables -> dbt staging -> dbt marts -> snapshots
```

`gastroflow_full_pipeline` runs this flow without AI. It starts from files
already in Cloud Storage; it does not upload files from your computer.
The AI variant is in `gastroflow_full_pipline_ai.py`
(DAG ID: `gastroflow_full_pipeline_ai`):

```text
check files -> load raw tables -> dbt staging -> dbt marts
-> Gemini enrichment -> dbt AI mart -> snapshots
```

With AI disabled, the enrichment and AI mart tasks print `SKIP` and do no work.

### 4. AI layer (`ai/` and `app/`)

| Feature | File | What it does |
|---|---|---|
| Review enrichment | `ai/enrich_reviews.py` | Adds sentiment, topic and key issue to review comments |
| Text-to-SQL | `app/text_to_sql.py` | Turns an English question into BigQuery SQL on the marts |
| Review chat (RAG) | `app/rag_chat.py` | Answers questions using the most similar review comments |

**Cost controls**

- Each **distinct** comment is classified once, and the result is reused.
- `GASTROFLOW_AI_MAX_COMMENTS` caps the comments per run (default: 2000).
- `--dry-run` counts pending comments and estimates tokens without calling Gemini.
- Review chat embeds a limited number of the most frequent comments
  (`MAX_COMMENTS` in `app/rag_chat.py`).
- Review chat saves embeddings in `review_embeddings.parquet`. Delete this file
  to rebuild them after the reviews change.
- Text-to-SQL limits the bytes billed per query
  (`GASTROFLOW_APP_MAX_BYTES_BILLED`, default: 10 GB).

The review chat still calls Gemini for each question, and so does text-to-SQL.

The AI mart `mart_review_insights` is built only with
`--vars '{enable_ai: true}'`, after enrichment has run.

## Project structure

```text
GastroFlow/
├── airflow/
│   ├── dags/
│   │   ├── gastroflow_full_pipeline.py      full pipeline without AI
│   │   └── gastroflow_full_pipline_ai.py    full pipeline with AI
│   └── dbt/
│       └── profiles.yml.example             used by Composer and local dbt
├── ai/
│   ├── __init__.py
│   ├── enrich_reviews.py                    review enrichment
│   ├── llm.py                               Gemini client
│   ├── sql_safety.py                        checks for generated SQL
│   ├── requirements.txt
│   └── tests/
├── app/
│   ├── text_to_sql.py                       English question to SQL
│   ├── rag_chat.py                          chat with reviews
│   └── requirements.txt
├── collect/
│   ├── __init__.py
│   ├── config.py                            settings from .env
│   ├── schemas.py                           expected CSV columns
│   ├── upload_to_gcs.py                     local CSV to Cloud Storage
│   ├── load_to_bigquery.py                  load from your computer
│   ├── load_from_gcs.py                     load used by Composer
│   ├── lib/                                 Storage and BigQuery helpers
│   └── tests/
├── transformation/                          dbt project
│   ├── dbt_project.yml
│   ├── macros/
│   ├── models/
│   │   ├── staging/
│   │   └── marts/
│   ├── snapshots/
│   └── tests/
├── terraform/                               *.tf, lock file, tfvars example
├── docs/
│   └── data_dictionary/
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

These stay on your computer and are **not** in Git: `.env`,
`terraform/terraform.tfvars`, `data/` and `.venv/`.

Keep `airflow/dbt/profiles.yml.example`: Terraform uploads it to Composer.

## Recreate the project from zero

Commands are for **Windows PowerShell**. Run them from the repository root unless
a step says otherwise.

### 1. Requirements

- Git, a Python version supported by dbt, Terraform 1.6 or newer, Google Cloud CLI
- A Google Cloud project with billing enabled
- Permission to create resources and IAM roles in it (for example, Owner on a
  personal project)
- The 7 source CSV files (they are not in Git)

### 2. Choose your values

| Value | Example | Rule |
|---|---|---|
| Project ID | `my-gastroflow-123` | Your Google Cloud project |
| Region | `europe-west1` | Use the same one everywhere |
| Prefix | `gastroflow` | **Keep this value:** some AI code expects it |
| Lake bucket | `<project-id>-gastroflow-lake` | Terraform builds this name |
| State bucket | `<project-id>-tfstate` | Must be globally unique |

```powershell
git clone https://github.com/Ilhamelgharbi/GastroFlow-AI-Powered-Restaurant-Data-Platform.git
cd GastroFlow-AI-Powered-Restaurant-Data-Platform
git switch develop

$PROJECT_ID = "YOUR_PROJECT_ID"
$REGION = "europe-west1"
$STATE_BUCKET = "$PROJECT_ID-tfstate"
```

### 3. Sign in and prepare the project

Do this once for a new project. Skip the bucket creation if it already exists.

```powershell
gcloud auth login
gcloud config set project $PROJECT_ID
gcloud auth application-default login
gcloud auth application-default set-quota-project $PROJECT_ID
gcloud services enable serviceusage.googleapis.com cloudresourcemanager.googleapis.com
gcloud storage buckets create "gs://$STATE_BUCKET" --location=$REGION --uniform-bucket-level-access
gcloud storage buckets update "gs://$STATE_BUCKET" --versioning
```

### 4. Install Python packages

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r app/requirements.txt
```

### 5. Set the variables

There are two files. Neither one goes to Git.

#### `.env` (Python, dbt and AI on your computer)

You need **only this one env file**:

```powershell
Copy-Item .env.example .env
notepad .env
```

```dotenv
GCP_PROJECT_ID=YOUR_PROJECT_ID
GCP_REGION=europe-west1
GCS_BUCKET=YOUR_PROJECT_ID-gastroflow-lake
GASTROFLOW_AI_MAX_COMMENTS=20
# Gemini API key (AI Studio). Needed for the AI features.
GASTROFLOW_GEMINI_API_KEY=
```

| Variable | Why |
|---|---|
| `GCP_PROJECT_ID` | Project used by the upload, load, dbt and AI code |
| `GCP_REGION` | Region used by local dbt |
| `GCS_BUCKET` | Data lake bucket |
| `GASTROFLOW_AI_MAX_COMMENTS` | Cost guard. Without it, the script's cap is 2000 |

| `GASTROFLOW_GEMINI_API_KEY` | Used by all Gemini calls (chat and embeddings) |

BigQuery, Cloud Storage and local dbt still need
`gcloud auth application-default login`, even with an API key.

The Google Cloud $300 welcome credit does **not** pay for Gemini API usage through
AI Studio. See the [free trial terms](https://docs.cloud.google.com/free/docs/free-cloud-features).
Never commit the key. For Composer, `terraform.tfvars` (ignored by Git) holds
`gemini_api_key`, and `composer.tf` passes it as an environment variable. This is
simple but **not the most secure option**: the key can be read in the Terraform
state, saved plans and Composer settings. Secret Manager is the safer choice.

Dataset names, the `raw/` prefix and the model names have defaults in the code.

`dbt` and `ai.enrich_reviews` **do not read `.env` by themselves**. Load it into
your terminal, and repeat this in every new terminal:

```powershell
Get-Content .env | Where-Object { $_ -match '^\s*[^#=]+=' } | ForEach-Object {
  $name, $value = $_ -split '=', 2
  Set-Item -Path "Env:$($name.Trim())" -Value $value.Trim()
}
$env:GASTROFLOW_PROJECT_ID
```

The last line should print your project ID.

#### `terraform/terraform.tfvars` (infrastructure)

```powershell
Copy-Item terraform\terraform.tfvars.example terraform\terraform.tfvars
notepad terraform\terraform.tfvars
```

```hcl
project_id      = "YOUR_PROJECT_ID"
region          = "europe-west1"
prefix          = "gastroflow"
force_destroy   = false
enable_composer = false

# Needed when enable_composer = true. Use a version available in your region.
composer_image_version = "composer-3-airflow-2.11.1-build.27"

# Only needed for AI on Composer. Never commit the real value.
gemini_api_key = ""
```

Composer variables are set automatically by `terraform/composer.tf`. You do not
copy `.env` to Composer.

### 6. Create the infrastructure

```powershell
cd terraform
terraform init -reconfigure -backend-config="bucket=$STATE_BUCKET"
terraform plan -out=tfplan
terraform apply tfplan
terraform output
cd ..
```

Read the plan before applying. With Composer off, this creates the data lake,
the BigQuery datasets, service accounts, permissions and enables the APIs.

> If you already deployed this project, use your **existing** backend settings.
> A different state bucket or prefix makes Terraform think nothing exists.

### 7. Add the source data

```text
data/sample/food/food.csv
data/sample/menu/menu.csv
data/sample/restaurants/restaurants.csv
data/sample/users/users.csv
data/sample/reviews/reviews.csv
data/sample/orders/orders.csv
data/sample/order_items/order_items.csv
```

```powershell
python -m collect.upload_to_gcs
```

This replaces matching files in Cloud Storage.

### 8. Run the pipeline

You can run it on Composer (see below), or from your computer:

```powershell
# Load the raw tables (replaces them)
python -m collect.load_to_bigquery

# Create a local dbt profile outside the repository
New-Item -ItemType Directory -Force "$HOME\.dbt-gastroflow" | Out-Null
Copy-Item airflow\dbt\profiles.yml.example "$HOME\.dbt-gastroflow\profiles.yml"

dbt debug --project-dir transformation --profiles-dir "$HOME\.dbt-gastroflow"
dbt build --project-dir transformation --profiles-dir "$HOME\.dbt-gastroflow" --select staging marts --exclude tag:ai
dbt snapshot --project-dir transformation --profiles-dir "$HOME\.dbt-gastroflow" --select snap_restaurants snap_orders
```

These commands use your Google Cloud quota and may cost money.

## Run on Cloud Composer

**Composer costs money while it exists, even when no DAG runs.**

1. In `terraform.tfvars`, set `enable_composer = true` and
   `composer_image_version`.
2. Run `terraform plan -out=tfplan`, check it, then `terraform apply tfplan`.
3. Check for import errors:

```powershell
gcloud composer environments run gastroflow-composer --project=YOUR_PROJECT --location=europe-west1 dags list-import-errors
```

4. Trigger the DAG from the Airflow UI.

### AI settings on Composer

Set these in the `env_variables` block of `terraform/composer.tf`, then plan and
apply again:

| Variable | Default | Effect |
|---|---|---|
| `GASTROFLOW_ENABLE_AI` | `"false"` | `"true"` runs enrichment and the AI mart in `gastroflow_full_pipeline_ai` |
| `GASTROFLOW_AI_MAX_COMMENTS` | `20` in that DAG | Distinct comments per run |

Retries inside the enrichment script can make more Gemini calls than the comment
limit. Other DAG files may use these variables differently, so check a DAG before
triggering it.

### Turn Composer off

Set `enable_composer = false`, run `terraform plan -out=tfplan`, and confirm that
only Composer resources will be destroyed before applying. A Composer bucket
may remain; keep the data lake and Terraform state buckets.

## Run the AI features

These run from your computer and do not need Composer. First complete step 8,
activate `.venv` and load `.env` (step 5).

```powershell
# 1. Count pending comments (no Gemini calls)
python -m ai.enrich_reviews --dry-run

# 2. Classify a small sample (calls Gemini)
python -m ai.enrich_reviews --limit 20

# 3. Build the AI mart
dbt build --project-dir transformation --profiles-dir "$HOME\.dbt-gastroflow" --select mart_review_insights --vars '{enable_ai: true}'

# 4. Start one app at a time (Ctrl+C to stop)
streamlit run app/text_to_sql.py
streamlit run app/rag_chat.py
```

With a 20-comment sample, the AI mart covers only reviews whose comments have
been classified. The dry run queries BigQuery and creates the comment cache
table if it is missing.

## Known limitations

- **Text-to-SQL safety is basic.** The keyword filter can be bypassed, for
  example by `SELECT *` on a table that contains emails. Keep the app private.
  Stronger protection needs restricted BigQuery permissions, a table allowlist
  and marts without personal data.
- **Incremental facts use a timestamp watermark**, so later updates to older
  orders can be missed.
- **Raw loads replace tables** on every run.
- **DAGs are triggered manually.**
- **No CI pipeline yet.**

## Tests

```powershell
python -m pytest collect/tests ai/tests
```

One test, which checks the CSV headers, needs the source files in `data/sample/`.

## Data and security

Use synthetic data only. The users file has `email` and `password` columns, so
never load real credentials or personal data. Do not commit `.env`,
`terraform.tfvars`, plan files, key files or source data.