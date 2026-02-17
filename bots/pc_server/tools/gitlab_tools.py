"""GitLab tools - compatibility wrapper for new gitlab package.

This module re-exports the new modular gitlab package for backward compatibility.
New code should import directly from tools.gitlab.
"""

# Re-export everything from the new gitlab package
from .gitlab import (  # Models; Components; Registration
    CacheStats,
    DocFile,
    DocIndex,
    DocSnippet,
    DocType,
    GitLabCacheManager,
    GitLabClient,
    GitLabDocIndexer,
    GitLabError,
    GitLabSearchEngine,
    GitLabSecurityError,
    Repository,
    SearchResult,
    register_gitlab_tools,
)

__all__ = [
    "Repository",
    "DocType",
    "DocFile",
    "DocIndex",
    "DocSnippet",
    "SearchResult",
    "CacheStats",
    "GitLabClient",
    "GitLabError",
    "GitLabSecurityError",
    "GitLabCacheManager",
    "GitLabDocIndexer",
    "GitLabSearchEngine",
    "register_gitlab_tools",
]
