resource "google_storage_bucket" "lake" {
  name                        = "${var.project_id}-${var.prefix}-lake"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = var.force_destroy

  versioning {
    enabled = true
  }

  depends_on = [google_project_service.apis]
}