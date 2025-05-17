terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # For production, you should configure a remote backend
  backend "local" {}
}

provider "aws" {
  region = "us-east-1"  # Default region, can be overridden by environment variables
} 