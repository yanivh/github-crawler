from utils.glue_toolkit import load_glue_context
from utils.github_collector_toolkit import GitHubCollector
from datetime import datetime

def main():
    # Get job arguments
    args = load_glue_context()

    # Initialize collector
    collector = GitHubCollector(
        token_key=args['github_token_secret_name'],
        bucket_name=args['default_s3_bucket']
    )

    # Parse dates
    start_date = datetime.strptime(args['start_date'], '%Y-%m-%d')
    end_date = datetime.strptime(args['end_date'], '%Y-%m-%d')


    # Run transformation
    collector.process_raw_commits(
        owner=args['owner'],
        repo=args['repo'],
        start_date=start_date,
        end_date=end_date
    )

if __name__ == '__main__':
    main() 