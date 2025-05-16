output "bucket_arn" {
  description = "ARN of the created S3 bucket"
  value       = aws_s3_bucket.github_data.arn
}

output "bucket_id" {
  description = "ID (name) of the created S3 bucket"
  value       = aws_s3_bucket.github_data.id
} 