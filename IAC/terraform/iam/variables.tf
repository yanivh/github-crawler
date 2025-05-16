variable "role_name" {
  description = "Name of the IAM role"
  type        = string
}

variable "service_principal" {
  description = "AWS service principal that can assume this role"
  type        = string
  default     = "lambda.amazonaws.com"
}

variable "s3_bucket_arn" {
  description = "ARN of the S3 bucket to grant access to"
  type        = string
}

variable "secret_arn" {
  description = "ARN of the secret to grant access to"
  type        = string
}

variable "s3_actions" {
  description = "List of S3 actions to allow"
  type        = list(string)
  default     = ["s3:PutObject", "s3:GetObject", "s3:ListBucket"]
}

variable "tags" {
  description = "Tags to apply to the IAM role"
  type        = map(string)
  default     = {}
} 