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

module "glue_jobs" {
  source = "./glue"

  environment              = var.environment
  aws_region               = var.aws_region
  default_s3_bucket        = module.s3_storage.bucket_id
  github_token_secret_name = module.credentials.github_token_secret_name
  glue_job_timeout         = var.glue_job_timeout
}

module "github_actions" {
  source = "./github-actions"

  github_org  = "yanivh" # Correct GitHub organization name
  github_repo = "github-crawler"
  s3_bucket   = module.s3_storage.bucket_id
  tags        = var.tags
}