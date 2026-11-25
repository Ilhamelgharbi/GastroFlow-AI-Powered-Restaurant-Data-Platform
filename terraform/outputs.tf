output "bucket_name" {
  value = google_storage_bucket.lake.name
}

output "datasets" {
  value = { for k, d in google_bigquery_dataset.ds : k => d.dataset_id }
}

output "pipeline_sa" {
  value = google_service_account.pipeline.email
}

output "readonly_sa" {
  value = google_service_account.readonly.email
}

output "composer_airflow_uri" {
  value = var.enable_composer ? google_composer_environment.this[0].config[0].airflow_uri : null
}

output "composer_bucket" {
  value = var.enable_composer ? local.composer_bucket : null
}