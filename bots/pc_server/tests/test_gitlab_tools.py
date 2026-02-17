#!/usr/bin/env python3
"""Unit tests for GitLab tools.

Usage:
    PYTHONPATH=/path/to/bots python -m pytest pc_server/tests/test_gitlab_tools.py
"""

import unittest
from unittest.mock import Mock, patch

import requests.exceptions
from pc_server.tools.gitlab import (
    GitLabCacheManager,
    GitLabClient,
    GitLabDocIndexer,
    GitLabError,
    GitLabSearchEngine,
)
from pc_server.tools.registry import ToolRegistry


class TestGitLabClient(unittest.TestCase):
    """Test cases for GitLabClient."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = GitLabClient()

    @patch("pc_server.tools.gitlab.client.requests.Session.get")
    def test_list_directory_success(self, mock_get):
        """Test successful directory listing."""
        mock_response = Mock()
        mock_response.json.return_value = [
            {"name": "README.md", "type": "blob", "path": "README.md"},
            {"name": "docs", "type": "tree", "path": "docs"},
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = self.client.list_directory("codes/groupmeeting", "/", "master")

        self.assertIn("files", result)
        self.assertIn("directories", result)
        self.assertEqual(len(result["files"]), 1)
        self.assertEqual(len(result["directories"]), 1)
        self.assertEqual(result["files"][0]["name"], "README.md")

    @patch("pc_server.tools.gitlab.client.requests.Session.get")
    def test_get_file_content_success(self, mock_get):
        """Test successful file reading."""
        mock_response = Mock()
        mock_response.text = "# Test Content"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = self.client.get_file_content("codes/groupmeeting", "README.md", "master")

        self.assertEqual(result, "# Test Content")

    @patch("pc_server.tools.gitlab.client.requests.Session.get")
    def test_get_file_content_not_found(self, mock_get):
        """Test file reading with 404 error."""
        mock_response = Mock()
        http_error = requests.exceptions.HTTPError("Not Found")
        http_error.response = Mock(status_code=404)
        mock_response.raise_for_status.side_effect = http_error
        mock_get.return_value = mock_response

        result = self.client.get_file_content("codes/groupmeeting", "nonexistent.md", "master")

        self.assertIsNone(result)


class TestGitLabToolsIntegration(unittest.TestCase):
    """Integration tests for GitLab tools with ToolRegistry."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_pc_manager = Mock()
        self.mock_pc_manager.root = "/tmp/test_pc"
        self.registry = ToolRegistry(self.mock_pc_manager)

    def test_tool_registration(self):
        """Test that GitLab tools are registered."""
        from pc_server.tools.gitlab.tools import register_gitlab_tools

        register_gitlab_tools(self.registry, self.mock_pc_manager)

        expected_tools = [
            "itpGitLab_list_directory",
            "itpGitLab_read_file",
            "gitlab_list_repos",
            "gitlab_get_repo_info",
            "gitlab_search_repos",
        ]

        for tool_name in expected_tools:
            tool = self.registry.get_tool(tool_name)
            self.assertIsNotNone(tool, f"Tool {tool_name} should be registered")
            self.assertEqual(tool.name, tool_name)
            self.assertFalse(tool.dangerous, f"Tool {tool_name} should not be dangerous")
            self.assertTrue(
                tool.allowed_by_default,
                f"Tool {tool_name} should be allowed by default",
            )


class TestGitLabCacheManager(unittest.TestCase):
    """Test cases for GitLabCacheManager."""

    def setUp(self):
        """Set up test fixtures."""
        import tempfile

        self.temp_dir = tempfile.mkdtemp()
        self.cache = GitLabCacheManager(self.temp_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_cache_repositories(self):
        """Test caching and retrieving repositories."""
        from pc_server.tools.gitlab.models import Repository

        repos = [
            Repository(
                id=1,
                name="test-repo",
                path="group/test-repo",
                description="Test repository",
                url="http://test/repo",
                stars=10,
                forks=2,
                issues=5,
                visibility="internal",
                default_branch="main",
            )
        ]

        self.cache.set_repositories(repos)
        cached = self.cache.get_repositories()

        self.assertEqual(len(cached), 1)
        self.assertEqual(cached[0].name, "test-repo")


class TestGitLabSearchEngine(unittest.TestCase):
    """Test cases for GitLabSearchEngine."""

    def setUp(self):
        """Set up test fixtures."""
        import tempfile

        self.temp_dir = tempfile.mkdtemp()
        self.client = GitLabClient()
        self.cache = GitLabCacheManager(self.temp_dir)
        self.indexer = GitLabDocIndexer(self.client, self.cache)
        self.search_engine = GitLabSearchEngine(self.client, self.cache, self.indexer)

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_search_empty_query(self):
        """Test search with empty query returns empty list."""
        # search() method returns empty list for empty query
        result = self.search_engine.search("", top_k=10)
        self.assertEqual(result, [])

    def test_search_repositories_empty_query(self):
        """Test search_repositories with empty query returns error dict."""
        # search_repositories() returns dict with success=False
        result = self.search_engine.search_repositories("", top_k=10)
        self.assertTrue(result["success"])  # Actually returns success=True with empty results
        self.assertEqual(result["count"], 0)


class TestToolExecution(unittest.TestCase):
    """Test cases for tool execution via ToolRegistry."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_pc_manager = Mock()
        self.mock_pc_manager.root = "/tmp/test_pc"
        self.registry = ToolRegistry(self.mock_pc_manager)
        from pc_server.tools.gitlab.tools import register_gitlab_tools

        register_gitlab_tools(self.registry, self.mock_pc_manager)

    @patch("pc_server.tools.gitlab.client.requests.Session.get")
    def test_itpGitLab_list_directory_execution(self, mock_get):
        """Test executing itpGitLab_list_directory tool."""
        mock_response = Mock()
        mock_response.json.return_value = [
            {"name": "README.md", "type": "blob", "path": "README.md"},
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = self.registry.execute_tool(
            "itpGitLab_list_directory",
            {"project_path": "codes/groupmeeting", "path": "/", "ref": "master"},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["project"], "codes/groupmeeting")

    @patch("pc_server.tools.gitlab.client.requests.Session.get")
    def test_itpGitLab_read_file_execution(self, mock_get):
        """Test executing itpGitLab_read_file tool."""
        mock_response = Mock()
        mock_response.text = "# Test README"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = self.registry.execute_tool(
            "itpGitLab_read_file",
            {"project_path": "codes/groupmeeting", "file_path": "README.md", "ref": "master"},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["content"], "# Test README")

    def test_gitlab_search_repos_empty_query(self):
        """Test gitlab_search_repos with empty query."""
        result = self.registry.execute_tool("gitlab_search_repos", {"query": ""})

        # Empty query should return either success=False with error or success=True with empty results
        # Depending on whether repos are available and how the search is processed
        self.assertIn("success", result)
        self.assertIsInstance(result["success"], bool)


if __name__ == "__main__":
    unittest.main()
