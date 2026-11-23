# Pipeline identity: loads data, runs dbt, writes AI tables
resource "google_service_account" "pipeline" {
  account_id   = "${var.prefix}-pipeline"
  display_name = "GastroFlow pipeline"
}

# Read-only identity for the Text-to-SQL app
resource "google_service_account" "readonly" {
  account_id   = "${var.prefix}-readonly"
  display_name = "GastroFlow read-only analytics"
}

resource "google_project_iam_member" "pipeline_jobs" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_project_iam_member" "pipeline_vertex" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_bigquery_dataset_iam_member" "pipeline_editor" {
  for_each   = local.datasets
  dataset_id = google_bigquery_dataset.ds[each.key].dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_storage_bucket_iam_member" "pipeline_objects" {
  bucket = google_storage_bucket.lake.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_project_iam_member" "readonly_jobs" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.readonly.email}"
}

# Read-only access to marts only (not raw, not users data)
resource "google_bigquery_dataset_iam_member" "readonly_marts" {
  dataset_id = google_bigquery_dataset.ds["marts"].dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.readonly.email}"
}