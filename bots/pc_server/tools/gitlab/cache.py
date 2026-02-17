"""Cache management for GitLab data.

Manages two levels of caching:
1. Repository metadata cache - List of all repos with basic info
2. Documentation cache - Indexed documentation content per repository
"""

import json
import logging
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .models import CacheStats, DocFile, DocIndex, Repository

logger = logging.getLogger(__name__)


class GitLabCacheManager:
    """Manages caching for GitLab repository data and documentation.

    Provides persistent disk-based caching with TTL support for:
    - Repository metadata list
    - Repository documentation content

    Example:
        cache = GitLabCacheManager("/pc/cache")

        # Repository cache
        repos = cache.get_repositories()
        cache.set_repositories(repos)

        # Documentation cache
        doc_index = cache.get_doc_index("group/project")
        cache.set_doc_index("group/project", doc_index)
    """

    # Default TTL values (seconds)
    DEFAULT_REPO_CACHE_TTL = 3600  # 1 hour for repo list
    DEFAULT_DOC_CACHE_TTL = 86400  # 24 hours for documentation

    def __init__(
        self,
        cache_dir: str,
        repo_ttl: int = DEFAULT_REPO_CACHE_TTL,
        doc_ttl: int = DEFAULT_DOC_CACHE_TTL,
    ):
        """Initialize cache manager.

        Args:
            cache_dir: Directory for cache files
            repo_ttl: Repository cache TTL in seconds
            doc_ttl: Documentation cache TTL in seconds
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.repo_ttl = repo_ttl
        self.doc_ttl = doc_ttl

        # Cache file paths
        self._repo_cache_file = self.cache_dir / "repositories_cache.json"
        self._doc_cache_file = self.cache_dir / "documentation_cache.json"

        # In-memory caches
        self._repo_cache: Optional[List[Repository]] = None
        self._doc_cache: Dict[str, DocIndex] = {}

        # Cache timestamps
        self._repo_cache_time: float = 0
        self._doc_cache_time: float = 0

        # Statistics
        self.stats = CacheStats()

        # Load existing caches
        self._load_repositories()
        self._load_documentation()

    # === Repository Cache ===

    def _load_repositories(self) -> None:
        """Load repository cache from disk."""
        try:
            if self._repo_cache_file.exists():
                with open(self._repo_cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    repos_data = data.get("repositories", [])
                    self._repo_cache = [Repository(**repo_data) for repo_data in repos_data]
                    self._repo_cache_time = data.get("timestamp", 0)
                    self.stats.repos_cached = len(self._repo_cache)
                logger.info(f"Loaded repository cache: {self.stats.repos_cached} repos")
        except Exception as e:
            logger.warning(f"Failed to load repository cache: {e}")
            self._repo_cache = None
            self._repo_cache_time = 0

    def _save_repositories(self) -> None:
        """Save repository cache to disk."""
        if self._repo_cache is None:
            return

        try:
            data = {
                "repositories": [asdict(repo) for repo in self._repo_cache],
                "timestamp": datetime.now().timestamp(),
                "version": "1.0",
            }
            with open(self._repo_cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"Saved repository cache: {len(self._repo_cache)} repos")
        except Exception as e:
            logger.error(f"Failed to save repository cache: {e}")

    def is_repo_cache_valid(self) -> bool:
        """Check if repository cache is still valid (within TTL).

        Returns:
            True if cache is valid, False otherwise
        """
        if self._repo_cache is None:
            return False
        age = datetime.now().timestamp() - self._repo_cache_time
        return age < self.repo_ttl

    def get_repositories(self) -> Optional[List[Repository]]:
        """Get cached repositories if valid.

        Returns:
            List of repositories or None if cache invalid/empty
        """
        if self.is_repo_cache_valid():
            return self._repo_cache
        return None

    def set_repositories(self, repositories: List[Repository]) -> None:
        """Update repository cache.

        Args:
            repositories: List of repositories to cache

        Returns:
            None
        """
        self._repo_cache = repositories
        self._repo_cache_time = datetime.now().timestamp()
        self.stats.repos_cached = len(repositories)
        self.stats.last_updated = self._repo_cache_time
        self._save_repositories()

    # === Documentation Cache ===

    def _serialize_doc_index(self, index: DocIndex) -> Dict:
        """Serialize DocIndex to JSON-compatible dict.

        Args:
            index: DocIndex to serialize

        Returns:
            Dictionary representation of DocIndex
        """
        return {
            "repo_path": index.repo_path,
            "doc_type": index.doc_type.name,
            "best_file": index.best_file,
            "files": {
                path: {
                    "path": f.path,
                    "name": f.name,
                    "doc_type": f.doc_type.name,
                    "content": f.content,
                    "size": f.size,
                    "cached_at": f.cached_at,
                    "ref": f.ref,
                }
                for path, f in index.files.items()
            },
        }

    def _deserialize_doc_index(self, data: Dict) -> DocIndex:
        """Deserialize DocIndex from dict.

        Args:
            data: Dictionary to deserialize

        Returns:
            DocIndex instance
        """
        from .models import DocType

        files = {}
        for path, f_data in data.get("files", {}).items():
            doc_type = DocType[f_data.get("doc_type", "README")]
            files[path] = DocFile(
                path=f_data["path"],
                name=f_data["name"],
                doc_type=doc_type,
                content=f_data.get("content", ""),
                size=f_data.get("size", 0),
                cached_at=f_data.get("cached_at", 0),
                ref=f_data.get("ref", "main"),
            )

        return DocIndex(
            repo_path=data["repo_path"],
            doc_type=DocType[data.get("doc_type", "README")],
            files=files,
            best_file=data.get("best_file"),
        )

    def _load_documentation(self) -> None:
        """Load documentation cache from disk."""
        try:
            if self._doc_cache_file.exists():
                with open(self._doc_cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    cache_data = data.get("cache", {})
                    self._doc_cache = {
                        path: self._deserialize_doc_index(idx_data)
                        for path, idx_data in cache_data.items()
                    }
                    self._doc_cache_time = data.get("timestamp", 0)
                    self.stats.docs_cached = sum(len(idx.files) for idx in self._doc_cache.values())
                logger.info(f"Loaded documentation cache: {len(self._doc_cache)} repos")
        except Exception as e:
            logger.warning(f"Failed to load documentation cache: {e}")
            self._doc_cache = {}
            self._doc_cache_time = 0

    def _save_documentation(self) -> None:
        """Save documentation cache to disk."""
        if not self._doc_cache:
            return

        try:
            data = {
                "cache": {
                    path: self._serialize_doc_index(idx) for path, idx in self._doc_cache.items()
                },
                "timestamp": datetime.now().timestamp(),
                "version": "2.0",
            }
            with open(self._doc_cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)

            total_files = sum(len(idx.files) for idx in self._doc_cache.values())
            logger.debug(
                f"Saved documentation cache: {len(self._doc_cache)} repos, {total_files} files"
            )
        except Exception as e:
            logger.error(f"Failed to save documentation cache: {e}")

    def is_doc_cache_valid(self) -> bool:
        """Check if documentation cache is still valid (within TTL).

        Returns:
            True if cache is valid, False otherwise
        """
        if not self._doc_cache:
            return False
        age = datetime.now().timestamp() - self._doc_cache_time
        return age < self.doc_ttl

    def get_doc_index(self, repo_path: str) -> Optional[DocIndex]:
        """Get documentation index for a repository.

        Args:
            repo_path: Repository path (e.g., 'group/project')

        Returns:
            DocIndex or None if not cached
        """
        return self._doc_cache.get(repo_path)

    def set_doc_index(self, repo_path: str, index: DocIndex) -> None:
        """Set documentation index for a repository.

        Args:
            repo_path: Repository path
            index: Documentation index

        Returns:
            None
        """
        self._doc_cache[repo_path] = index

    def get_all_doc_indices(self) -> Dict[str, DocIndex]:
        """Get all cached documentation indices.

        Returns:
            Dictionary mapping repo paths to DocIndex instances
        """
        return self._doc_cache.copy()

    def save(self) -> None:
        """Save all caches to disk.

        Returns:
            None
        """
        self._save_repositories()
        self._save_documentation()

        total_docs = sum(len(idx.files) for idx in self._doc_cache.values())
        self.stats.docs_cached = total_docs
        logger.info(f"Cache saved: {self.stats.repos_cached} repos, {total_docs} doc files")

    def clear(self) -> None:
        """Clear all caches.

        Returns:
            None
        """
        self._repo_cache = None
        self._repo_cache_time = 0
        self._doc_cache = {}
        self._doc_cache_time = 0
        self.stats = CacheStats()

        # Delete cache files
        for f in [self._repo_cache_file, self._doc_cache_file]:
            if f.exists():
                f.unlink()

        logger.info("Cache cleared")

    def get_stats(self) -> CacheStats:
        """Get cache statistics.

        Returns:
            CacheStats instance with current statistics
        """
        self.stats.docs_cached = sum(len(idx.files) for idx in self._doc_cache.values())
        return self.stats
