# Uses the real provider's local policy-document builder; no AWS API calls.
provider "aws" {
  region                      = "us-east-1"
  access_key                  = "test"
  secret_key                  = "test"
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_metadata_api_check     = true
}
override_data {
  target = data.aws_caller_identity.target
  values = {
    account_id = "222222222222"
    arn        = "arn:aws:iam::222222222222:user/test"
    user_id    = "test"
  }
}
variables {
  role_name       = "test-deploy"
  source_role_arn = "arn:aws:iam::111111111111:role/pipeline"
  external_id     = "test-unique-external-id"
  permissions = [{
    sid       = "Artifacts"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["arn:aws:s3:::example-bucket/releases/dev/*"]
  }]
}
run "scoped_role_and_trust" {
  command = plan
  assert {
    condition     = jsondecode(aws_iam_role.deployment.assume_role_policy).Statement[0].Principal.AWS == var.source_role_arn
    error_message = "Trust must bind the exact source role."
  }
  assert {
    condition     = jsondecode(aws_iam_role.deployment.assume_role_policy).Statement[0].Condition.StringEquals["sts:ExternalId"] == var.external_id
    error_message = "Trust must require the exact external ID."
  }
  assert {
    condition     = jsondecode(aws_iam_role_policy.deployment.policy).Statement[0].Resource == "arn:aws:s3:::example-bucket/releases/dev/*"
    error_message = "Deployment permissions must remain prefix-scoped."
  }
  assert {
    condition     = aws_iam_role.deployment.max_session_duration == 3600
    error_message = "Role chaining duration must be bounded."
  }
}
run "reject_same_account" {
  command = plan
  variables { source_role_arn = "arn:aws:iam::222222222222:role/pipeline" }
  expect_failures = [aws_iam_role.deployment]
}
run "reject_empty_external_id" {
  command = plan
  variables { external_id = "" }
  expect_failures = [var.external_id]
}
run "reject_wildcard_action" {
  command = plan
  variables {
    permissions = [{ sid = "Bad", actions = ["s3:*"], resources = ["arn:aws:s3:::example-bucket/releases/*"] }]
  }
  expect_failures = [var.permissions]
}
run "reject_global_resource" {
  command = plan
  variables {
    permissions = [{ sid = "Bad", actions = ["s3:GetObject"], resources = ["*"] }]
  }
  expect_failures = [var.permissions]
}
run "reject_wildcard_principal" {
  command = plan
  variables { source_role_arn = "arn:aws:iam::111111111111:role/*" }
  expect_failures = [var.source_role_arn]
}
