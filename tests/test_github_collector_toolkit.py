import unittest
from unittest.mock import Mock, patch
from datetime import datetime
import pandas as pd
from src.utils.github_collector_toolkit import GitHubCollector

class TestGitHubCollector(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.mock_secrets = {
            'SecretString': 'mock_token'
        }
        self.mock_s3_client = Mock()
        self.mock_github = Mock()
        
        # Patch the dependencies
        self.secrets_patcher = patch('src.utils.github_collector_toolkit.SecretsManager')
        self.s3_patcher = patch('src.utils.github_collector_toolkit.S3')
        self.github_patcher = patch('src.utils.github_collector_toolkit.Github')
        
        # Start the patches
        self.mock_secrets_manager = self.secrets_patcher.start()
        self.mock_s3 = self.s3_patcher.start()
        self.mock_github_class = self.github_patcher.start()
        
        # Configure the mocks
        self.mock_secrets_manager.return_value.get_secret.return_value = self.mock_secrets
        self.mock_s3.return_value = self.mock_s3_client
        self.mock_github_class.return_value = self.mock_github
        
        # Create the collector instance
        self.collector = GitHubCollector('mock_token_key', 'mock_bucket')

    def tearDown(self):
        """Clean up after each test method."""
        self.secrets_patcher.stop()
        self.s3_patcher.stop()
        self.github_patcher.stop()

    def test_get_file_extension(self):
        """Test file extension extraction."""
        test_cases = [
            ('test.py', 'py'),
            ('README.md', 'md'),
            ('no_extension', ''),
            ('multiple.dots.txt', 'txt'),
            ('UPPERCASE.PY', 'py')
        ]
        
        for filename, expected in test_cases:
            with self.subTest(filename=filename):
                result = self.collector.get_file_extension(filename)
                self.assertEqual(result, expected)

    def test_get_directory_category(self):
        """Test directory categorization."""
        test_cases = [
            ('src/main.py', 'source'),
            ('tests/test_file.py', 'test'),
            ('docs/README.md', 'docs'),
            ('config/settings.json', 'config'),
            ('unknown/path/file.txt', 'other')
        ]
        
        for path, expected in test_cases:
            with self.subTest(path=path):
                result = self.collector.get_directory_category(path)
                self.assertEqual(result, expected)

    def test_calculate_change_complexity(self):
        """Test change complexity calculation."""
        # Test empty diff
        self.assertEqual(self.collector.calculate_change_complexity(None), 0.0)
        
        # Test simple addition
        simple_diff = """@@ -1,2 +1,3 @@
 line1
+line2
 line3"""
        self.assertLess(self.collector.calculate_change_complexity(simple_diff), 0.5)
        
        # Test complex changes
        complex_diff = """@@ -1,5 +1,7 @@
 line1
-line2
+line2_modified
 line3
+line4
+line5
-line6
+line6_modified"""
        self.assertGreater(self.collector.calculate_change_complexity(complex_diff), 0.5)

    @patch('src.utils.github_collector_toolkit.GitHubCollector.check_rate_limit')
    def test_get_repository(self, mock_check_rate_limit):
        """Test repository retrieval."""
        # Configure mock
        mock_check_rate_limit.return_value = True
        mock_repo = Mock()
        self.mock_github.get_repo.return_value = mock_repo
        
        # Test successful retrieval
        result = self.collector.get_repository('test/repo')
        self.assertEqual(result, mock_repo)
        self.mock_github.get_repo.assert_called_once_with('test/repo')
        
        # Test rate limit handling
        mock_check_rate_limit.return_value = False
        result = self.collector.get_repository('test/repo')
        self.assertIsNone(result)

    def test_process_file_entry(self):
        """Test file entry processing."""
        commit_data = {
            'sha': 'abc123',
            'author': {'name': 'Test Author'},
            'message': 'Test commit',
            'stats': {'total': 10}
        }
        
        file_data = {
            'filename': 'test.py',
            'status': 'modified',
            'changes': 5,
            'additions': 3,
            'deletions': 2
        }
        
        result = self.collector.process_file_entry(commit_data, file_data, 1)
        
        self.assertEqual(result['commit_sha'], 'abc123')
        self.assertEqual(result['author_name'], 'Test Author')
        self.assertEqual(result['file_path'], 'test.py')
        self.assertEqual(result['status'], 'modified')
        self.assertEqual(result['file_type'], 'py')
        self.assertEqual(result['commit_overall_files_changed'], 1)
        self.assertEqual(result['commit_overall_lines_changed'], 10)

if __name__ == '__main__':
    unittest.main() 