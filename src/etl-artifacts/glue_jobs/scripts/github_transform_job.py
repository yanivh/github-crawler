import sys
from awsglue.utils import getResolvedOptions
from datetime import datetime
from src.utils.github_collector_toolkit import GitHubCollector

def main():
    # Get job arguments
    args = getResolvedOptions(sys.argv, [
        'start_date',
        'end_date',
        'github_token_secret_name',
        'default_s3_bucket',
        'owner',
        'repo',
        'environment'
    ])
    
    # Parse dates
    start_date = datetime.strptime(args['start_date'], '%Y-%m-%d')
    end_date = datetime.strptime(args['end_date'], '%Y-%m-%d')
    
    # Initialize collector
    collector = GitHubCollector(
        bucket_name=args['DEFAULT_S3_BUCKET']
    )
    
    # Run transformation
    collector.process_raw_commits(
        owner=args['owner'],
        repo=args['repo'],
        start_date=start_date,
        end_date=end_date
    )

if __name__ == '__main__':
    main() 