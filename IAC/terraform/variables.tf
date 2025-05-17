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

variable "github_token" {
  description = "GitHub personal access token"
  type        = string
  sensitive   = true
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default = {
    Project = "github-crawler"
  }
}

# Optional Glue job settings that can be overridden
variable "glue_job_timeout" {
  description = "Timeout in minutes for Glue jobs"
  type        = number
  default     = 120 # 2 hours
}

variable "glue_job_workers" {
  description = "Number of workers for Glue jobs"
  type        = number
  default     = 2
}

variable "glue_worker_type" {
  description = "Worker type for Glue jobs"
  type        = string
  default     = "G.1X"
} 