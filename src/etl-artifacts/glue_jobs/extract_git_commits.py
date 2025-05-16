from datetime import datetime
from src.utils.github_collector_toolkit  import GitHubCollector


def main():
    # Initialize collector
    github_secret_manager = "github-api-token-dev"
    bucket_name = "github-crawler-data-590183923818"
    collector = GitHubCollector(github_secret_manager, bucket_name)

    # Example repositories to collect from
    repositories = [
        "grafana/grafana"
    ]

    # Collect commits from each repository
    for repo_name in repositories:
        print(f"\nCollecting commits from {repo_name}")
        collector.collect_repository_commits(
            repo_name,
            since=datetime(2025, 1, 1),
            until=datetime(2025, 1, 5),
            max_commits_per_date=4  # Collect up to N commits per date, use -1 for unlimited
        )


if __name__ == "__main__":
    main() 