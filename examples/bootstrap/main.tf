terraform {
  required_version = ">= 1.6.0, < 2.0.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0, < 7.0"
    }
  }
}
# Bootstrap credentials are separate from the runtime deployment role.
provider "aws" {
  alias               = "source"
  region              = var.region
  profile             = var.source_admin_profile
  allowed_account_ids = [var.source_account_id]
}
provider "aws" {
  alias               = "target"
  region              = var.region
  profile             = var.target_admin_profile
  allowed_account_ids = [var.target_account_id]
}
data "aws_iam_role" "pipeline" {
  provider = aws.source
  name     = var.source_role_name
}
module "target" {
  source          = "../../modules/cross_account_role"
  providers       = { aws = aws.target }
  role_name       = "cicd-artifact-dev"
  source_role_arn = data.aws_iam_role.pipeline.arn
  external_id     = var.external_id
  tags            = { Environment = "dev", ManagedBy = "Terraform" }
  permissions = [
    {
      sid        = "ListArtifactPrefix"
      actions    = ["s3:ListBucket"]
      resources  = ["arn:aws:s3:::${var.artifact_bucket}"]
      conditions = [{ test = "StringLike", variable = "s3:prefix", values = ["${var.artifact_prefix}/*"] }]
    },
    {
      sid       = "ReadWriteArtifacts"
      actions   = ["s3:GetObject", "s3:PutObject"]
      resources = ["arn:aws:s3:::${var.artifact_bucket}/${var.artifact_prefix}/*"]
    }
  ]
}
resource "aws_iam_role_policy" "assume_target" {
  provider = aws.source
  name     = "AssumeArtifactDev"
  role     = data.aws_iam_role.pipeline.name
  policy   = module.target.caller_policy_json
}
output "target_role_arn" { value = module.target.role_arn }
output "source_role_arn" { value = data.aws_iam_role.pipeline.arn }
