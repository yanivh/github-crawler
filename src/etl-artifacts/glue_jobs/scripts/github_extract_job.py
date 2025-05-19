from src.utils.glue_toolkit import load_glue_context
from src.utils.github_collector_toolkit import GitHubCollector

def main():
    # Get job arguments
    args = load_glue_context()
    
    # Initialize collector
    collector = GitHubCollector(
        token_key=args['github_token_secret_name'],
        bucket_name=args['default_s3_bucket']
    )
    
    # Run collection
    collector.collect_repository_commits(
        repo_name=f"{args['owner']}/{args['repo']}",
        since=args['start_date'],
        until=args['end_date']
    )

if __name__ == '__main__':
    main() 