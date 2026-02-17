"""Response formatters for different LLM models.

Handles formatting of special fields like reasoning, thinking, etc.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ModelFormatter:
    """Formats LLM responses according to model-specific rules."""

    def __init__(self, model_config: Dict[str, Any], default_formatting: Dict[str, Any]):
        """Initialize formatter with model configuration.

        Args:
            model_config: Model-specific configuration dictionary
            default_formatting: Default formatting rules to apply
        """
        self.model_config = model_config
        self.default_formatting = default_formatting
        self.formatting_rules = model_config.get("formatting", {})

    def format_response(self, response: Dict[str, Any]) -> str:
        """
        Format LLM response according to model rules.

        Args:
            response: Raw LLM response dict with content and optional fields

        Returns:
            Formatted response string
        """
        content: str = response.get("content", "")

        # Apply default formatting rules (trim whitespace, etc.)
        # Note: Special fields like reasoning/thinking are intentionally NOT
        # rendered to users - they are used internally by LLM but hidden from output
        content = self._apply_default_formatting(content)

        return content

    def _apply_field_formatting(
        self,
        field_content: str,
        main_content: str,
        field_name: str,
        rule: Dict[str, Any],
    ) -> str:
        """Apply formatting for a specific field."""
        format_type = rule.get("format", "plain")

        if format_type == "markdown_quote":
            formatted = self._format_as_markdown_quote(field_content, rule)
        elif format_type == "markdown_code":
            formatted = self._format_as_markdown_code(field_content, rule)
        else:
            # Plain format - just use the content
            formatted = field_content

        # Determine placement
        if rule.get("prepend", True):
            return f"{formatted}\n\n{main_content}"
        else:
            return f"{main_content}\n\n{formatted}"

    def _format_as_markdown_quote(self, content: str, rule: Dict[str, Any]) -> str:
        """Format content as markdown quote block."""
        header = rule.get("header", "")
        lines = content.strip().split("\n")

        if header:
            formatted = f"> {header}\n> \n"
        else:
            formatted = ""

        formatted += "\n".join(f"> {line}" for line in lines)
        return formatted

    def _format_as_markdown_code(self, content: str, rule: Dict[str, Any]) -> str:
        """Format content as markdown code block."""
        language = rule.get("language", "")
        return f"```{language}\n{content.strip()}\n```"

    def _apply_default_formatting(self, content: str) -> str:
        """Apply default formatting rules to content."""
        if not content:
            return content

        result = content

        # Trim whitespace
        if self.default_formatting.get("trim_whitespace", True):
            result = result.strip()

        # Escape HTML (basic)
        if self.default_formatting.get("escape_html", False):
            result = result.replace("<", "&lt;").replace(">", "&gt;")

        return result


def get_formatter(model_name: str, model_registry: Dict[str, Any]) -> Optional[ModelFormatter]:
    """
    Get formatter for a model.

    Args:
        model_name: Name of the model
        model_registry: Loaded models.yml configuration

    Returns:
        ModelFormatter instance or None if model not found
    """
    models = model_registry.get("models", {})
    default_formatting = model_registry.get("default_formatting", {})

    if model_name not in models:
        logger.warning(f"Model '{model_name}' not found in registry, using default formatting")
        return ModelFormatter({"formatting": {}}, default_formatting)

    return ModelFormatter(models[model_name], default_formatting)
