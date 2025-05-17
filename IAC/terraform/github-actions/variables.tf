variable "github_org" {
  description = "GitHub organization name"
  type        = string
  default     = "yanivh"
}

variable "github_repo" {
  description = "GitHub repository name"
  type        = string
  default     = "github-crawler"
}

variable "s3_bucket" {
  description = "S3 bucket name for artifacts"
  type        = string
  default     = "github-crawler-data-590183923818"
}

variable "s3_prefix" {
  description = "S3 prefix for artifacts"
  type        = string
  default     = "etl-artifacts/code"
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
} 