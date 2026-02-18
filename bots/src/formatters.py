"""Response formatters for different LLM models.

Handles formatting of special fields like reasoning, thinking, etc.
"""

import logging
import re
from typing import Any, Dict, List, Optional

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


def convert_latex_to_zulip_katex(content: str) -> str:
    """Convert standard LaTeX math delimiters to Zulip KaTeX syntax.

    LLMs output standard LaTeX: $...$ for inline math, $$...$$ for display math.
    Zulip uses KaTeX with different delimiters:
      - Inline math: $$...$$
      - Display/block math: ```math ... ```

    This function converts from standard LaTeX to Zulip KaTeX format,
    while preserving content inside code blocks.

    Args:
        content: Text content potentially containing LaTeX math.

    Returns:
        Content with math delimiters converted to Zulip KaTeX syntax.
    """
    if not content or "$" not in content:
        return content

    # Split content into protected (code blocks) and unprotected segments.
    # We protect fenced code blocks (```...```) and inline code (`...`).
    segments = _split_preserving_code_blocks(content)

    result_parts: List[str] = []
    for segment, is_code in segments:
        if is_code:
            result_parts.append(segment)
        else:
            converted = _convert_math_in_text(segment)
            result_parts.append(converted)

    return "".join(result_parts)


def _split_preserving_code_blocks(content: str) -> List[tuple]:
    """Split content into segments, marking code blocks as protected.

    Args:
        content: Raw text content.

    Returns:
        List of (segment_text, is_code) tuples.
    """
    # Match fenced code blocks (```...```) and inline code (`...`)
    # Fenced blocks first (greedy), then inline code (non-greedy)
    code_pattern = re.compile(r"(```[\s\S]*?```|`[^`\n]+`)")

    segments: List[tuple] = []
    last_end = 0

    for match in code_pattern.finditer(content):
        start, end = match.span()
        # Add text before code block
        if start > last_end:
            segments.append((content[last_end:start], False))
        # Add code block (protected)
        segments.append((match.group(0), True))
        last_end = end

    # Add remaining text after last code block
    if last_end < len(content):
        segments.append((content[last_end:], False))

    return segments


def _convert_math_in_text(text: str) -> str:
    """Convert LaTeX math delimiters in non-code text.

    Handles two conversions:
      1. Display math: $$...$$ → ```math\\n...\\n```
      2. Inline math: $...$ → $$...$$

    Args:
        text: Text segment without code blocks.

    Returns:
        Text with converted math delimiters.
    """
    # Step 1: Convert display/block math $$...$$ to ```math ... ```
    # Match $$ that may span multiple lines
    text = re.sub(
        r"\$\$([\s\S]*?)\$\$",
        _replace_display_math,
        text,
    )

    # Step 2: Convert inline math $...$ to $$...$$
    # Match single $ that:
    # - Is not preceded by $ or \ (avoid matching escaped or already-converted)
    # - Contains non-empty content without newlines (inline only)
    # - Is not followed by $ (avoid matching display math)
    text = re.sub(
        r"(?<!\$)(?<!\\)\$(?!\$)((?:[^$\\\n]|\\.)+)\$(?!\$)",
        r"$$\1$$",
        text,
    )

    return text


def _replace_display_math(match: re.Match) -> str:
    """Replace a display math match with Zulip math fence.

    Args:
        match: Regex match object for display math.

    Returns:
        Zulip-formatted math block.
    """
    math_content = match.group(1).strip()
    return f"\n```math\n{math_content}\n```\n"
