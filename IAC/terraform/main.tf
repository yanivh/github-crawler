# Get current AWS account ID
data "aws_caller_identity" "current" {}

module "s3_storage" {
  source = "./s3"

  bucket_name = "github-crawler-data-${data.aws_caller_identity.current.account_id}"
  environment = var.environment
  tags        = var.tags
}

module "credentials" {
  source = "./credentials"

  github_token = var.github_token
  environment  = var.environment
  tags         = var.tags
}

module "iam_roles" {
  source = "./iam"

  role_name         = "github-crawler-role"
  service_principal = "lambda.amazonaws.com"
  s3_bucket_arn     = module.s3_storage.bucket_arn
  secret_arn        = module.credentials.github_token_secret_arn
  tags              = var.tags
} 