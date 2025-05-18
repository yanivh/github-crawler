import sys
from awsglue.utils import getResolvedOptions
from datetime import datetime
from utils.github_collector_toolkit import GitHubCollector

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
        token_key=args['github_token_secret_name'],
        bucket_name=args['default_s3_bucket']
    )
    
    # Run collection
    collector.collect_repository_commits(
        repo_name=f"{args['owner']}/{args['repo']}",
        since=start_date,
        until=end_date
    )

if __name__ == '__main__':
    main() 