resource "aws_iam_role" "github_crawler" {
  name = var.role_name

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = var.service_principal
        }
      }
    ]
  })

  tags = var.tags
}

# Policy for S3 access
resource "aws_iam_role_policy" "s3_access" {
  name = "${var.role_name}-s3-policy"
  role = aws_iam_role.github_crawler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          var.s3_bucket_arn,
          "${var.s3_bucket_arn}/*"
        ]
      }
    ]
  })
}

# Policy for Secrets Manager access
resource "aws_iam_role_policy" "secrets_access" {
  name = "${var.role_name}-secrets-policy"
  role = aws_iam_role.github_crawler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [var.secret_arn]
      }
    ]
  })
} 