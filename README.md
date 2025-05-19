# GitHub Crawler

A tool for collecting commit data from GitHub repositories for training ML models.

## Overview

This project is designed to collect and process GitHub commit data for ML model training. It crawls repositories, extracts commit information, and stores it in a structured format optimized for ML training purposes.

## Architecture

The project follows a modern data pipeline architecture:

1. **Data Collection Layer**
   - GitHub API integration for fetching repository data
   - Rate limit handling and pagination
     - Standard rate limit: 5,000 requests per hour for personal access tokens
     - Higher limits available with GitHub Enterprise accounts
     - Rate limit monitoring and automatic throttling
   - Raw data storage in S3

2. **Data Processing Layer**
   - AWS Glue jobs for ETL processing
   - Data transformation and enrichment
   - Optimized storage format for ML training

3. **Infrastructure**
   - AWS S3 for data storage
   - AWS Glue for ETL jobs
   - AWS Secrets Manager for secure credential management
   - Infrastructure as Code (Terraform) for deployment

## Data Schema

The processed data is stored in a flattened schema optimized for ML training. Each record represents a file change within a commit:

```json
{
    "commit_sha": "string",
    "author_name": "string",
    "message": "string",
    "file_path": "string",
    "status": "string",
    "content_before": "string",
    "content_after": "string",
    "changes": "integer",
    "additions": "integer",
    "deletions": "integer",
    "file_type": "string",
    "unified_diff": "string",
    "directory_category": "string",
    "change_complexity": "float",
    "commit_overall_files_changed": "integer",
    "commit_overall_lines_changed": "integer"
}
```

### Schema Details

- **Commit Metadata**
  - `commit_sha`: Unique identifier for the commit
  - `author_name`: Name of the commit author
  - `message`: Commit message

- **File Metadata**
  - `file_path`: Path of the modified file
  - `status`: Change status (added, modified, removed)
  - `content_before`: File content before the commit
  - `content_after`: File content after the commit
  - `changes`: Total number of changes
  - `additions`: Number of lines added
  - `deletions`: Number of lines deleted
  - `file_type`: File extension
  - `unified_diff`: Unified diff format of changes

- **ML Features**
  - `directory_category`: Category of the directory
  - `change_complexity`: Complexity score of the change (0-1)
    - Higher score (closer to 1) means more complex change
    - Lower score (closer to 0) means simpler change
    - Calculated based on:
      - Number of change chunks
      - Mix of additions and deletions
      - Spread of changes across the file
  - `commit_overall_files_changed`: Total files changed in commit
  - `commit_overall_lines_changed`: Total lines changed in commit

## Setup

This project uses a Python virtual environment to manage dependencies.

See [Virtual Environment Setup](VIRTUAL_ENV_SETUP.md) for instructions on how to set up and use the virtual environment.

### Prerequisites

- Python 3.9+
- AWS Account with appropriate permissions
- GitHub API token
- Terraform (for infrastructure deployment)

### Configuration

1. Set up AWS credentials
2. Configure GitHub API token in AWS Secrets Manager
3. Update Terraform variables as needed

### Deployment

1. Initialize Terraform:
```bash
cd IAC/terraform
terraform init
```

2. Apply infrastructure:
```bash
terraform apply
```

## Usage

The project provides two main ETL jobs:

1. **Extract Job**: Collects raw commit data from GitHub
2. **Transform Job**: Processes raw data into ML-optimized format

Jobs can be triggered manually or scheduled via AWS Glue.

## Scaling Considerations

### AWS Glue Job Concurrency

1. **Job-Level Settings**
   - Maximum concurrency: Controls parallel job instances
   - Default: 1 concurrent run
   - Configurable up to 50 concurrent runs per job
   - Additional invocations are queued

2. **Account-Level Limits**
   - Default: 10 concurrent jobs across all Glue jobs
   - Applies per AWS account and region
   - Quota increases available through AWS Service Quotas Console

3. **Resource Constraints**
   - Limited by available DPUs (Data Processing Units)
   - Jobs may queue if insufficient DPUs
   - Automatic resource management

## Implementation Roadmap

1. **Phase 1: Core Infrastructure**
   - Set up S3 storage buckets
   - Implement data schema
   - Create GitHub API integration

2. **Phase 2: Data Collection**
   - Implement repository selection
   - Build commit extraction pipeline
   - Develop file content storage

3. **Phase 3: Scaling and Optimization**
   - Implement distributed processing
   - Add incremental updates
   - Optimize storage usage

4. **Phase 4: Advanced Features**
   - Add filtering capabilities
   - Implement repository state reconstruction
   - Develop analytics features
