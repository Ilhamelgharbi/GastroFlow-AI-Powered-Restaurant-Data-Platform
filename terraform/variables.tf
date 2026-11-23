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
  default     = true
  description = "Allow destroy to delete non-empty bucket and datasets (dev only)"
}

variable "enable_composer" {
  type    = bool
  default = false
}