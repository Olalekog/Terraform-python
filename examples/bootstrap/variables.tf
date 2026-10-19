variable "source_account_id" {
  type = string
  validation {
    condition     = can(regex("^[0-9]{12}$", var.source_account_id))
    error_message = "Provide a 12-digit account ID."
  }
}
variable "target_account_id" {
  type = string
  validation {
    condition     = can(regex("^[0-9]{12}$", var.target_account_id))
    error_message = "Provide a 12-digit account ID."
  }
}
variable "source_role_name" { type = string }
variable "source_admin_profile" { type = string }
variable "target_admin_profile" { type = string }
variable "region" {
  type    = string
  default = "us-east-1"
}
variable "external_id" {
  type      = string
  sensitive = true
}
variable "artifact_bucket" {
  type = string
  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$", var.artifact_bucket))
    error_message = "Provide a literal S3 bucket name without ARN or wildcards."
  }
}
variable "artifact_prefix" {
  type    = string
  default = "releases/dev"
  validation {
    condition     = can(regex("^[A-Za-z0-9_-]+(/[A-Za-z0-9_-]+)*$", var.artifact_prefix))
    error_message = "Use a nonempty literal path without wildcards or leading/trailing slashes."
  }
}
