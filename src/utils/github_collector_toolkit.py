import os
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from github import Github
from github.Repository import Repository
from github.Commit import Commit
from github.ContentFile import ContentFile
from github.GithubException import GithubException, RateLimitExceededException

from src.utils.secrets_manger_toolkit import SecretsManager
from src.utils.s3_toolkit import S3


class GitHubCollector:
    def __init__(self, token_key: str, bucket_name: str = "github-crawler-data-590183923818"):
        """
        Initialize the GitHub collector
        
        Args:
            token_key: Key for GitHub API token in Secrets Manager
            bucket_name: Name of the S3 bucket to store data
            output_dir: Directory to store collected data locally (as backup)
        """
        # Extract token from AWS Secrets Manager
        self.secrets_manager = SecretsManager()
        self.github_access_token = self.secrets_manager.get_secret(token_key)
        secret = self.github_access_token['SecretString']

        # Initialize GitHub client
        self.github = Github(secret)
        
        # Initialize S3 client
        self.s3_client = S3(bucket_name)

        
    def check_rate_limit(self, force_check=False):
        """
        Check current rate limit status and wait if necessary
        
        Args:
            force_check: If True, always check the rate limit. If False, only check every 10 calls.
        
        Returns:
            bool: True if we can proceed, False if we should abort
        """
        # Use class variable to track number of calls since last check
        if not hasattr(self, '_calls_since_check'):
            self._calls_since_check = 0
            
        # Only check every 10 calls unless forced
        if not force_check:
            self._calls_since_check += 1
            if self._calls_since_check < 10:
                return True
            
        self._calls_since_check = 0
            
        try:
            rate_limit = self.github.get_rate_limit()
            core_rate = rate_limit.core
            
            if core_rate.remaining < 100:  # Warning when getting low
                print(f"\nWarning: Only {core_rate.remaining} API calls remaining")
            
            if core_rate.remaining == 0:
                reset_timestamp = core_rate.reset.timestamp()
                current_timestamp = time.time()
                sleep_time = int(reset_timestamp - current_timestamp) + 1
                
                if sleep_time > 3600:  # If wait time is more than 1 hour
                    print(f"\nRate limit exceeded. Reset time is too long ({sleep_time} seconds). Aborting.")
                    return False
                elif sleep_time > 0:
                    print(f"\nRate limit reached. Waiting {sleep_time} seconds for reset...")
                    # Wait in smaller intervals to allow for keyboard interrupt
                    while sleep_time > 0:
                        time.sleep(min(30, sleep_time))  # Wait in 30-second chunks
                        sleep_time -= 30
                        if sleep_time > 0:
                            print(f"Still waiting... {sleep_time} seconds remaining")
                return True
                
            return True
            
        except Exception as e:
            print(f"Error checking rate limit: {e}")
            return False

    def get_repository(self, repo_name: str) -> Optional[Repository]:
        """
        Get repository by name
        
        Args:
            repo_name: Repository name in format 'owner/repo'
            
        Returns:
            Repository object or None if not found
        """
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                if not self.check_rate_limit():
                    return None
                return self.github.get_repo(repo_name)
            except RateLimitExceededException as e:
                print(f"Rate limit exceeded while getting repository: {e}")
                retry_count += 1
                if retry_count < max_retries and self.check_rate_limit():
                    continue
                return None
            except GithubException as e:
                print(f"Error getting repository {repo_name}: {e}")
                raise
            except Exception as e:
                print(f"Unexpected error getting repository: {e}")
                raise

    def get_file_content(self, repo: Repository, file_path: str, commit_sha: str) -> Optional[str]:
        """
        Get file content at specific commit
        
        Args:
            repo: Repository object
            file_path: Path to the file
            commit_sha: Commit SHA
            
        Returns:
            File content as string or None if not found
        """
        try:
            if not self.check_rate_limit():
                return None
            content = repo.get_contents(file_path, ref=commit_sha)
            if isinstance(content, list):
                return None  # Directory, not a file
            return content.decoded_content.decode('utf-8')
        except RateLimitExceededException:
            if not self.check_rate_limit():
                return None
            return self.get_file_content(repo, file_path, commit_sha)
        except GithubException as e:
            if e.status == 404:  # File not found is expected in some cases
                return None
            print(f"Error getting file content for {file_path} at {commit_sha}: {e}")
            raise  # Re-raise other exceptions

    def collect_commit_data(self, repo: Repository, commit: Commit) -> Dict:
        """
        Collect detailed data for a specific commit
        
        Args:
            repo: Repository object
            commit: Commit object
            
        Returns:
            Dictionary containing commit data
        """
        files_data = []
        for file in commit.files:
            file_data = {
                'filename': file.filename,
                'status': file.status,
                'additions': file.additions,
                'deletions': file.deletions,
                'changes': file.changes,
            }
            
            # Get file content before and after commit
            if file.status != "removed":
                file_data['content_after'] = self.get_file_content(repo, file.filename, commit.sha)
            if file.status != "added" and commit.parents:
                file_data['content_before'] = self.get_file_content(repo, file.filename, commit.parents[0].sha)
                
            files_data.append(file_data)

        return {
            'sha': commit.sha,
            'author': {
                'name': commit.commit.author.name,
                'email': commit.commit.author.email,
                'date': commit.commit.author.date.isoformat()
            },
            'committer': {
                'name': commit.commit.committer.name,
                'email': commit.commit.committer.email,
                'date': commit.commit.committer.date.isoformat()
            },
            'message': commit.commit.message,
            'files': files_data,
            'stats': {
                'additions': commit.stats.additions,
                'deletions': commit.stats.deletions,
                'total': commit.stats.total
            }
        }

    def collect_repository_commits(self, repo_name: str, 
                                 since: Optional[datetime] = None,
                                 until: Optional[datetime] = None,
                                 max_commits_per_date: Optional[int] = None) -> None:
        """
        Collect commits from a repository and store them in S3
        
        Args:
            repo_name: Repository name in format 'owner/repo'
            since: Collect commits after this date (inclusive)
            until: Collect commits before this date (inclusive)
            max_commits_per_date: Maximum number of commits to collect per date, use -1 for unlimited
        """
        try:
            print(f"\nStarting collection for {repo_name}")
            repo = self.get_repository(repo_name)
            if not repo:
                print("Failed to get repository. Aborting.")
                return

            # Print initial rate limit info
            if not self.check_rate_limit(force_check=True):
                print("Initial rate limit check failed. Aborting.")
                return

            try:
                # Print date range info
                if since and until:
                    print(f"Requested date range: since {since.strftime('%Y-%m-%d')} until {until.strftime('%Y-%m-%d')}")

                # Get all commits first
                print("Fetching commits...")
                commits = list(repo.get_commits(since=since, until=until))
                total_commits = len(commits)
                print(f"Found {total_commits} total commits in date range")
                
                if max_commits_per_date != -1:
                    print(f"Will collect up to {max_commits_per_date} commits per date")
                else:
                    print("Will collect all commits")

                # Initialize tracking
                date_counts = {}
                processed_commits = 0

                # Process commits
                print("\nProcessing commits...")
                for commit in commits:
                    try:
                        # Check rate limit periodically
                        if not self.check_rate_limit():
                            print("\nAborting due to rate limit constraints")
                            break

                        # Get commit date first to check if we need it
                        commit_date = commit.commit.author.date.strftime('%Y-%m-%d')
                        current_count = date_counts.get(commit_date, 0)

                        # Skip if we already have enough commits for this date
                        if max_commits_per_date != -1 and current_count >= max_commits_per_date:
                            continue

                        # Collect full commit data
                        commit_data = self.collect_commit_data(repo, commit)
                        
                        # Save to S3
                        s3_key = f"datalake/raw/github/owner={repo.owner.login}/repo={repo.name}/commits/date={commit_date}/{commit.sha}.json"
                        if not self.s3_client.save_json_to_s3(s3_key, commit_data):
                            print(f"Failed to save commit {commit.sha} to S3")
                            continue

                        # Update tracking
                        date_counts[commit_date] = current_count + 1
                        processed_commits += 1
                        
                        print(f"Processed commit {commit.sha} for date {commit_date}")

                    except GithubException as e:
                        print(f"\nError processing commit {commit.sha}: {e}")
                        if isinstance(e, RateLimitExceededException):
                            if not self.check_rate_limit(force_check=True):
                                print("\nAborting due to rate limit constraints")
                                break
                        else:
                            raise

                # Print summary
                print("\nCollection completed!")
                print("\nCollected commits by date:")
                if since and until:
                    current_date = since
                    while current_date <= until:
                        date_str = current_date.strftime('%Y-%m-%d')
                        commit_count = date_counts.get(date_str, 0)
                        if commit_count > 0:
                            print(f"  {date_str}: {commit_count} commits")
                        else:
                            print(f"  {date_str}: No commits found")
                        current_date += timedelta(days=1)
                else:
                    for date in sorted(date_counts.keys()):
                        print(f"  {date}: {date_counts[date]} commits")
                
                print(f"\nTotal commits collected: {processed_commits}")
                
                # Final rate limit check
                self.check_rate_limit(force_check=True)

            except GithubException as e:
                print(f"GitHub API error while collecting commits from {repo_name}: {e}")
                raise
                
        except Exception as e:
            print(f"Unexpected error while processing repository {repo_name}: {e}")
            raise 