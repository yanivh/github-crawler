resource "aws_glue_job" "github_extract_job" {
  name     = "github-extract-job-${var.environment}"
  role_arn = aws_iam_role.glue_job_role.arn

  command {
    name            = "pythonshell"
    python_version  = "3.9"
    script_location = "${local.s3_script_base_path}/etl-artifacts/code/github_extract_job.py"
  }

  default_arguments = {
    "--github_token_secret_name"  = var.github_token_secret_name
    "--default_s3_bucket"         = var.default_s3_bucket
    "--end_date"                  = "Today"
    "--start_date"                = "Yesterday"
    "--environment"               = "dev"
    "--owner"                     = "grafana"
    "--repo"                      = "grafana"
    "--extra-py-files"            = "${local.s3_script_base_path}/etl-artifacts/code/utils-0.1-py3-none-any.whl"
    "--additional-python-modules" = "PyGithub==2.2.0,python-dotenv==1.0.1,requests>=2.23.0,<2.27.2,tqdm==4.66.2,pyarrow>=2.0.0,<7.1.0"
    "--TempDir"                   = local.glue_temp_dir
  }

  execution_property {
    max_concurrent_runs = 1
  }

  timeout = var.glue_job_timeout
}

resource "aws_glue_job" "github_transform_job" {
  name     = "github-transform-job-${var.environment}"
  role_arn = aws_iam_role.glue_job_role.arn

  command {
    name            = "pythonshell"
    python_version  = "3.9"
    script_location = "${local.s3_script_base_path}/etl-artifacts/code/github_transform_job.py"
  }

  default_arguments = {
    "--default_s3_bucket"         = var.default_s3_bucket
    "--github_token_secret_name"  = var.github_token_secret_name
    "--end_date"                  = "Today"
    "--start_date"                = "Yesterday"
    "--environment"               = "dev"
    "--owner"                     = "grafana"
    "--repo"                      = "grafana"
    "--TempDir"                   = local.glue_temp_dir
    "--extra-py-files"            = "${local.s3_script_base_path}/etl-artifacts/code/utils-0.1-py3-none-any.whl"
    "--additional-python-modules" = "PyGithub==2.2.0,python-dotenv==1.0.1,requests>=2.23.0,<2.27.2,tqdm==4.66.2,pyarrow>=2.0.0,<7.1.0"
  }

  execution_property {
    max_concurrent_runs = 1
  }

  timeout = var.glue_job_timeout
} 