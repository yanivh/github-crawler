import os
import json
import time
import copy
import difflib
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
import pandas as pd
from github import Github
from github.Repository import Repository
from github.Commit import Commit
from github.ContentFile import ContentFile
from github.GithubException import GithubException, RateLimitExceededException

from .secrets_manger_toolkit import SecretsManager
from .s3_toolkit import S3


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
            try:
                return content.decoded_content.decode('utf-8')
            except AssertionError:
                # Handle case where encoding is 'none'
                if hasattr(content, 'content'):
                    return content.content
                return None
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

    def get_file_extension(self, filename: str) -> str:
        """
        Extract file extension from filename.
        
        Args:
            filename: Name of the file
            
        Returns:
            File extension in lowercase or empty string if no extension
        """
        if '.' not in filename:
            return ''
        return filename.split('.')[-1].lower()

    def enrich_commit_data(self, commit_data: Dict) -> Dict:
        """
        Enrich commit data with additional properties.
        
        Args:
            commit_data: Raw commit data dictionary
        
        Returns:
            Enriched commit data dictionary with additional properties:
            - files_changed: Number of files modified in the commit
            - lines_changed: Total number of lines changed
            - file_types_changed: List of unique file extensions modified
            Each file in the commit will also have:
            - code_change: The diff between content_before and content_after
            - file_type: The file extension
        """
        # Count number of files changed
        files_changed = len(commit_data.get('files', []))
        
        # Get total lines changed from stats
        lines_changed = commit_data.get('stats', {}).get('total', 0)
        
        # Extract unique file extensions and enrich file data
        file_types = set()
        enriched_files = []
        
        for file in commit_data.get('files', []):
            # Get file extension
            ext = self.get_file_extension(file.get('filename', ''))
            if ext:
                file_types.add(ext)
            
            # Create enriched file data with deep copy
            enriched_file = copy.deepcopy(file)
            enriched_file['file_type'] = ext
            
            # Add code change if we have both before and after content
            content_before = file.get('content_before')
            content_after = file.get('content_after')
            
            if content_before is not None or content_after is not None:
                enriched_file['code_change'] = {
                    'before': content_before,
                    'after': content_after
                }
            
            enriched_files.append(enriched_file)
        
        # Create deep copy of commit data before enriching
        enriched_data = copy.deepcopy(commit_data)
        enriched_data.update({
            'files_changed': files_changed,
            'lines_changed': lines_changed,
            'file_types_changed': sorted(list(file_types)),  # Convert set to sorted list for consistent output
            'files': enriched_files
        })
        
        return enriched_data

    def extract_file_type(self, file_path: str) -> str:
        """Extract file type from file path"""
        if '.' not in file_path:
            return 'no_extension'
        return file_path.split('.')[-1].lower()

    def generate_unified_diff(self, content_before: Optional[str], content_after: Optional[str]) -> Optional[str]:
        """Generate unified diff between before and after content"""
        if content_before is None and content_after is None:
            return None
            
        before_lines = content_before.splitlines() if content_before else []
        after_lines = content_after.splitlines() if content_after else []
        
        diff = difflib.unified_diff(
            before_lines,
            after_lines,
            lineterm='',
            n=3  # Context lines
        )
        return '\n'.join(list(diff))

    def get_directory_category(self, file_path: str) -> str:
        """
        Categorize the file based on its directory path.
        
        Args:
            file_path: Path of the file
            
        Returns:
            Category of the directory (e.g., 'source', 'test', 'config', etc.)
        """
        # Convert to lowercase and split path
        path_parts = file_path.lower().split('/')
        
        # Directory category patterns
        patterns = {
            'source': {'src', 'source'},
            'test': {'test', 'tests', 'spec', 'specs'},
            'config': {'config', 'conf', 'settings'},
            'docs': {'docs', 'documentation', 'wiki'},
            'scripts': {'scripts', 'tools'},
            'examples': {'examples', 'sample', 'samples'},
            'library': {'lib', 'libs', 'library'},
            'api': {'api'},
            'utils': {'utils', 'helpers', 'util'},
            'data': {'data'},
            'assets': {'assets', 'static'},
            'database': {'migrations', 'db'}
        }
        
        # Check each path component against patterns
        for part in path_parts:
            for category, keywords in patterns.items():
                if part in keywords:
                    return category
                
            # Check for compound words (e.g., "testutils", "apiserver")
            for category, keywords in patterns.items():
                if any(keyword in part for keyword in keywords):
                    return category
        
        return 'other'

    def calculate_change_complexity(self, unified_diff: Optional[str]) -> float:
        """
        Calculate complexity score for a change based on its unified diff.
        
        Args:
            unified_diff: Unified diff string
            
        Returns:
            Complexity score between 0 and 1
        """
        if not unified_diff:
            return 0.0
            
        # Split diff into chunks
        chunks = unified_diff.split('\n@@')
        num_chunks = len(chunks) - 1  # -1 because split creates empty first chunk
        
        if num_chunks == 0:
            return 0.0
            
        # Calculate metrics
        chunk_complexity = min(1.0, num_chunks / 10)  # Normalize number of chunks (max 10)
        
        # Count different types of changes
        additions = len(re.findall(r'\n\+', unified_diff))
        deletions = len(re.findall(r'\n-', unified_diff))
        total_changes = additions + deletions
        
        if total_changes == 0:
            return 0.0
            
        # Calculate change type diversity (0 if all additions or all deletions, 1 if equal mix)
        change_diversity = 2 * min(additions, deletions) / total_changes
        
        # Calculate spread of changes
        lines = unified_diff.split('\n')
        change_lines = [i for i, line in enumerate(lines) if line.startswith('+') or line.startswith('-')]
        if len(change_lines) > 1:
            spread = (change_lines[-1] - change_lines[0]) / len(lines)
            spread_complexity = min(1.0, spread)
        else:
            spread_complexity = 0.0
        
        # Combine metrics with weights
        complexity_score = (
            0.4 * chunk_complexity +    # Weight for number of chunks
            0.3 * change_diversity +    # Weight for mix of changes
            0.3 * spread_complexity     # Weight for spread of changes
        )
        
        return round(complexity_score, 3)

    def process_file_entry(self, commit_data: Dict, file_data: Dict, files_changed: int) -> Dict:
        """Process a single file entry into a flat dictionary"""
        content_before = file_data.get('content_before')
        content_after = file_data.get('content_after')
        unified_diff = self.generate_unified_diff(content_before, content_after)
        
        return {
            # Commit metadata
            'commit_sha': commit_data['sha'],  # Adding explicit SHA
            'author_name': commit_data['author']['name'],
            'message': commit_data['message'],
            
            # File metadata
            'file_path': file_data['filename'],
            'status': file_data['status'],
            'content_before': content_before,
            'content_after': content_after,
            'changes': file_data['changes'],
            'additions': file_data['additions'],
            'deletions': file_data['deletions'],
            'file_type': self.extract_file_type(file_data['filename']),
            'unified_diff': unified_diff,
            
            # New ML features
            'directory_category': self.get_directory_category(file_data['filename']),
            'change_complexity': self.calculate_change_complexity(unified_diff),
            
            # Commit-level statistics
            'commit_overall_files_changed': files_changed,
            'commit_overall_lines_changed': commit_data['stats']['total']
        }

    def process_raw_commits(self, owner: str, repo: str, start_date: datetime, end_date: datetime) -> None:
        """
        Process raw commits into a flat dataset optimized for ML training.
        Each row represents a single file change within a commit.
        
        Args:
            owner: Repository owner
            repo: Repository name
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
        """
        current_date = start_date
        all_file_entries = []
        
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            prefix = f"datalake/raw/github/owner={owner}/repo={repo}/commits/date={date_str}"
            
            # List all commit files for the current date
            files = self.s3_client.get_s3_list_of_files(prefix=prefix)
            
            print(f"Processing commits for {date_str}...")
            for file_path in files:
                try:
                    # Read raw commit data
                    commit_data = self.s3_client.read_json_s3_object(file_path)
                    files_changed = len(commit_data.get('files', []))
                    
                    # Process each file in the commit
                    for file_data in commit_data.get('files', []):
                        file_entry = self.process_file_entry(commit_data, file_data, files_changed)
                        all_file_entries.append(file_entry)
                    
                    print(f"Successfully processed commit: {commit_data['sha']}")
                    
                except Exception as e:
                    print(f"Error processing file {file_path}: {e}")
                    continue
            
            # Convert to DataFrame and save as parquet if we have data
            if all_file_entries:
                df = pd.DataFrame(all_file_entries)
                
                # Save to processed layer as parquet
                processed_path = f"datalake/processed/github/owner={owner}/repo={repo}/date={date_str}/{owner}__{repo}_{date_str}.parquet"
                
                if not self.s3_client.save_parquet_to_s3(processed_path, df):
                    print(f"Failed to save processed data for date: {date_str}")
            
            # Clear list for next date
            all_file_entries = []
            current_date += timedelta(days=1) 