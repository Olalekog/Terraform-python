output "role_arn" {
  value = aws_iam_role.deployment.arn
}
output "caller_policy_json" {
  value     = data.aws_iam_policy_document.caller.json
  sensitive = true
}
