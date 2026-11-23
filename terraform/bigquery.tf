resource "google_bigquery_dataset" "ds" {
  for_each                   = local.datasets
  dataset_id                 = "${var.prefix}_${each.key}"
  location                   = var.region
  delete_contents_on_destroy = var.force_destroy
  description                = "GastroFlow ${each.key} layer"

  labels = {
    project = var.prefix
    layer   = each.key
  }

  depends_on = [google_project_service.apis]
}