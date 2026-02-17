"""Data models for GitLab integration.

Provides type-safe dataclasses for repositories, documentation, and search results.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class DocType(Enum):
    """Documentation types with priority weights for search ranking."""

    README = 5  # README files (highest priority)
    AGENTS = 4  # AGENTS.md
    CLAUDE = 4  # CLAUDE.md
    CHANGELOG = 3  # CHANGELOG, CHANGES, HISTORY
    ENTRY = 2  # Entry point files


@dataclass
class Repository:
    """GitLab repository metadata."""

    id: int
    name: str
    path: str  # path_with_namespace
    description: str = ""
    url: str = ""
    stars: int = 0
    forks: int = 0
    issues: int = 0
    visibility: str = "private"
    default_branch: str = "main"
    created_at: Optional[str] = None
    last_activity_at: Optional[str] = None

    @classmethod
    def from_gitlab_api(cls, data: Dict[str, Any]) -> "Repository":
        """Create from GitLab API response.

        Args:
            data: GitLab API response data

        Returns:
            Repository instance
        """
        return cls(
            id=data.get("id", 0),
            name=data.get("name", ""),
            path=data.get("path_with_namespace", ""),
            description=data.get("description") or "",
            url=data.get("web_url", ""),
            stars=data.get("star_count", 0),
            forks=data.get("forks_count", 0),
            issues=data.get("open_issues_count", 0),
            visibility=data.get("visibility", "private"),
            default_branch=data.get("default_branch", "main"),
            created_at=data.get("created_at"),
            last_activity_at=data.get("last_activity_at"),
        )


@dataclass
class DocFile:
    """Documentation file metadata."""

    path: str
    name: str
    doc_type: DocType
    content: str = ""
    size: int = 0
    cached_at: float = field(default_factory=lambda: datetime.now().timestamp())
    ref: str = "main"

    def is_fresh(self, ttl_seconds: int = 3600) -> bool:
        """Check if cache entry is still fresh.

        Args:
            ttl_seconds: TTL in seconds

        Returns:
            True if entry is still fresh
        """
        return (datetime.now().timestamp() - self.cached_at) < ttl_seconds


@dataclass
class DocIndex:
    """Documentation index for a repository."""

    repo_path: str
    doc_type: DocType
    files: Dict[str, DocFile] = field(default_factory=dict)
    best_file: Optional[str] = None  # Highest priority file path

    @property
    def priority(self) -> int:
        """Get documentation priority weight.

        Returns:
            Priority value from DocType enum
        """
        return self.doc_type.value


@dataclass
class DocSnippet:
    """Matched documentation snippet from search."""

    file: str
    snippet: str
    keyword: str
    doc_type: DocType

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation of DocSnippet
        """
        return {
            "file": self.file,
            "snippet": self.snippet,
            "keyword": self.keyword,
            "doc_type": self.doc_type.name,
        }


@dataclass
class SearchResult:
    """Repository search result with scoring."""

    repository: Repository
    score: int
    matched_keywords: List[str] = field(default_factory=list)
    doc_snippets: List[DocSnippet] = field(default_factory=list)
    doc_types_found: List[str] = field(default_factory=list)
    doc_files: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation of SearchResult
        """
        return {
            "id": self.repository.id,
            "name": self.repository.name,
            "path_namespace": self.repository.path,
            "description": self.repository.description,
            "web_url": self.repository.url,
            "default_branch": self.repository.default_branch,
            "score": self.score,
            "matched_keywords": self.matched_keywords,
            "doc_snippets": [s.to_dict() for s in self.doc_snippets],
            "doc_types_found": self.doc_types_found,
            "doc_files": self.doc_files,
        }


@dataclass
class CacheStats:
    """Cache statistics for monitoring."""

    repos_cached: int = 0
    docs_cached: int = 0
    repos_indexed: int = 0
    errors: int = 0
    last_updated: Optional[float] = None
