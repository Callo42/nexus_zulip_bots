"""Documentation indexing for GitLab repositories.

Discovers and indexes documentation files from repositories with:
- Priority-based document type detection
- Content fetching and caching
- Incremental updates
"""

import logging
import re
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .cache import GitLabCacheManager
from .client import GitLabClient
from .models import DocFile, DocIndex, DocType, Repository

logger = logging.getLogger(__name__)


class GitLabDocIndexer:
    """Indexes documentation files from GitLab repositories.

    Supports multiple documentation types with priority weighting:
    - README (priority 5): README files
    - AGENTS (priority 4): AGENTS.md
    - CLAUDE (priority 4): CLAUDE.md
    - CHANGELOG (priority 3): CHANGELOG, CHANGES, HISTORY
    - ENTRY (priority 2): Entry point files

    Example:
        indexer = GitLabDocIndexer(client, cache_manager)

        # Index a single repository
        index = indexer.index_repository(repo)

        # Batch index multiple repositories
        stats = indexer.index_repositories(repo_list)
    """

    # File patterns for each documentation type (regex)
    DOC_PATTERNS: Dict[DocType, List[str]] = {
        DocType.README: [
            r"README[^/]*\.(md|rst|txt|markdown)?$",
            r"^README[^/]*$",
        ],
        DocType.AGENTS: [
            r"AGENTS\.md$",
        ],
        DocType.CLAUDE: [
            r"CLAUDE\.md$",
        ],
        DocType.CHANGELOG: [
            r"CHANGE(S|LOG)[^/]*\.(md|rst|txt)?$",
            r"HISTORY[^/]*\.(md|rst|txt)?$",
        ],
        DocType.ENTRY: [
            r"^main\.py$",
            r"^index\.(js|ts)$",
            r"^Cargo\.toml$",
            r"^package\.json$",
            r"^go\.mod$",
            r"^setup\.py$",
            r"^pyproject\.toml$",
        ],
    }

    # Allowed file extensions for documentation
    ALLOWED_EXTENSIONS: Set[str] = {
        ".md",
        ".rst",
        ".txt",
        ".markdown",
        ".py",
        ".js",
        ".ts",
        ".go",
        ".rs",
        ".json",
        ".toml",
        ".yaml",
        ".yml",
        "",  # Files without extension (Makefile, etc.)
    }

    # Sensitive file patterns to exclude
    SENSITIVE_PATTERNS: List[str] = [
        r"\.env",
        r"credential",
        r"secret",
        r"private",
        r"passwd",
        r"password",
        r"\.key",
        r"\.pem",
        r"token",
        r"api_key",
        r"auth",
        r"\.git/",
        r"ssh/",
        r"id_rsa",
        r"keystore",
        r"\.jks",
        r"\.p12",
        r"\.pfx",
        r"netrc",
        r"\.htpasswd",
    ]

    def __init__(self, client: GitLabClient, cache: GitLabCacheManager):
        """Initialize indexer.

        Args:
            client: GitLab API client
            cache: Cache manager for persistence
        """
        self.client = client
        self.cache = cache

    def _validate_file_path(self, file_path: str) -> Tuple[bool, str]:
        """Validate file path for security and file type.

        Args:
            file_path: File path to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not file_path:
            return False, "File path cannot be empty"

        path_lower = file_path.lower()

        # Check against sensitive patterns
        for pattern in self.SENSITIVE_PATTERNS:
            if re.search(pattern, path_lower):
                return False, "Access denied: matches sensitive pattern"

        # Check extension
        import os

        ext = os.path.splitext(file_path)[1].lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            return False, f"File type '{ext}' not allowed"

        return True, ""

    def _detect_doc_type(self, file_name: str) -> Optional[DocType]:
        """Detect documentation type from file name.

        Args:
            file_name: File name

        Returns:
            DocType or None if not a documentation file
        """
        # Check patterns in priority order (highest first)
        for doc_type in sorted(DocType, key=lambda x: x.value, reverse=True):
            patterns = self.DOC_PATTERNS.get(doc_type, [])
            for pattern in patterns:
                if re.search(pattern, file_name, re.IGNORECASE):
                    return doc_type
        return None

    def _find_doc_files(self, repo: Repository) -> Dict[DocType, List[Dict]]:
        """Find documentation files in repository tree.

        Args:
            repo: Repository to scan

        Returns:
            Dictionary mapping DocType to list of file metadata dictionaries
        """
        doc_files_by_type: Dict[DocType, List[Dict]] = {doc_type: [] for doc_type in DocType}

        # Fetch repository tree
        tree = self.client.list_tree(repo.path, recursive=True)

        for entry in tree:
            if entry.get("type") != "blob":  # Skip directories
                continue

            file_path = entry.get("path", "")
            file_name = entry.get("name", "")

            # Validate file
            is_valid, _ = self._validate_file_path(file_path)
            if not is_valid:
                continue

            # Detect documentation type
            doc_type = self._detect_doc_type(file_name)
            if doc_type:
                doc_files_by_type[doc_type].append(
                    {
                        "path": file_path,
                        "name": file_name,
                        "id": entry.get("id"),
                    }
                )

        return doc_files_by_type

    def _get_cached_index(
        self, repo_path: str, force_refresh: bool
    ) -> Tuple[Optional[DocIndex], bool]:
        """Check cache for existing doc index.

        Args:
            repo_path: Repository path
            force_refresh: Whether to force refresh

        Returns:
            Tuple of (cached_index or None, found_in_cache)
        """
        if force_refresh:
            return None, False

        cached = self.cache.get_doc_index(repo_path)
        if cached:
            logger.debug(f"Using cached doc index for {repo_path}")
            return cached, True

        return None, False

    def _select_doc_files(
        self, doc_files_by_type: Dict[DocType, List[Dict]]
    ) -> Tuple[Optional[DocType], List[Dict]]:
        """Select highest priority documentation type and files.

        Args:
            doc_files_by_type: Dictionary mapping DocType to file list

        Returns:
            Tuple of (selected_type or None, list of selected files)
        """
        for doc_type in sorted(DocType, key=lambda x: x.value, reverse=True):
            if doc_files_by_type[doc_type]:
                return doc_type, doc_files_by_type[doc_type]
        return None, []

    def _create_doc_file(
        self, file_meta: Dict, content: str, doc_type: DocType, ref: str
    ) -> DocFile:
        """Create a DocFile object from metadata and content.

        Args:
            file_meta: File metadata dictionary
            content: File content
            doc_type: Documentation type
            ref: Git reference

        Returns:
            DocFile instance
        """
        return DocFile(
            path=file_meta["path"],
            name=file_meta["name"],
            doc_type=doc_type,
            content=content,
            size=len(content.encode("utf-8")),
            ref=ref,
        )

    def _build_index_from_files(
        self,
        repo: Repository,
        selected_type: DocType,
        selected_files: List[Dict],
        cached: Optional[DocIndex],
    ) -> DocIndex:
        """Build doc index by fetching or reusing file contents.

        Args:
            repo: Repository to index
            selected_type: Selected documentation type
            selected_files: List of file metadata
            cached: Cached index if available

        Returns:
            DocIndex with files populated
        """
        index = DocIndex(
            repo_path=repo.path,
            doc_type=selected_type,
            best_file=selected_files[0]["path"] if selected_files else None,
        )

        for file_meta in selected_files:
            file_path = file_meta["path"]

            # Check if already cached and fresh
            if cached and file_path in cached.files:
                cached_file = cached.files[file_path]
                if cached_file.is_fresh(self.cache.doc_ttl):
                    index.files[file_path] = cached_file
                    continue

            # Fetch content
            content = self.client.get_file_content(repo.path, file_path, repo.default_branch)

            if content is not None:
                doc_file = self._create_doc_file(
                    file_meta, content, selected_type, repo.default_branch
                )
                index.files[file_path] = doc_file

        return index

    def index_repository(self, repo: Repository, force_refresh: bool = False) -> Optional[DocIndex]:
        """Index documentation for a single repository.

        Args:
            repo: Repository to index
            force_refresh: Force re-index even if cached

        Returns:
            DocIndex or None if no documentation found
        """
        # Check cache first
        cached, found_in_cache = self._get_cached_index(repo.path, force_refresh)
        if found_in_cache and cached is not None:
            return cached

        logger.debug(f"Indexing documentation for {repo.path}")

        # Find documentation files
        doc_files_by_type = self._find_doc_files(repo)

        # Select highest priority documentation type
        selected_type, selected_files = self._select_doc_files(doc_files_by_type)

        if not selected_type:
            logger.debug(f"No documentation found for {repo.path}")
            return None

        # Build index with file contents
        index = self._build_index_from_files(repo, selected_type, selected_files, cached)

        # Save to cache
        if index.files:
            self.cache.set_doc_index(repo.path, index)
            logger.debug(f"Indexed {len(index.files)} files for {repo.path}")
            return index

        return None

    def index_repositories(
        self,
        repositories: List[Repository],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, Any]:
        """Batch index multiple repositories.

        Args:
            repositories: List of repositories to index
            progress_callback: Optional callback(current, total) for progress reporting

        Returns:
            Statistics dictionary
        """
        stats = {
            "processed": 0,
            "indexed": 0,
            "skipped": 0,
            "errors": 0,
            "total_files": 0,
        }

        total = len(repositories)
        logger.info(f"Starting documentation indexing for {total} repositories")

        for i, repo in enumerate(repositories):
            try:
                index = self.index_repository(repo)

                if index:
                    stats["indexed"] += 1
                    stats["total_files"] += len(index.files)
                else:
                    stats["skipped"] += 1

                stats["processed"] += 1

                # Report progress
                if progress_callback and (i + 1) % 10 == 0:
                    progress_callback(i + 1, total)

                # Log progress
                if (i + 1) % 10 == 0:
                    logger.info(
                        f"Indexing progress: {i + 1}/{total} "
                        f"({stats['indexed']} indexed, {stats['total_files']} files)"
                    )

            except Exception as e:
                logger.error(f"Error indexing {repo.path}: {e}")
                stats["errors"] += 1

        # Save cache
        self.cache.save()

        logger.info(f"Indexing complete: {stats}")
        return stats

    def get_documentation_stats(self) -> Dict[str, Any]:
        """Get documentation indexing statistics.

        Returns:
            Dictionary with documentation statistics
        """
        indices = self.cache.get_all_doc_indices()

        type_counts: Dict[str, int] = {}
        total_files = 0

        for idx in indices.values():
            type_name = idx.doc_type.name
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
            total_files += len(idx.files)

        return {
            "repositories_indexed": len(indices),
            "total_files": total_files,
            "doc_types": type_counts,
            "cache_valid": self.cache.is_doc_cache_valid(),
        }
