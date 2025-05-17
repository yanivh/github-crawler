output "extract_job_name" {
  description = "Name of the GitHub extract Glue job"
  value       = aws_glue_job.github_extract_job.name
}

output "transform_job_name" {
  description = "Name of the GitHub transform Glue job"
  value       = aws_glue_job.github_transform_job.name
}

output "glue_role_arn" {
  description = "ARN of the IAM role used by Glue jobs"
  value       = aws_iam_role.glue_job_role.arn
}

output "glue_job_script_locations" {
  description = "S3 locations of the Glue job scripts"
  value = {
    extract_job   = aws_glue_job.github_extract_job.command[0].script_location
    transform_job = aws_glue_job.github_transform_job.command[0].script_location
  }
} 