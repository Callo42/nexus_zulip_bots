"""Security utilities for PC sidecar.

This module re-exports security utilities from the shared utils package.
"""

from src.utils.security import (
    DANGEROUS_PATTERNS,
    SENSITIVE_PATTERNS,
    filter_sensitive_content,
    validate_command,
)

__all__ = [
    "DANGEROUS_PATTERNS",
    "SENSITIVE_PATTERNS",
    "validate_command",
    "filter_sensitive_content",
]
