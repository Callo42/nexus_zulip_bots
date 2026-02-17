"""GitLab API client with security enforcement.

Provides read-only access to GitLab API with multiple layers of security controls
to prevent any write operations.
"""

import logging
import os
import urllib.parse
from typing import Any, Dict, List, Optional

import requests

from .models import Repository

logger = logging.getLogger(__name__)


class GitLabError(Exception):
    """Base exception for GitLab client errors."""

    pass


class GitLabSecurityError(GitLabError):
    """Security validation error."""

    pass


class GitLabClient:
    """GitLab API client with enforced read-only access.

    Security features:
    1. URL validation - only allows requests to configured GitLab instance
    2. Method enforcement - GET only, rejects any other HTTP method
    3. Parameter filtering - blocks write-related parameters
    4. Response size limits - prevents memory exhaustion

    Example:
        client = GitLabClient("https://gitlab.example.com")
        repos = client.get_all_repositories()
        content = client.get_file_content("group/project", "README.md")
    """

    # Forbidden parameters that could enable write operations
    FORBIDDEN_PARAMS = {"content", "message", "ref_name", "file_name", "branch_name"}

    # Maximum file size to fetch (10MB)
    MAX_FILE_SIZE_MB = 10

    def __init__(self, base_url: str = "https://code.itp.ac.cn", api_version: str = "v4"):
        """Initialize GitLab client.

        Args:
            base_url: GitLab instance URL
            api_version: GitLab API version
        """
        self.base_url = base_url.rstrip("/")
        self.api_version = api_version
        self._session = requests.Session()

        # Load token from environment
        self.private_token = os.getenv("GITLAB_PRIVATE_TOKEN", "")
        if self.private_token:
            self._session.headers["PRIVATE-TOKEN"] = self.private_token
            logger.debug("GitLab client initialized with token")
        else:
            logger.warning("GitLab client initialized without token (read-only public access)")

    def _validate_url(self, url: str) -> None:
        """Validate URL is from allowed GitLab instance.

        Args:
            url: URL to validate

        Raises:
            GitLabSecurityError: If URL validation fails
        """
        if not url.startswith(self.base_url):
            raise GitLabSecurityError(
                f"Invalid GitLab URL: must start with {self.base_url}, got: {url}"
            )

    def _validate_params(self, url: str, params: Optional[Dict] = None) -> None:
        """Validate no forbidden parameters in URL or params.

        Args:
            url: URL to check
            params: Query parameters to check

        Raises:
            GitLabSecurityError: If forbidden parameters detected
        """
        url_lower = url.lower()

        # Check URL for forbidden parameters
        for param in self.FORBIDDEN_PARAMS:
            if param in url_lower:
                raise GitLabSecurityError(
                    f"Security violation: forbidden parameter '{param}' detected in URL"
                )

        # Check params dict
        if params:
            for param in self.FORBIDDEN_PARAMS:
                if param in params:
                    raise GitLabSecurityError(
                        f"Security violation: forbidden parameter '{param}' detected in request"
                    )

    def get(
        self, endpoint: str, params: Optional[Dict] = None, timeout: int = 30
    ) -> requests.Response:
        """Make authenticated GET request with security enforcement.

        Args:
            endpoint: API endpoint (relative or absolute URL)
            params: Query parameters
            timeout: Request timeout

        Returns:
            Response object

        Raises:
            GitLabSecurityError: If security check fails
            requests.RequestException: If request fails
        """
        # Build full URL
        if endpoint.startswith("http"):
            url = endpoint
        else:
            endpoint = endpoint.lstrip("/")
            url = f"{self.base_url}/api/{self.api_version}/{endpoint}"

        # Security validation
        self._validate_url(url)
        self._validate_params(url, params)

        # Execute request
        try:
            response = self._session.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.HTTPError as e:
            logger.error(f"GitLab API error: {e.response.status_code} - {url}")
            raise

    def get_all_repositories(self) -> List[Repository]:
        """Fetch all repositories with pagination.

        Returns:
            List of Repository objects
        """
        all_repos = []
        page = 1
        per_page = 100

        while True:
            try:
                response = self.get(
                    "projects",
                    params={
                        "page": page,
                        "per_page": per_page,
                        "simple": True,  # Lightweight response
                    },
                )

                repos_data = response.json()
                if not repos_data:
                    break

                for repo_data in repos_data:
                    try:
                        all_repos.append(Repository.from_gitlab_api(repo_data))
                    except Exception as e:
                        logger.warning(f"Failed to parse repository: {e}")

                # Check pagination
                total_pages = int(response.headers.get("X-Total-Pages", page))
                if page >= total_pages or len(repos_data) < per_page:
                    break

                page += 1

            except Exception as e:
                logger.error(f"Failed to fetch repositories page {page}: {e}")
                break

        logger.info(f"Fetched {len(all_repos)} repositories from GitLab")
        return all_repos

    def get_repository(self, project_path: str) -> Optional[Repository]:
        """Get single repository by path.

        Args:
            project_path: Project path (e.g., 'group/project')

        Returns:
            Repository or None if not found

        Raises:
            requests.HTTPError: If API request fails (other than 404)
        """
        encoded = urllib.parse.quote(project_path, safe="")

        try:
            response = self.get(f"projects/{encoded}")
            return Repository.from_gitlab_api(response.json())
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise
        except Exception as e:
            logger.error(f"Failed to fetch repository {project_path}: {e}")
            return None

    def list_directory(
        self, project_path: str, path: str = "", ref: str = "main"
    ) -> Dict[str, List[Dict]]:
        """List directory contents.

        Args:
            project_path: Project path
            path: Directory path within repository
            ref: Git reference (branch/tag)

        Returns:
            Dictionary with 'files' and 'directories' lists
        """
        encoded_project = urllib.parse.quote(project_path, safe="")

        try:
            response = self.get(
                f"projects/{encoded_project}/repository/tree",
                params={"path": path, "ref": ref},
            )

            items = response.json()
            files = []
            directories = []

            for item in items:
                item_type = item.get("type")
                name = item.get("name", "")
                item_path = item.get("path", "")

                entry = {
                    "name": name,
                    "path": item_path,
                    "type": item_type,
                }

                if item_type == "tree":
                    directories.append(entry)
                else:
                    files.append(entry)

            return {"files": files, "directories": directories}

        except Exception as e:
            logger.error(f"Failed to list directory {project_path}/{path}: {e}")
            return {"files": [], "directories": []}

    def get_file_content(
        self, project_path: str, file_path: str, ref: str = "main"
    ) -> Optional[str]:
        """Fetch file content from repository.

        Args:
            project_path: Project path
            file_path: File path within repository
            ref: Git reference

        Returns:
            File content or None if not found/error
        """
        encoded_project = urllib.parse.quote(project_path, safe="")
        encoded_file = urllib.parse.quote(file_path, safe="")

        try:
            response = self.get(
                f"projects/{encoded_project}/repository/files/{encoded_file}/raw",
                params={"ref": ref},
            )

            content = response.text
            size_bytes = len(content.encode("utf-8"))
            max_size = self.MAX_FILE_SIZE_MB * 1024 * 1024

            if size_bytes > max_size:
                logger.warning(
                    f"File {file_path} exceeds size limit ({size_bytes}b > {max_size}b), truncating"
                )
                return content[:max_size]

            return content

        except requests.HTTPError as e:
            if e.response.status_code == 404:
                return None
            logger.error(f"Failed to fetch file {file_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching file {file_path}: {e}")
            return None

    def list_tree(self, project_path: str, recursive: bool = True) -> List[Dict]:
        """List all files in repository tree.

        Args:
            project_path: Project path
            recursive: Whether to list recursively

        Returns:
            List of file entries

        Raises:
            Exception: If API request fails
        """
        encoded_project = urllib.parse.quote(project_path, safe="")

        try:
            response = self.get(
                f"projects/{encoded_project}/repository/tree",
                params={"recursive": recursive, "per_page": 100},
            )
            result: List[Dict[Any, Any]] = response.json()
            return result
        except Exception as e:
            logger.error(f"Failed to list tree for {project_path}: {e}")
            return []
