data "google_project" "this" {
  project_id = var.project_id
}

resource "google_service_account" "composer" {
  count        = var.enable_composer ? 1 : 0
  account_id   = "${var.prefix}-composer"
  display_name = "GastroFlow Composer runtime"

  depends_on = [google_project_service.apis]
}

resource "google_project_iam_member" "composer_worker" {
  count   = var.enable_composer ? 1 : 0
  project = var.project_id
  role    = "roles/composer.worker"
  member  = "serviceAccount:${google_service_account.composer[0].email}"
}

resource "google_project_iam_member" "composer_jobs" {
  count   = var.enable_composer ? 1 : 0
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.composer[0].email}"
}

resource "google_project_iam_member" "composer_vertex" {
  count   = var.enable_composer ? 1 : 0
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.composer[0].email}"
}

resource "google_project_iam_member" "composer_service_agent" {
  count   = var.enable_composer ? 1 : 0
  project = var.project_id
  role    = "roles/composer.ServiceAgentV2Ext"
  member  = "serviceAccount:service-${data.google_project.this.number}@cloudcomposer-accounts.iam.gserviceaccount.com"

  depends_on = [google_project_service.apis]
}

resource "google_bigquery_dataset_iam_member" "composer_editor" {
  for_each = var.enable_composer ? toset(["raw", "staging", "marts", "snapshots", "ai"]) : toset([])

  dataset_id = google_bigquery_dataset.ds[each.key].dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.composer[0].email}"
}

resource "google_storage_bucket_iam_member" "composer_lake_reader" {
  count  = var.enable_composer ? 1 : 0
  bucket = google_storage_bucket.lake.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.composer[0].email}"
}

resource "google_composer_environment" "this" {
  count  = var.enable_composer ? 1 : 0
  name   = "${var.prefix}-composer"
  region = var.region

  config {
    environment_size = "ENVIRONMENT_SIZE_SMALL"

    software_config {
      image_version = var.composer_image_version
      env_variables = {
        GASTROFLOW_ENABLE_AI            = "false"
        GASTROFLOW_ENV                  = "composer"
        GASTROFLOW_PREFIX               = var.prefix
        GASTROFLOW_PROJECT_ID           = var.project_id
        GASTROFLOW_REGION               = var.region
        GASTROFLOW_GCS_BUCKET           = google_storage_bucket.lake.name
        GASTROFLOW_GCS_PREFIX           = "raw/"
        GASTROFLOW_BQ_RAW_DATASET       = google_bigquery_dataset.ds["raw"].dataset_id
        GASTROFLOW_DBT_DATASET          = google_bigquery_dataset.ds["staging"].dataset_id
        GASTROFLOW_BQ_SNAPSHOTS_DATASET = google_bigquery_dataset.ds["snapshots"].dataset_id
        GASTROFLOW_BQ_AI_DATASET        = google_bigquery_dataset.ds["ai"].dataset_id
      }
    }

    node_config {
      service_account = google_service_account.composer[0].email
    }
  }

  lifecycle {
    precondition {
      condition     = trimspace(var.composer_image_version) != ""
      error_message = "Set composer_image_version to an image supported in the selected region."
    }
  }

  depends_on = [
    google_project_service.apis,
    google_project_iam_member.composer_worker,
    google_project_iam_member.composer_jobs,
    google_project_iam_member.composer_vertex,
    google_project_iam_member.composer_service_agent,
    google_bigquery_dataset_iam_member.composer_editor,
    google_storage_bucket_iam_member.composer_lake_reader,
  ]
}

locals {
  composer_bucket = var.enable_composer ? split(
    "/",
    trimprefix(google_composer_environment.this[0].config[0].dag_gcs_prefix, "gs://"),
  )[0] : ""

  composer_dag_dir     = "${path.module}/../airflow/dags"
  composer_collect_dir = "${path.module}/../collect"
  composer_ai_dir      = "${path.module}/../ai"
  composer_dbt_dir     = "${path.module}/../transformation"
  composer_profile     = "${path.module}/../airflow/dbt/profiles.yml.example"

  composer_collect_files = var.enable_composer ? [
    for file in fileset(local.composer_collect_dir, "**/*.py") : file
    if !startswith(file, "tests/")
  ] : []

  composer_ai_files = var.enable_composer ? [
    for file in fileset(local.composer_ai_dir, "**/*.py") : file
    if !startswith(file, "tests/")
  ] : []

  composer_dbt_files = var.enable_composer ? [
    for file in fileset(local.composer_dbt_dir, "**") : file
    if !anytrue([
      for excluded in ["target/", "logs/", "dbt_packages/"] : startswith(file, excluded)
    ])
    && !endswith(file, ".gitkeep")
    && file != ".user.yml"
    && file != ".gitignore"
  ] : []
}

resource "google_storage_bucket_object" "composer_dag" {
  for_each = var.enable_composer ? fileset(local.composer_dag_dir, "*.py") : toset([])

  bucket  = local.composer_bucket
  name    = "dags/${each.value}"
  content = file("${local.composer_dag_dir}/${each.value}")
}

resource "google_storage_bucket_object" "composer_collect" {
  for_each = toset(local.composer_collect_files)

  bucket  = local.composer_bucket
  name    = "dags/collect/${each.value}"
  content = file("${local.composer_collect_dir}/${each.value}")
}

resource "google_storage_bucket_object" "composer_ai" {
  for_each = toset(local.composer_ai_files)

  bucket  = local.composer_bucket
  name    = "dags/ai/${each.value}"
  content = file("${local.composer_ai_dir}/${each.value}")
}

resource "google_storage_bucket_object" "composer_airflowignore" {
  count = var.enable_composer ? 1 : 0

  bucket  = local.composer_bucket
  name    = "dags/.airflowignore"
  content = "collect/\nai/\n"
}

resource "google_storage_bucket_object" "composer_dbt" {
  for_each = toset(local.composer_dbt_files)

  bucket  = local.composer_bucket
  name    = "data/transformation/${each.value}"
  content = file("${local.composer_dbt_dir}/${each.value}")
}

resource "google_storage_bucket_object" "composer_dbt_profile" {
  count = var.enable_composer ? 1 : 0

  bucket  = local.composer_bucket
  name    = "data/dbt_profiles/profiles.yml"
  content = file(local.composer_profile)
}
