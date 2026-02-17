"""Tool Manager for PC sidecar - provides OpenAI-compatible tool definitions and execution.

This module now serves as a thin wrapper around the modular tools package,
maintaining backward compatibility while delegating to specialized tool modules.

For new code, consider using tools.ToolRegistry directly.
"""

import logging
from typing import Any, Dict, List, Optional

from .tools import ToolRegistry, register_all_tools
from .tools.base import Tool

logger = logging.getLogger(__name__)


class ToolManager:
    """Manages tool definitions and execution with security controls.

    This class is now a thin wrapper around ToolRegistry for backward compatibility.
    All actual tool logic has been moved to the tools package.
    """

    def __init__(self, pc_manager, history_manager=None):
        """Initialize ToolManager with tool registry.

        Args:
            pc_manager: PCManager instance for file/command operations
            history_manager: Optional HistoryManager for history operations
        """
        self._registry: ToolRegistry = ToolRegistry(pc_manager, history_manager)
        register_all_tools(self._registry, pc_manager, history_manager)

        logger.info(f"ToolManager initialized with {len(self._registry.list_tools())} tools")

    def register_tool(self, tool) -> None:
        """Register a tool (delegates to registry).

        Args:
            tool: Tool instance to register

        Returns:
            None
        """
        self._registry.register_tool(tool)

    def get_tool(self, name: str) -> Optional[Any]:
        """Get a tool by name (delegates to registry).

        Args:
            name: Tool name

        Returns:
            Tool instance or None if not found
        """
        return self._registry.get_tool(name)

    def list_tools(
        self,
        include_dangerous: bool = True,
        allowed_only: bool = True,
        category: Optional[str] = None,
    ) -> List[Tool]:
        """List available tools (delegates to registry).

        Args:
            include_dangerous: Whether to include dangerous tools
            allowed_only: Whether to only return allowed tools
            category: Optional category filter

        Returns:
            List of matching tools
        """
        result: List[Tool] = self._registry.list_tools(include_dangerous, allowed_only, category)
        return result

    def list_tools_openai_format(
        self, include_dangerous: bool = False, allowed_only: bool = True
    ) -> Dict[str, Any]:
        """List tools in OpenAI-compatible format (delegates to registry).

        Args:
            include_dangerous: Whether to include dangerous tools
            allowed_only: Whether to only return allowed tools

        Returns:
            Dictionary with 'tools' key containing OpenAI format tools
        """
        result: Dict[str, Any] = self._registry.list_tools_openai_format(
            include_dangerous, allowed_only
        )
        return result

    def execute_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by name (delegates to registry).

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            Tool execution result
        """
        result: Dict[str, Any] = self._registry.execute_tool(name, arguments)
        return result

    def set_allowed_tools(self, tool_names: List[str]) -> None:
        """Set the list of allowed tools (delegates to registry).

        Args:
            tool_names: List of allowed tool names

        Returns:
            None
        """
        self._registry.set_allowed_tools(tool_names)

    def allow_all_tools(self) -> None:
        """Allow all tools (delegates to registry).

        Returns:
            None
        """
        self._registry.allow_all_tools()

    def allow_safe_tools_only(self) -> None:
        """Allow only safe tools (delegates to registry).

        Returns:
            None
        """
        self._registry.allow_safe_tools_only()
