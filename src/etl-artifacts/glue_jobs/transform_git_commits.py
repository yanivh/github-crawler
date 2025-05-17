import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Set
from src.utils.s3_toolkit import S3
from src.utils.github_collector_toolkit import GitHubCollector


def main():
    """Main function to run the transformation job."""
    try:
        # Configuration
        bucket_name = "github-crawler-data-590183923818"  # You can make this configurable
        owner = "grafana"  # You can make these configurable
        repo = "grafana"
        start_date = datetime(2025, 1, 1)  # You can make these configurable
        end_date = datetime(2025, 1, 5)
        
        print(f"Starting commit transformation for {owner}/{repo}")
        print(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        
        # Initialize collector with S3 client
        collector = GitHubCollector(token_key="github-api-token-dev", bucket_name=bucket_name)
        
        # Process commits
        collector.process_raw_commits_2(owner, repo, start_date, end_date)
        
        print("Transformation completed successfully!")
        
    except Exception as e:
        print(f"Error in transformation job: {e}")
        raise

if __name__ == "__main__":
    main()

