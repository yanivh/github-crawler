terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.98.0"
    }
  }

  # For production, you should configure a remote backend
  backend "local" {}
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "github-crawler"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
} 