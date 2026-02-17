"""Security utilities shared across the project.

This module provides security-related functions and constants used by both
the main bot and PC sidecar to ensure consistent security policies.
"""

import re
from typing import Optional, Tuple

# Dangerous command patterns that should be blocked
DANGEROUS_PATTERNS = [
    "rm -rf",
    "mkfs",
    "dd if=",
    "chmod 777",
    "wget http://",
    "curl -s http://",
    "curl -o",
    "curl -L",
    'python -c "',
    'bash -c "',
    'sh -c "',
    "> /dev/",
    ">> /dev/",
    "| nc ",
    "nc -l",
    "socat ",
    "chattr",
    "setuid",
    "setgid",
    "chown root:",
    "chmod +s",
    "$(",
    "`",
    ";",
    "&&",
    "||",
    "&",
    "|",
    ">",
    "<",
    ">>",
    ":(){ :|:& };:",  # Fork bomb
    "echo vulnerable >",
    "cat >",
    "tee >",
]

# Sensitive patterns that should be filtered from logs
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

# Shell special characters that could enable injection
DANGEROUS_CHARS = [";", "&", "|", "$", "`", ">", "<"]


def validate_command(
    command: str, allowed_commands: Optional[list[str]] = None
) -> Tuple[bool, str]:
    """Validate command for security.

    Args:
        command: The command string to validate
        allowed_commands: Optional list of allowed command prefixes

    Returns:
        Tuple of (is_valid, message)

    Example:
        >>> validate_command("ls -la")
        (True, "Command validated")
        >>> validate_command("rm -rf /")
        (False, "Dangerous pattern detected: rm -rf")
    """
    if not command:
        return False, "Empty command"

    command_lower = command.lower()

    # Check for dangerous patterns
    for pattern in DANGEROUS_PATTERNS:
        if pattern in command_lower:
            return False, f"Dangerous pattern detected: {pattern}"

    # Check for shell special characters that could enable injection
    for char in DANGEROUS_CHARS:
        if char in command and f"\\{char}" not in command:
            return False, f"Potentially dangerous character: {char}"

    # If allowed commands list is configured, enforce it
    if allowed_commands:
        first_word = command.split()[0] if command.split() else ""
        if first_word not in allowed_commands:
            return False, f"Command not in allowed list: {first_word}"

    return True, "Command validated"


def filter_sensitive_content(text: str) -> str:
    """Filter sensitive information from logs.

    Args:
        text: The text to filter

    Returns:
        Filtered text with sensitive content redacted

    Example:
        >>> filter_sensitive_content("password=secret123")
        '[REDACTED DUE TO SENSITIVE CONTENT]'
    """
    if not text:
        return text

    filtered = text
    for pattern in SENSITIVE_PATTERNS:
        if pattern in filtered.lower():
            filtered = "[REDACTED DUE TO SENSITIVE CONTENT]"
            break

    # Also check for potential API keys (long alphanumeric strings)
    # Match strings that look like API keys/tokens (20+ chars alphanumeric)
    api_key_pattern = r"[A-Za-z0-9\-_]{20,}"
    filtered = re.sub(api_key_pattern, "[API_KEY_REDACTED]", filtered)

    return filtered
