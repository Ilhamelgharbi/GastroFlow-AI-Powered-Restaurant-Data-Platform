variable "project_id" {
  type        = string
  description = "GCP project id"
}

variable "region" {
  type        = string
  default     = "europe-west1"
  description = "Region for GCS and BigQuery (must match so load jobs work)"
}

variable "prefix" {
  type    = string
  default = "gastroflow"
}

variable "force_destroy" {
  type        = bool
  default     = false
  description = "Allow Terraform to delete non-empty buckets and datasets"
}

variable "enable_composer" {
  type    = bool
  default = false
}

variable "composer_image_version" {
  type        = string
  default     = ""
  description = "Pinned Composer image version; required when enable_composer is true"
}

variable "gemini_api_key" {
  description = "Gemini Developer API key"
  type        = string
  sensitive   = true
  default     = ""
}