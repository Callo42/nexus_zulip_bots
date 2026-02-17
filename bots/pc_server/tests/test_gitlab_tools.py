#!/usr/bin/env python3
"""Unit tests for ITP GitLab tools.

Usage:
    PYTHONPATH=/path/to/bots python -m pytest pc_server/tests/test_gitlab_tools.py
"""

import unittest
from unittest.mock import Mock, patch

import requests.exceptions

try:
    from pc_server.tool_manager import ToolManager

    HAS_DEPENDENCIES = True
except ImportError as e:
    HAS_DEPENDENCIES = False
    print(f"Import error: {e}, skipping tests")


@unittest.skipIf(not HAS_DEPENDENCIES, "Dependencies not available")
class TestGitLabTools(unittest.TestCase):
    """Test cases for GitLab tools."""

    def setUp(self):
        """Set up test fixtures.

        Args:
            self: Test instance
        """
        self.mock_pc_manager = Mock()
        self.mock_pc_manager.root = "/tmp/test_pc"  # nosec B108
        self.mock_history_manager = Mock()
        self.tool_manager = ToolManager(self.mock_pc_manager, self.mock_history_manager)

    def test_tool_registration(self):
        """Test that GitLab tools are registered.

        Args:
            self: Test instance
        """
        # Check all GitLab tools are registered
        gitlab_tools = [
            "itpGitLab_list_directory",
            "itpGitLab_read_file",
            "gitlab_list_repos",
            "gitlab_get_repo_info",
            "gitlab_search_repos",
        ]

        for tool_name in gitlab_tools:
            self.assertIn(
                tool_name,
                self.tool_manager.tools,
                f"Tool {tool_name} should be registered",
            )
            tool = self.tool_manager.tools[tool_name]
            self.assertEqual(tool.name, tool_name)
            self.assertFalse(tool.dangerous, f"Tool {tool_name} should not be dangerous")
            self.assertTrue(
                tool.allowed_by_default,
                f"Tool {tool_name} should be allowed by default",
            )

    @patch("tool_manager.requests")
    def test_itpGitLab_list_directory_success(self, mock_requests):
        """Test successful directory listing.

        Args:
            self: Test instance
            mock_requests: Mocked requests module
        """
        # Ensure exceptions module is properly mocked with real exception classes
        mock_requests.exceptions = requests.exceptions
        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = [
            {
                "name": "README.md",
                "type": "blob",
                "path": "README.md",
                "id": "123",
                "mode": "100644",
                "commit_id": "abc",
            },
            {
                "name": "docs",
                "type": "tree",
                "path": "docs",
                "id": "456",
                "mode": "040000",
                "commit_id": "def",
            },
        ]
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        # Execute tool
        result = self.tool_manager._execute_itpGitLab_list_directory(
            {"path": "", "recursive": False, "private_token": ""}
        )

        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["path"], "")
        self.assertEqual(result["repository"], "codes/groupmeeting")

        entries = result["entries"]
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["name"], "README.md")
        self.assertEqual(entries[0]["type"], "blob")
        self.assertEqual(entries[1]["name"], "docs")
        self.assertEqual(entries[1]["type"], "tree")

        # Verify API call
        mock_requests.get.assert_called_once()
        call_args = mock_requests.get.call_args
        self.assertIn(
            "https://code.itp.ac.cn/api/v4/projects/codes%2Fgroupmeeting/repository/tree",
            call_args[0][0],
        )
        self.assertNotIn("PRIVATE-TOKEN", call_args[1].get("headers", {}))

    @patch("tool_manager.requests")
    def test_itpGitLab_list_directory_with_token(self, mock_requests):
        """Test directory listing with private token.

        Args:
            self: Test instance
            mock_requests: Mocked requests module
        """
        # Ensure exceptions module is properly mocked with real exception classes
        mock_requests.exceptions = requests.exceptions
        mock_response = Mock()
        mock_response.json.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        result = self.tool_manager._execute_itpGitLab_list_directory(
            {"path": "docs", "recursive": True, "private_token": "fake-token"}
        )

        self.assertTrue(result["success"])

        # Verify token was included in headers
        call_args = mock_requests.get.call_args
        headers = call_args[1].get("headers", {})
        self.assertEqual(headers.get("PRIVATE-TOKEN"), "fake-token")

    @patch("tool_manager.requests")
    def test_itpGitLab_list_directory_api_error(self, mock_requests):
        """Test directory listing with API error.

        Args:
            self: Test instance
            mock_requests: Mocked requests module
        """
        # Ensure exceptions module is properly mocked with real exception classes
        mock_requests.exceptions = requests.exceptions
        mock_requests.get.side_effect = requests.exceptions.ConnectionError("Connection failed")

        result = self.tool_manager._execute_itpGitLab_list_directory(
            {"path": "", "recursive": False, "private_token": ""}
        )

        self.assertFalse(result["success"])
        self.assertIn("error", result)
        self.assertEqual(result.get("repository"), "codes/groupmeeting")

    @patch("tool_manager.requests")
    def test_itpGitLab_read_file_success(self, mock_requests):
        """Test successful file reading.

        Args:
            self: Test instance
            mock_requests: Mocked requests module
        """
        # Ensure exceptions module is properly mocked with real exception classes
        mock_requests.exceptions = requests.exceptions
        mock_response = Mock()
        mock_response.text = "# Group Meeting Repository\n\nThis is a test README."
        mock_response.encoding = "utf-8"
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        result = self.tool_manager._execute_itpGitLab_read_file(
            {"file_path": "README.md", "ref": "main", "private_token": ""}
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["file_path"], "README.md")
        self.assertEqual(result["ref"], "main")
        self.assertEqual(result["repository"], "codes/groupmeeting")
        self.assertIn("# Group Meeting Repository", result["content"])
        self.assertEqual(
            result["size"], len("# Group Meeting Repository\n\nThis is a test README.")
        )

    @patch("tool_manager.requests")
    def test_itpGitLab_read_file_not_found(self, mock_requests):
        """Test file reading with 404 error.

        Args:
            self: Test instance
            mock_requests: Mocked requests module
        """
        from requests.exceptions import HTTPError

        # Ensure exceptions module is properly mocked with real exception classes
        mock_requests.exceptions = requests.exceptions

        # Create a mock response with status_code for the exception
        mock_http_response = Mock()
        mock_http_response.status_code = 404

        # Create HTTPError with response attribute
        http_error = HTTPError("Not Found")
        http_error.response = mock_http_response

        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = http_error
        mock_requests.get.return_value = mock_response

        result = self.tool_manager._execute_itpGitLab_read_file(
            {"file_path": "nonexistent.md", "ref": "main", "private_token": ""}
        )

        self.assertFalse(result["success"])
        self.assertIn("File not found", result["error"])

    @patch("tool_manager.requests")
    def test_itpGitLab_read_file_large_content(self, mock_requests):
        """Test file reading with large content.

        Args:
            self: Test instance
            mock_requests: Mocked requests module
        """
        # Ensure exceptions module is properly mocked with real exception classes
        mock_requests.exceptions = requests.exceptions
        large_content = "x" * 150000  # 150KB

        mock_response = Mock()
        mock_response.text = large_content
        mock_response.encoding = "utf-8"
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        result = self.tool_manager._execute_itpGitLab_read_file(
            {"file_path": "large.txt", "ref": "main", "private_token": ""}
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["size"], 150000)
        # Content is no longer truncated in the new implementation
        self.assertEqual(result["content"], large_content)

    def test_itpGitLab_read_file_any_file(self):
        """Test that itpGitLab_read_file can read any file, not just README.md.

        Args:
            self: Test instance
        """
        # This test verifies the hardcoded restriction has been removed
        with patch("tool_manager.requests") as mock_requests:
            mock_requests.exceptions = requests.exceptions
            mock_response = Mock()
            mock_response.text = "Any file content"
            mock_response.encoding = "utf-8"
            mock_response.raise_for_status.return_value = None
            mock_requests.get.return_value = mock_response

            # Should work with any file path
            result = self.tool_manager._execute_itpGitLab_read_file(
                {"file_path": "docs/guide.md", "ref": "develop", "private_token": ""}
            )

            self.assertTrue(result["success"])
            self.assertEqual(result["file_path"], "docs/guide.md")
            self.assertEqual(result["ref"], "develop")

    @patch("tool_manager.requests")
    def test_gitlab_list_repos_success(self, mock_requests):
        """Test successful repository listing.

        Args:
            self: Test instance
            mock_requests: Mocked requests module
        """
        mock_requests.exceptions = requests.exceptions

        # Mock response for first page
        mock_response = Mock()
        mock_response.json.return_value = [
            {
                "id": 1,
                "name": "groupmeeting",
                "path_with_namespace": "codes/groupmeeting",
                "description": "Group meeting repository",
                "web_url": "https://code.itp.ac.cn/codes/groupmeeting",
                "default_branch": "main",
                "last_activity_at": "2024-01-01T00:00:00Z",
                "star_count": 10,
            },
            {
                "id": 2,
                "name": "project2",
                "path_with_namespace": "codes/project2",
                "description": "Another project",
                "web_url": "https://code.itp.ac.cn/codes/project2",
                "default_branch": "master",
                "last_activity_at": "2024-01-02T00:00:00Z",
                "star_count": 5,
            },
        ]
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {"X-Total-Pages": "1"}
        mock_requests.get.return_value = mock_response

        result = self.tool_manager._execute_gitlab_list_repos(
            {"page": 1, "per_page": 20, "use_cache": False}
        )

        self.assertTrue(result["success"])
        self.assertEqual(len(result["repositories"]), 2)
        self.assertEqual(result["pagination"]["total"], 2)
        self.assertEqual(result["repositories"][0]["name"], "groupmeeting")
        self.assertEqual(result["repositories"][1]["name"], "project2")
        self.assertIn("star_count", result["repositories"][0])

    def test_gitlab_list_repos_with_cache(self):
        """Test repository listing with cache.

        Args:
            self: Test instance
        """
        # First call should populate cache
        with patch("tool_manager.requests") as mock_requests:
            mock_requests.exceptions = requests.exceptions
            mock_response = Mock()
            mock_response.json.return_value = [
                {
                    "id": 1,
                    "name": "repo1",
                    "path_with_namespace": "test/repo1",
                    "description": "",
                    "web_url": "http://test/repo1",
                    "default_branch": "main",
                    "star_count": 0,
                }
            ]
            mock_response.raise_for_status.return_value = None
            mock_response.headers = {"X-Total-Pages": "1"}
            mock_requests.get.return_value = mock_response

            result1 = self.tool_manager._execute_gitlab_list_repos({"use_cache": True})

            self.assertTrue(result1["success"])
            self.assertFalse(result1.get("cache_used", False))

        # Second call should use cache
        with patch("tool_manager.requests") as mock_requests:
            result2 = self.tool_manager._execute_gitlab_list_repos({"use_cache": True})

            self.assertTrue(result2["success"])
            self.assertTrue(result2.get("cache_used", True))
            # Requests should not be called
            mock_requests.get.assert_not_called()

    @patch("tool_manager.requests")
    def test_gitlab_get_repo_info_success(self, mock_requests):
        """Test successful repository info retrieval.

        Args:
            self: Test instance
            mock_requests: Mocked requests module
        """
        mock_requests.exceptions = requests.exceptions

        # Mock project info response
        project_response = Mock()
        project_response.json.return_value = {
            "id": 123,
            "name": "groupmeeting",
            "path_with_namespace": "codes/groupmeeting",
            "description": "Group meeting repository",
            "web_url": "https://code.itp.ac.cn/codes/groupmeeting",
            "default_branch": "main",
            "visibility": "internal",
            "created_at": "2023-01-01T00:00:00Z",
            "last_activity_at": "2024-01-01T00:00:00Z",
            "star_count": 10,
            "forks_count": 2,
            "open_issues_count": 5,
        }
        project_response.raise_for_status.return_value = None

        # Mock branches response
        branches_response = Mock()
        branches_response.json.return_value = [
            {
                "name": "main",
                "protected": True,
                "default": True,
                "commit": {"short_id": "abc123"},
            },
            {
                "name": "develop",
                "protected": False,
                "default": False,
                "commit": {"short_id": "def456"},
            },
        ]
        branches_response.status_code = 200
        branches_response.raise_for_status.return_value = None

        # Configure side_effect to return different responses
        mock_requests.get.side_effect = [project_response, branches_response]

        result = self.tool_manager._execute_gitlab_get_repo_info(
            {"project_id": "codes%2Fgroupmeeting", "include_branches": True}
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["repository"]["name"], "groupmeeting")
        self.assertEqual(result["repository"]["star_count"], 10)
        self.assertEqual(len(result["branches"]), 2)
        self.assertEqual(result["branch_count"], 2)

    @patch("tool_manager.requests")
    def test_gitlab_get_repo_info_not_found(self, mock_requests):
        """Test repository info with 404 error.

        Args:
            self: Test instance
            mock_requests: Mocked requests module
        """
        mock_requests.exceptions = requests.exceptions

        from requests.exceptions import HTTPError

        mock_http_response = Mock()
        mock_http_response.status_code = 404
        http_error = HTTPError("Not Found")
        http_error.response = mock_http_response

        mock_response = Mock()
        mock_response.raise_for_status.side_effect = http_error
        mock_requests.get.return_value = mock_response

        result = self.tool_manager._execute_gitlab_get_repo_info(
            {"project_id": "nonexistent/project", "include_branches": True}
        )

        self.assertFalse(result["success"])
        self.assertIn("Repository not found", result["error"])

    @patch("tool_manager.requests")
    def test_gitlab_search_repos_success(self, mock_requests):
        """Test successful repository search with keyword matching.

        Args:
            self: Test instance
            mock_requests: Mocked requests module
        """
        mock_requests.exceptions = requests.exceptions

        # Mock repositories list
        mock_response = Mock()
        mock_response.json.return_value = [
            {
                "id": 1,
                "name": "machine-learning-toolkit",
                "path_with_namespace": "ml/toolkit",
                "description": "Machine learning tools and utilities",
                "web_url": "http://test/1",
                "default_branch": "main",
                "star_count": 50,
            },
            {
                "id": 2,
                "name": "data-analysis",
                "path_with_namespace": "data/analysis",
                "description": "Data analysis scripts",
                "web_url": "http://test/2",
                "default_branch": "main",
                "star_count": 30,
            },
            {
                "id": 3,
                "name": "web-server",
                "path_with_namespace": "infra/web",
                "description": "Web server implementation",
                "web_url": "http://test/3",
                "default_branch": "main",
                "star_count": 10,
            },
        ]
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {"X-Total-Pages": "1"}
        mock_requests.get.return_value = mock_response

        result = self.tool_manager._execute_gitlab_search_repos(
            {"query": "machine learning toolkit", "top_k": 5}
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["query"], "machine learning toolkit")
        self.assertIn("machine", result["keywords"])
        self.assertIn("learning", result["keywords"])
        self.assertEqual(result["method"], "keyword_matching_with_doc")

        # Should find matching repositories
        self.assertGreaterEqual(len(result["repositories"]), 1)

        # machine-learning-toolkit should have highest score
        first_repo = result["repositories"][0]
        self.assertIn("score", first_repo)
        self.assertIn("matched_keywords", first_repo)

    def test_gitlab_search_repos_empty_query(self):
        """Test search with empty query.

        Args:
            self: Test instance
        """
        result = self.tool_manager._execute_gitlab_search_repos({"query": "", "top_k": 10})

        self.assertFalse(result["success"])
        self.assertIn("query is required", result["error"])

    @patch("tool_manager.requests")
    def test_gitlab_search_repos_no_matches(self, mock_requests):
        """Test search with no matching results.

        Args:
            self: Test instance
            mock_requests: Mocked requests module
        """
        mock_requests.exceptions = requests.exceptions

        mock_response = Mock()
        mock_response.json.return_value = [
            {
                "id": 1,
                "name": "repo1",
                "path_with_namespace": "test/repo1",
                "description": "Test repo",
                "web_url": "http://test/1",
                "default_branch": "main",
                "star_count": 0,
            }
        ]
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {"X-Total-Pages": "1"}
        mock_requests.get.return_value = mock_response

        result = self.tool_manager._execute_gitlab_search_repos(
            {"query": "xyznonexistent", "top_k": 10}
        )

        self.assertTrue(result["success"])
        self.assertEqual(len(result["repositories"]), 0)
        self.assertEqual(result["total_matched"], 0)

    def test_doc_priority_weights(self):
        """Test that documentation priority weights are correctly defined.

        Args:
            self: Test instance
        """
        self.assertEqual(self.tool_manager.DOC_PRIORITY_WEIGHTS["README"], 5)
        self.assertEqual(self.tool_manager.DOC_PRIORITY_WEIGHTS["AGENTS"], 4)
        self.assertEqual(self.tool_manager.DOC_PRIORITY_WEIGHTS["CLAUDE"], 4)
        self.assertEqual(self.tool_manager.DOC_PRIORITY_WEIGHTS["CHANGELOG"], 3)
        self.assertEqual(self.tool_manager.DOC_PRIORITY_WEIGHTS["ENTRY"], 2)

    def test_doc_file_patterns(self):
        """Test that documentation file patterns are correctly defined.

        Args:
            self: Test instance
        """
        import re

        # Test README patterns
        for pattern in self.tool_manager.DOC_FILE_PATTERNS["README"]:
            self.assertTrue(re.search(pattern, "README.md", re.IGNORECASE))
            self.assertTrue(re.search(pattern, "README.rst", re.IGNORECASE))

        # Test AGENTS patterns
        for pattern in self.tool_manager.DOC_FILE_PATTERNS["AGENTS"]:
            self.assertTrue(re.search(pattern, "AGENTS.md", re.IGNORECASE))

        # Test CLAUDE patterns
        for pattern in self.tool_manager.DOC_FILE_PATTERNS["CLAUDE"]:
            self.assertTrue(re.search(pattern, "CLAUDE.md", re.IGNORECASE))

        # Test CHANGELOG patterns (first pattern should match CHANGELOG files)
        changelog_pattern = self.tool_manager.DOC_FILE_PATTERNS["CHANGELOG"][0]
        self.assertTrue(re.search(changelog_pattern, "CHANGELOG.md", re.IGNORECASE))
        self.assertTrue(re.search(changelog_pattern, "CHANGES.rst", re.IGNORECASE))
        # HISTORY patterns are separate (second pattern)
        history_pattern = self.tool_manager.DOC_FILE_PATTERNS["CHANGELOG"][1]
        self.assertTrue(re.search(history_pattern, "HISTORY.txt", re.IGNORECASE))
        self.assertTrue(re.search(history_pattern, "HISTORY.md", re.IGNORECASE))

        # Test ENTRY patterns (each pattern matches specific files)
        entry_patterns = self.tool_manager.DOC_FILE_PATTERNS["ENTRY"]
        self.assertTrue(re.search(entry_patterns[0], "main.py", re.IGNORECASE))
        self.assertTrue(re.search(entry_patterns[2], "Cargo.toml", re.IGNORECASE))


class TestToolManagerIntegration(unittest.TestCase):
    """Integration tests for ToolManager with GitLab tools."""

    @unittest.skip("Requires network access to GitLab")
    def test_real_gitlab_access(self):
        """Test actual GitLab API access (requires network)."""
        # This test is skipped by default to avoid network dependencies
        # It can be run manually to verify real API connectivity
        import requests

        # Test public repository access
        response = requests.get(
            "https://code.itp.ac.cn/api/v4/projects/codes%2Fgroupmeeting/repository/tree",
            params={"per_page": 1},
            timeout=10,
        )
        self.assertEqual(response.status_code, 200)

        # Test file access
        response = requests.get(
            "https://code.itp.ac.cn/api/v4/projects/codes%2Fgroupmeeting/"
            "repository/files/README.md/raw",
            params={"ref": "main"},
            timeout=10,
        )
        # 404 is okay if file doesn't exist, but should not be 401/403
        if response.status_code != 404:
            response.raise_for_status()


if __name__ == "__main__":
    unittest.main()
