"""Authentication utilities for PC API.

Provides API key authentication and audit logging hooks.
"""

import json
import logging
import time
from functools import wraps
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import g, request

logger = logging.getLogger(__name__)


class AuthManager:
    """Manages API key authentication and security logging.

    This class handles:
    - API key validation
    - Audit event logging
    - Security-sensitive content filtering
    """

    # Sensitive patterns to filter from logs
    SENSITIVE_PATTERNS = [
        "password=",
        "key=",
        "secret=",
        "token=",
        "auth=",
        "api_key=",
        "apikey=",
        "credential=",
        "cred=",
        "passwd=",
        "pwd=",
        "mysql://",
        "postgres://",
        "mongodb://",
        "redis://",
        "http://",
        "https://",
    ]

    def __init__(self, keys_file: Path, audit_log_file: Path, legacy_api_key: str = ""):
        """Initialize auth manager.

        Args:
            keys_file: Path to valid API keys JSON file
            audit_log_file: Path to audit log file
            legacy_api_key: Legacy single API key for backward compatibility
        """
        self.keys_file = keys_file
        self.audit_log_file = audit_log_file
        self.legacy_api_key = legacy_api_key

        # Ensure directories exist
        self.keys_file.parent.mkdir(parents=True, exist_ok=True)
        self.audit_log_file.parent.mkdir(parents=True, exist_ok=True)

    def filter_sensitive_content(self, text: str) -> str:
        """Filter sensitive information from logs.

        Args:
            text: Text to filter

        Returns:
            Filtered text with sensitive content redacted
        """
        if not text:
            return text

        filtered = text
        for pattern in self.SENSITIVE_PATTERNS:
            if pattern in filtered.lower():
                filtered = "[REDACTED DUE TO SENSITIVE CONTENT]"
                break

        # Check for potential API keys (long alphanumeric strings)
        import re

        api_key_pattern = r"[A-Za-z0-9\-_]{20,}"
        filtered = re.sub(api_key_pattern, "[API_KEY_REDACTED]", filtered)

        return filtered

    def load_valid_keys(self) -> List[str]:
        """Load valid API keys from file.

        Returns:
            List of valid API keys
        """
        try:
            if self.keys_file.exists():
                with open(self.keys_file, "r") as f:
                    keys = json.load(f)
                    if isinstance(keys, list):
                        return keys
        except Exception as e:
            logger.error(f"Failed to load valid keys: {e}")

        # Fallback to legacy key
        if self.legacy_api_key:
            return [self.legacy_api_key]
        return []

    def save_valid_keys(self, keys: List[str]) -> None:
        """Save valid API keys to file.

        Args:
            keys: List of valid API keys

        Returns:
            None
        """
        try:
            with open(self.keys_file, "w") as f:
                json.dump(keys, f, indent=2)
            logger.info(f"Saved {len(keys)} valid keys")
        except Exception as e:
            logger.error(f"Failed to save valid keys: {e}")

    def generate_new_key(self, length: int = 32) -> str:
        """Generate a new random API key.

        Args:
            length: Key length

        Returns:
            Generated API key
        """
        import secrets
        import string

        alphabet = string.ascii_letters + string.digits + "-_"
        return "".join(secrets.choice(alphabet) for _ in range(length))

    def validate_api_key(self, api_key: str) -> bool:
        """Validate an API key.

        Args:
            api_key: API key to validate

        Returns:
            True if valid, False otherwise
        """
        if not api_key:
            return False

        valid_keys = self.load_valid_keys()

        # If no keys configured, allow all (development mode)
        if not valid_keys:
            logger.warning("No API keys configured - allowing unauthenticated access")
            return True

        return api_key in valid_keys

    def log_audit_event(
        self,
        event_type: str,
        user: str = "",
        command: str = "",
        success: bool = False,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log security audit event.

        Args:
            event_type: Type of event (e.g., 'command_execute', 'file_read')
            user: User identifier
            command: Command or action
            success: Whether the action succeeded
            details: Additional details

        Returns:
            None
        """
        audit_entry = {
            "timestamp": time.time(),
            "event_type": event_type,
            "user": user or "unknown",
            "command": self.filter_sensitive_content(command) if command else "",
            "success": success,
            "details": details or {},
        }

        try:
            with open(self.audit_log_file, "a") as f:
                f.write(json.dumps(audit_entry) + "\n")
            logger.info(f"AUDIT: {json.dumps(audit_entry)}")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

    def get_audit_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve audit logs.

        Args:
            limit: Maximum number of logs to return

        Returns:
            List of audit log entries
        """
        logs = []
        try:
            if self.audit_log_file.exists():
                with open(self.audit_log_file, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                logs.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue

            # Return most recent first
            return list(reversed(logs))[:limit]
        except Exception as e:
            logger.error(f"Failed to read audit logs: {e}")
            return []


def require_api_key(auth_manager: AuthManager):
    """Require API key authentication decorator.

    Args:
        auth_manager: AuthManager instance

    Returns:
        Decorator function
    """

    def decorator(f):
        """Wrap function with API key authentication check.

        Args:
            f: Function to decorate

        Returns:
            Decorated function with authentication check
        """

        @wraps(f)
        def decorated_function(*args, **kwargs):
            """Perform authentication check before calling the wrapped function.

            Args:
                *args: Positional arguments passed to the original function
                **kwargs: Keyword arguments passed to the original function

            Returns:
                Result of the original function if authenticated, or error response if not
            """
            # Skip auth for health checks
            if request.path == "/health":
                return f(*args, **kwargs)

            # Get API key from header
            api_key = request.headers.get("X-API-Key", "")

            if not auth_manager.validate_api_key(api_key):
                return {"error": "Unauthorized - invalid API key"}, 401

            # Store user info for audit logging
            g.user = api_key[:8] + "..." if api_key else "anonymous"

            return f(*args, **kwargs)

        return decorated_function

    return decorator
