variable "environment" {
  description = "Environment name (e.g., dev, prod)"
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "glue_job_timeout" {
  description = "Timeout in minutes for Glue jobs"
  type        = number
  default     = 60
}

variable "github_token_secret_name" {
  description = "Name of the secret containing GitHub token"
  type        = string
}

variable "default_s3_bucket" {
  description = "Default S3 bucket for data storage"
  type        = string
  default     = "github-crawler-data-590183923818"
}
