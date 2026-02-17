"""Search engine for GitLab repositories.

Provides content-aware search with:
- Metadata matching (name, description, path)
- Documentation content matching with priority weighting
- Fuzzy keyword matching with snippet extraction
"""

import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from .cache import GitLabCacheManager
from .client import GitLabClient
from .indexer import GitLabDocIndexer
from .models import DocIndex, DocSnippet, Repository, SearchResult

logger = logging.getLogger(__name__)


class GitLabSearchEngine:
    """Search engine for GitLab repositories.

    Performs two-phase search:
    1. Metadata search: Match query against repo name/description/path
    2. Content search: Match query against documentation content

    Results are ranked by combined score with documentation priority weights.

    Example:
        engine = GitLabSearchEngine(client, cache, indexer)
        results = engine.search("python web framework", top_k=10)

        for result in results:
            print(f"{result.repository.name}: {result.score}")
            for snippet in result.doc_snippets:
                print(f"  {snippet.snippet}")
    """

    # Field weights for metadata search
    METADATA_WEIGHTS = {
        "name": 3,  # Name has highest weight
        "description": 2,  # Description medium weight
        "path": 1,  # Path lowest weight
    }

    # Score bonuses
    EXACT_MATCH_BONUS = 10
    WORD_MATCH_BONUS = 10
    SUBSTRING_MATCH = 1

    def __init__(
        self,
        client: GitLabClient,
        cache: GitLabCacheManager,
        indexer: Optional[GitLabDocIndexer] = None,
    ):
        """Initialize search engine.

        Args:
            client: GitLab API client
            cache: Cache manager
            indexer: Optional doc indexer (for cache warming)
        """
        self.client = client
        self.cache = cache
        self.indexer = indexer or GitLabDocIndexer(client, cache)

    def _extract_keywords(self, query: str) -> List[str]:
        """Extract search keywords from query.

        Args:
            query: Search query

        Returns:
            List of keywords
        """
        query_lower = query.lower()
        keywords = [k.strip() for k in re.split(r"[\s,;]+", query_lower) if k.strip()]
        return keywords if keywords else [query_lower]

    def _score_metadata_match(self, repo: Repository, keywords: List[str]) -> Tuple[int, Set[str]]:
        """Score repository metadata match.

        Args:
            repo: Repository to score
            keywords: Search keywords

        Returns:
            Tuple of (score, matched_keywords)
        """
        score = 0
        matched = set()

        # Fields to search with weights
        fields = [
            (repo.name.lower(), self.METADATA_WEIGHTS["name"]),
            (repo.description.lower(), self.METADATA_WEIGHTS["description"]),
            (repo.path.lower(), self.METADATA_WEIGHTS["path"]),
        ]

        for field_value, weight in fields:
            for keyword in keywords:
                # Exact match
                if keyword == field_value:
                    score += self.EXACT_MATCH_BONUS * weight
                    matched.add(f"{keyword}(exact)")
                # Substring match
                elif keyword in field_value:
                    score += self.SUBSTRING_MATCH * weight
                    matched.add(keyword)

        return score, matched

    def _extract_snippets(self, content: str, keyword: str, max_snippets: int = 2) -> List[str]:
        """Extract text snippets around keyword matches.

        Args:
            content: Document content
            keyword: Keyword to find
            max_snippets: Maximum snippets per document

        Returns:
            List of snippet strings
        """
        pattern = r".{0,100}" + re.escape(keyword) + r".{0,100}"
        matches = re.finditer(pattern, content, re.IGNORECASE)

        snippets = []
        for match in list(matches)[:max_snippets]:
            snippet = match.group(0).strip()
            # Normalize whitespace
            snippet = re.sub(r"\s+", " ", snippet)
            snippets.append(f"...{snippet}...")

        return snippets

    def _search_content(
        self, repo_path: str, index: DocIndex, keywords: List[str]
    ) -> Tuple[int, Set[str], List[DocSnippet]]:
        """Search documentation content.

        Args:
            repo_path: Repository path
            index: Documentation index
            keywords: Search keywords

        Returns:
            Tuple of (score, matched_keywords, snippets)
        """
        score = 0
        matched = set()
        snippets = []

        priority = index.priority

        for file_path, doc_file in index.files.items():
            content = doc_file.content
            content_lower = content.lower()

            for keyword in keywords:
                if keyword not in content_lower:
                    continue

                # Check for word boundary match
                if re.search(r"\b" + re.escape(keyword) + r"\b", content_lower):
                    score += self.WORD_MATCH_BONUS * priority
                    matched.add(f"{index.doc_type.name}:{keyword}(exact)")
                else:
                    score += self.SUBSTRING_MATCH * priority
                    matched.add(f"{index.doc_type.name}:{keyword}")

                # Extract snippets
                for snippet_text in self._extract_snippets(content, keyword):
                    snippets.append(
                        DocSnippet(
                            file=file_path,
                            snippet=snippet_text,
                            keyword=keyword,
                            doc_type=index.doc_type,
                        )
                    )

        return score, matched, snippets

    def _get_repositories(self) -> Optional[List[Repository]]:
        """Get repositories from cache or fetch from client.

        Returns:
            List of repositories or None if not available
        """
        repos = self.cache.get_repositories()
        if repos is None:
            repos = self.client.get_all_repositories()
            self.cache.set_repositories(repos)
        return repos

    def _filter_candidates_by_metadata(
        self, repos: List[Repository], keywords: List[str]
    ) -> List[Dict[str, Any]]:
        """Filter repositories based on metadata matching.

        Args:
            repos: List of repositories
            keywords: Search keywords

        Returns:
            List of candidate dictionaries with repo, score, and matched keywords
        """
        candidates = []
        for repo in repos:
            score, matched = self._score_metadata_match(repo, keywords)
            if score > 0:
                candidates.append({"repo": repo, "score": score, "matched": matched})
        return candidates

    def _warmup_cache_if_needed(self, candidates: List[Dict[str, Any]], warm_cache: bool) -> None:
        """Warm up documentation cache if needed.

        Args:
            candidates: List of candidate repositories
            warm_cache: Whether to warm cache
        """
        if not warm_cache or self.cache.is_doc_cache_valid():
            return

        logger.info("Documentation cache empty or stale, warming up...")
        from typing import cast

        warmup_repos = [cast(Repository, c["repo"]) for c in candidates[:100]]
        self.indexer.index_repositories(warmup_repos)

    def _build_search_results(
        self,
        candidates: List[Dict[str, Any]],
        keywords: List[str],
        top_k: int,
    ) -> List[SearchResult]:
        """Build final search results with content enhancement.

        Args:
            candidates: List of candidate repositories
            keywords: Search keywords
            top_k: Maximum results to return

        Returns:
            List of SearchResult objects
        """
        from typing import cast

        results: List[SearchResult] = []
        for item in candidates[: top_k * 3]:
            repo = cast(Repository, item["repo"])
            total_score = cast(int, item["score"])
            all_matched: set[str] = set(cast(List[str], item["matched"]))
            doc_snippets: List[DocSnippet] = []
            doc_files: List[str] = []
            doc_types: List[str] = []

            # Check documentation index
            index = self.cache.get_doc_index(repo.path)
            if index:
                content_score, content_matched, snippets = self._search_content(
                    repo.path, index, keywords
                )
                total_score += content_score
                all_matched.update(content_matched)
                doc_snippets.extend(snippets)
                doc_types.append(index.doc_type.name)
                doc_files.extend(s.file for s in snippets)

            # Build result
            results.append(
                SearchResult(
                    repository=repo,
                    score=total_score,
                    matched_keywords=list(all_matched),
                    doc_snippets=doc_snippets[:5],
                    doc_types_found=list(set(doc_types)),
                    doc_files=list(set(doc_files))[:3],
                )
            )

        # Sort by score and return top results
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    def search(self, query: str, top_k: int = 10, warm_cache: bool = True) -> List[SearchResult]:
        """Search repositories with content enhancement.

        Args:
            query: Search query
            top_k: Maximum results to return
            warm_cache: Whether to warm documentation cache if empty

        Returns:
            List of SearchResult objects sorted by relevance
        """
        query = query.strip()
        if not query:
            return []

        top_k = max(1, min(50, top_k))
        keywords = self._extract_keywords(query)

        logger.info(f"GitLab search: '{query}' (keywords: {keywords}, top_k={top_k})")

        # Step 1: Get repositories
        repos = self._get_repositories()
        if not repos:
            logger.warning("No repositories available for search")
            return []

        # Step 2: Metadata-based filtering and scoring
        candidates = self._filter_candidates_by_metadata(repos, keywords)
        if not candidates:
            logger.info("No metadata matches found")
            return []

        # Sort candidates by score
        candidates.sort(key=lambda x: x["score"], reverse=True)

        # Step 3: Warm up cache if needed
        self._warmup_cache_if_needed(candidates, warm_cache)

        # Step 4: Build final results with content enhancement
        results = self._build_search_results(candidates, keywords, top_k)

        logger.info(f"Search complete: {len(results)} results for '{query}'")
        return results

    def search_repositories(
        self, query: str, top_k: int = 10, warm_cache: bool = True
    ) -> Dict[str, Any]:
        """Search repositories and return results as dictionary.

        This is the main interface for tool execution.

        Args:
            query: Search query
            top_k: Maximum results
            warm_cache: Whether to warm cache

        Returns:
            Dictionary with success status and results
        """
        try:
            results = self.search(query, top_k, warm_cache)

            return {
                "success": True,
                "repositories": [r.to_dict() for r in results],
                "query": query,
                "count": len(results),
                "method": "metadata+content",
            }
        except Exception as e:
            logger.error(f"Search failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "query": query,
            }
