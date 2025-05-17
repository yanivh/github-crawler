resource "aws_secretsmanager_secret" "github_token" {
  name        = "github-api-token-${var.environment}"
  description = "GitHub API token for the crawler"
  tags        = var.tags
}

resource "aws_secretsmanager_secret_version" "github_token" {
  secret_id     = aws_secretsmanager_secret.github_token.id
  secret_string = var.github_token
} 