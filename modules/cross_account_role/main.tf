data "aws_caller_identity" "target" {}

data "aws_iam_policy_document" "trust" {
  statement {
    sid     = "ExactPipelineRoleWithExternalId"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = [var.source_role_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = [var.external_id]
    }
  }
}
resource "aws_iam_role" "deployment" {
  name                 = var.role_name
  assume_role_policy   = data.aws_iam_policy_document.trust.json
  max_session_duration = 3600
  permissions_boundary = var.permissions_boundary_arn
  tags                 = var.tags
  lifecycle {
    precondition {
      condition     = split(":", var.source_role_arn)[4] != data.aws_caller_identity.target.account_id
      error_message = "Source and target must be different accounts."
    }
  }
}
data "aws_iam_policy_document" "deployment" {
  dynamic "statement" {
    for_each = var.permissions
    content {
      sid       = statement.value.sid
      effect    = "Allow"
      actions   = statement.value.actions
      resources = statement.value.resources
      dynamic "condition" {
        for_each = statement.value.conditions
        content {
          test     = condition.value.test
          variable = condition.value.variable
          values   = condition.value.values
        }
      }
    }
  }
}
resource "aws_iam_role_policy" "deployment" {
  name   = "ScopedDeployment"
  role   = aws_iam_role.deployment.id
  policy = data.aws_iam_policy_document.deployment.json
}
# Attach this policy to the existing source role using the source-account provider.
data "aws_iam_policy_document" "caller" {
  statement {
    sid       = "AssumeExactTarget"
    actions   = ["sts:AssumeRole"]
    resources = [aws_iam_role.deployment.arn]
    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = [var.external_id]
    }
  }
}
