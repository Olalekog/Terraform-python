variable "role_name" {
  type = string
  validation {
    condition     = can(regex("^[A-Za-z0-9_+=,.@-]{1,64}$", var.role_name))
    error_message = "Use a valid IAM role name of at most 64 characters."
  }
}
variable "source_role_arn" {
  type = string
  validation {
    condition     = can(regex("^arn:(aws|aws-us-gov|aws-cn):iam::[0-9]{12}:role/[A-Za-z0-9_+=,.@/-]+$", var.source_role_arn))
    error_message = "Provide one exact IAM role ARN, without wildcards."
  }
}
variable "external_id" {
  type      = string
  sensitive = true
  validation {
    condition     = can(regex("^[A-Za-z0-9_+=,.@:/-]{2,1224}$", var.external_id))
    error_message = "External ID must be 2-1224 valid STS characters."
  }
}
variable "permissions" {
  description = "Explicit allow statements. Scope resources narrowly; wildcard actions and global resources are rejected."
  type = list(object({
    sid       = string
    actions   = list(string)
    resources = list(string)
    conditions = optional(list(object({
      test     = string
      variable = string
      values   = list(string)
    })), [])
  }))
  validation {
    condition = length(var.permissions) > 0 && alltrue([
      for s in var.permissions : length(s.actions) > 0 && length(s.resources) > 0 &&
      can(regex("^[A-Za-z0-9]+$", s.sid)) &&
      alltrue([for a in s.actions : can(regex("^[A-Za-z0-9-]+:[A-Za-z0-9]+$", a))]) &&
      alltrue([for r in s.resources : can(regex("^arn:(aws|aws-us-gov|aws-cn):[a-z0-9-]+:[a-z0-9-]*:[0-9]*:.+$", r)) && !strcontains(r, "?") &&
      (!strcontains(r, "*") || (endswith(r, "*") && length(split("*", r)) == 2))])
    ]) && length(distinct([for s in var.permissions : s.sid])) == length(var.permissions)
    error_message = "Use unique alphanumeric SIDs, exact actions, and resource ARNs with at most one trailing prefix wildcard."
  }
}
variable "permissions_boundary_arn" {
  type    = string
  default = null
}
variable "tags" {
  type    = map(string)
  default = {}
}
