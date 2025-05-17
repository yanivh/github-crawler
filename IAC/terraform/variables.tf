variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (e.g., dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "github_token" {
  description = "GitHub API token"
  type        = string
  sensitive   = true
}

variable "tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default = {
    Project     = "github-crawler"
    Environment = "dev"
    Terraform   = "true"
  }
} 