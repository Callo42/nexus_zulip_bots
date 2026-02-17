"""GitLab integration tools with documentation indexing and search.

This package provides comprehensive GitLab integration with:
- Read-only API access with security enforcement
- Repository metadata caching
- Documentation indexing and caching
- Content-aware search with priority weighting

Architecture:
    GitLabClient        - Low-level API client (security, rate limiting)
    GitLabCacheManager  - Cache management (repos, docs persistence)
    GitLabDocIndexer    - Documentation discovery and indexing
    GitLabSearchEngine  - Search orchestration (metadata + content)

Example:
    from tools.gitlab import GitLabClient, GitLabSearchEngine

    client = GitLabClient()
    search = GitLabSearchEngine(client)
    results = search.search_repositories("python web framework", top_k=10)
"""

from .cache import GitLabCacheManager
from .client import GitLabClient, GitLabError, GitLabSecurityError
from .indexer import GitLabDocIndexer
from .models import CacheStats, DocFile, DocIndex, DocSnippet, DocType, Repository, SearchResult
from .search import GitLabSearchEngine
from .tools import register_gitlab_tools

__all__ = [
    # Models
    "Repository",
    "DocType",
    "DocFile",
    "DocIndex",
    "DocSnippet",
    "SearchResult",
    "CacheStats",
    # Components
    "GitLabClient",
    "GitLabError",
    "GitLabSecurityError",
    "GitLabCacheManager",
    "GitLabDocIndexer",
    "GitLabSearchEngine",
    # Registration
    "register_gitlab_tools",
]
