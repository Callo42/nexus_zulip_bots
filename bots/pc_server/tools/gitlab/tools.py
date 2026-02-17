"""Tool registration for GitLab integration.

Registers GitLab tools with the tool registry, integrating:
- itpGitLab_list_directory
- itpGitLab_read_file
- gitlab_list_repos
- gitlab_get_repo_info
- gitlab_search_repos (with full documentation search)
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from .cache import GitLabCacheManager
from .client import GitLabClient
from .indexer import GitLabDocIndexer
from .search import GitLabSearchEngine

if TYPE_CHECKING:
    from ...pc_manager import PCManager
    from ..base import Tool
    from ..registry import ToolRegistry

logger = logging.getLogger(__name__)


def register_gitlab_tools(registry: "ToolRegistry", pc_manager: "PCManager") -> None:
    """Register all GitLab tools with the registry.

    Args:
        registry: ToolRegistry instance
        pc_manager: PCManager instance for cache directory

    Returns:
        None
    """
    # Initialize GitLab components
    client = GitLabClient()
    cache = GitLabCacheManager(str(Path(pc_manager.root) / "cache" / "gitlab"))
    indexer = GitLabDocIndexer(client, cache)
    search_engine = GitLabSearchEngine(client, cache, indexer)

    # Register tools
    registry.register_tool(_create_list_directory_tool(client))
    registry.register_tool(_create_read_file_tool(client))
    registry.register_tool(_create_list_repos_tool(client, cache))
    registry.register_tool(_create_get_repo_info_tool(client))
    registry.register_tool(_create_search_repos_tool(client, cache, indexer, search_engine))

    logger.info("Registered GitLab tools")


def _create_list_directory_tool(client: GitLabClient) -> "Tool":
    """Create itpGitLab_list_directory tool.

    Args:
        client: GitLab API client

    Returns:
        Tool instance for list directory
    """
    from ..base import Tool

    def execute(args: dict) -> dict:
        """Execute list directory tool.

        Args:
            args: Dictionary with project_path, path, and ref

        Returns:
            Dictionary with directory listing result
        """
        project_path = args.get("project_path", "")
        directory_path = args.get("path", "/")
        ref = args.get("ref", "master")

        result = client.list_directory(project_path, directory_path, ref)
        return {
            "success": True,
            "project": project_path,
            "path": directory_path,
            "ref": ref,
            "files": result["files"],
            "directories": result["directories"],
        }

    return Tool(
        name="itpGitLab_list_directory",
        description="List files and directories in an ITP GitLab repository",
        parameters={
            "type": "object",
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": "Project path (e.g., 'group/project')",
                },
                "path": {
                    "type": "string",
                    "description": "Directory path within repository",
                    "default": "/",
                },
                "ref": {
                    "type": "string",
                    "description": "Git reference (branch/tag)",
                    "default": "master",
                },
            },
            "required": ["project_path"],
        },
        execute_func=execute,
        category="gitlab",
        dangerous=False,
        allowed_by_default=True,
    )


def _create_read_file_tool(client: GitLabClient) -> "Tool":
    """Create itpGitLab_read_file tool.

    Args:
        client: GitLab API client

    Returns:
        Tool instance for read file
    """
    from ..base import Tool

    def execute(args: dict) -> dict:
        """Execute read file tool.

        Args:
            args: Dictionary with project_path, file_path, and ref

        Returns:
            Dictionary with file content or error
        """
        project_path = args.get("project_path", "")
        file_path = args.get("file_path", "")
        ref = args.get("ref", "master")

        content = client.get_file_content(project_path, file_path, ref)

        if content is None:
            return {
                "success": False,
                "error": f"File not found: {file_path}",
            }

        return {
            "success": True,
            "content": content,
            "size": len(content),
            "path": file_path,
        }

    return Tool(
        name="itpGitLab_read_file",
        description="Read file content from ITP GitLab repository",
        parameters={
            "type": "object",
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": "Project path (e.g., 'group/project')",
                },
                "file_path": {
                    "type": "string",
                    "description": "File path within repository",
                },
                "ref": {
                    "type": "string",
                    "description": "Git reference (branch/tag)",
                    "default": "master",
                },
            },
            "required": ["project_path", "file_path"],
        },
        execute_func=execute,
        category="gitlab",
        dangerous=False,
        allowed_by_default=True,
    )


def _create_list_repos_tool(client: GitLabClient, cache: GitLabCacheManager) -> "Tool":
    """Create gitlab_list_repos tool.

    Args:
        client: GitLab API client
        cache: Cache manager for repositories

    Returns:
        Tool instance for list repos
    """
    from ..base import Tool

    def execute(args: dict) -> dict:
        """Execute list repos tool.

        Args:
            args: Dictionary with use_cache option

        Returns:
            Dictionary with repository list
        """
        use_cache = args.get("use_cache", True)

        # Try cache first
        if use_cache:
            repos = cache.get_repositories()
            if repos:
                return {
                    "success": True,
                    "repositories": [
                        {
                            "id": r.id,
                            "name": r.name,
                            "path": r.path,
                            "description": r.description,
                            "url": r.url,
                            "stars": r.stars,
                            "forks": r.forks,
                            "visibility": r.visibility,
                        }
                        for r in repos
                    ],
                    "count": len(repos),
                    "cache_used": True,
                }

        # Fetch from API
        repos = client.get_all_repositories()
        cache.set_repositories(repos)

        return {
            "success": True,
            "repositories": [
                {
                    "id": r.id,
                    "name": r.name,
                    "path": r.path,
                    "description": r.description,
                    "url": r.url,
                    "stars": r.stars,
                    "forks": r.forks,
                    "visibility": r.visibility,
                }
                for r in repos
            ],
            "count": len(repos),
            "cache_used": False,
        }

    return Tool(
        name="gitlab_list_repos",
        description="List all repositories in ITP GitLab",
        parameters={
            "type": "object",
            "properties": {
                "use_cache": {
                    "type": "boolean",
                    "description": "Whether to use cached results",
                    "default": True,
                },
            },
        },
        execute_func=execute,
        category="gitlab",
        dangerous=False,
        allowed_by_default=True,
    )


def _create_get_repo_info_tool(client: GitLabClient) -> "Tool":
    """Create gitlab_get_repo_info tool.

    Args:
        client: GitLab API client

    Returns:
        Tool instance for get repo info
    """
    from ..base import Tool

    def execute(args: dict) -> dict:
        """Execute get repo info tool.

        Args:
            args: Dictionary with project_path

        Returns:
            Dictionary with repository information
        """
        project_path = args.get("project_path", "")

        repo = client.get_repository(project_path)

        if repo is None:
            return {
                "success": False,
                "error": f"Repository not found: {project_path}",
            }

        return {
            "success": True,
            "id": repo.id,
            "name": repo.name,
            "path": repo.path,
            "description": repo.description,
            "url": repo.url,
            "stars": repo.stars,
            "forks": repo.forks,
            "issues": repo.issues,
            "visibility": repo.visibility,
            "default_branch": repo.default_branch,
        }

    return Tool(
        name="gitlab_get_repo_info",
        description="Get detailed information about a GitLab repository",
        parameters={
            "type": "object",
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": "Project path (e.g., 'group/project')",
                },
            },
            "required": ["project_path"],
        },
        execute_func=execute,
        category="gitlab",
        dangerous=False,
        allowed_by_default=True,
    )


def _create_search_repos_tool(
    client: GitLabClient,
    cache: GitLabCacheManager,
    indexer: GitLabDocIndexer,
    search_engine: GitLabSearchEngine,
) -> "Tool":
    """Create gitlab_search_repos tool.

    Args:
        client: GitLab API client
        cache: Cache manager
        indexer: Documentation indexer
        search_engine: Search engine for repositories

    Returns:
        Tool instance for search repos
    """
    from ..base import Tool

    def execute(args: dict) -> dict:
        """Execute search repos tool.

        Args:
            args: Dictionary with query, top_k, and warm_cache options

        Returns:
            Dictionary with search results
        """
        query = args.get("query", "").strip()
        top_k = args.get("top_k", 10)
        warm_cache = args.get("warm_cache", True)

        if not query:
            return {"success": False, "error": "Query is required"}

        return search_engine.search_repositories(query, top_k, warm_cache)

    return Tool(
        name="gitlab_search_repos",
        description=(
            "Search repositories using LLM-extracted keywords with "
            "documentation content enhancement"
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (LLM-extracted clean keywords)",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Maximum results to return",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 50,
                },
                "warm_cache": {
                    "type": "boolean",
                    "description": "Whether to warmup doc cache if empty",
                    "default": True,
                },
            },
            "required": ["query"],
        },
        execute_func=execute,
        category="gitlab",
        dangerous=False,
        allowed_by_default=True,
    )
