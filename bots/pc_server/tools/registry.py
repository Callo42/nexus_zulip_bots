"""Tool registry for managing and executing tools.

This module provides a central registry for all tools, enabling
dynamic tool registration and execution with security controls.
"""

import logging
from typing import Any, Dict, List, Optional

from .base import Tool, ToolContext

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for managing and executing tools.

    The registry manages tool instances and provides:
    - Tool registration and lookup
    - Tool execution with security controls
    - Tool filtering by category and safety

    Example:
        registry = ToolRegistry(pc_manager, history_manager)
        registry.register_tool(my_tool)
        result = registry.execute_tool("list_files", {"path": "/docs"})
    """

    def __init__(self, pc_manager, history_manager=None, user: str = "unknown"):
        """Initialize tool registry.

        Args:
            pc_manager: PCManager instance for file/command operations
            history_manager: Optional HistoryManager for history operations
            user: User identifier for audit logging
        """
        self._tools: Dict[str, Tool] = {}
        self._allowed_tools: Optional[List[str]] = None
        self._context = ToolContext(
            pc_manager=pc_manager, history_manager=history_manager, user=user
        )

    def register_tool(self, tool: Tool) -> None:
        """Register a tool in the registry.

        Args:
            tool: Tool instance to register

        Returns:
            None
        """
        self._tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")

    def get_tool(self, name: str) -> Optional[Tool]:
        """Get a tool by name.

        Args:
            name: Tool name

        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(name)

    def list_tools(
        self,
        include_dangerous: bool = True,
        allowed_only: bool = True,
        category: Optional[str] = None,
    ) -> List[Tool]:
        """List available tools with optional filtering.

        Args:
            include_dangerous: Whether to include dangerous tools
            allowed_only: Whether to only return allowed tools
            category: Optional category filter

        Returns:
            List of matching tools
        """
        tools = list(self._tools.values())

        if not include_dangerous:
            tools = [t for t in tools if not t.dangerous]

        if allowed_only and self._allowed_tools is not None:
            tools = [t for t in tools if t.name in self._allowed_tools]

        if category:
            tools = [t for t in tools if t.category == category]

        return tools

    def list_tools_openai_format(
        self, include_dangerous: bool = False, allowed_only: bool = True
    ) -> Dict[str, Any]:
        """List tools in OpenAI-compatible format.

        Args:
            include_dangerous: Whether to include dangerous tools
            allowed_only: Whether to only return allowed tools

        Returns:
            Dictionary with 'tools' key containing OpenAI format tools
        """
        tools = self.list_tools(include_dangerous, allowed_only)
        return {"tools": [t.to_openai_format() for t in tools], "count": len(tools)}

    def execute_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by name.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            Tool execution result

        Raises:
            ValueError: If tool not found
            PermissionError: If tool not allowed
        """
        tool = self.get_tool(name)
        if not tool:
            return {"success": False, "error": f"Tool '{name}' not found"}

        if self._allowed_tools is not None and name not in self._allowed_tools:
            return {"success": False, "error": f"Tool '{name}' is not allowed"}

        try:
            logger.info(f"Executing tool: {name}")
            result = tool.execute_func(arguments)
            return result
        except Exception as e:
            logger.error(f"Tool execution failed: {name} - {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def set_allowed_tools(self, tool_names: List[str]) -> None:
        """Set the list of allowed tools.

        Args:
            tool_names: List of allowed tool names

        Returns:
            None
        """
        self._allowed_tools = tool_names
        logger.info(f"Allowed tools set: {tool_names}")

    def allow_all_tools(self) -> None:
        """Allow all tools (clear allowed list).

        Returns:
            None
        """
        self._allowed_tools = None
        logger.info("All tools allowed")

    def allow_safe_tools_only(self) -> None:
        """Allow only safe (non-dangerous) tools.

        Returns:
            None
        """
        self._allowed_tools = [name for name, tool in self._tools.items() if not tool.dangerous]
        logger.info(f"Safe tools only: {self._allowed_tools}")
