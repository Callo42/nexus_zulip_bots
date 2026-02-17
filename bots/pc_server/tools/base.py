"""Base classes for PC tools.

This module provides the foundation for the modular tool system,
including the Tool dataclass and ToolContext for execution.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

if TYPE_CHECKING:
    from ..history_manager import HistoryManager
    from ..pc_manager import PCManager


@dataclass
class Tool:
    """Represents an OpenAI-compatible tool.

    Attributes:
        name: Tool identifier
        description: Tool description for LLM
        parameters: JSON Schema for tool parameters
        execute_func: Function that executes the tool
        category: Tool category for organization
        dangerous: Whether tool requires explicit approval
        allowed_by_default: Whether tool is allowed by default
    """

    name: str
    description: str
    parameters: Dict[str, Any]
    execute_func: Callable[[Dict[str, Any]], Dict[str, Any]]
    category: str = "general"
    dangerous: bool = False
    allowed_by_default: bool = True

    def to_openai_format(self) -> Dict[str, Any]:
        """Convert to OpenAI tool definition format.

        Returns:
            Dictionary in OpenAI function format
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class ToolContext:
    """Context for tool execution.

    Provides access to PC manager and history manager for tools.
    """

    pc_manager: "PCManager"
    history_manager: Optional["HistoryManager"] = None
    user: str = "unknown"

    def get_pc_root(self) -> str:
        """Get PC root directory path.

        Returns:
            PC root directory path as string
        """
        return str(self.pc_manager.root)
