"""Tools package for PC sidecar.

This package provides modular tools for the PC sidecar, organized by category:
- file_tools: File operations (list, read, write, delete)
- command_tools: Shell command execution
- system_tools: System information
- gitlab: GitLab repository access with documentation indexing
- web_search_tools: Web search using Tavily

Example:
    from tools import ToolRegistry, register_all_tools

    registry = ToolRegistry(pc_manager)
    register_all_tools(registry, pc_manager)

    result = registry.execute_tool("list_files", {"path": "/docs"})
"""

from .base import Tool, ToolContext
from .command_tools import register_command_tools
from .file_tools import register_file_tools
from .gitlab import register_gitlab_tools
from .registry import ToolRegistry
from .system_tools import register_system_tools
from .web_search_tools import register_web_search_tools


def register_all_tools(registry: ToolRegistry, pc_manager, memory_manager=None):
    """Register all available tools with the registry.

    Args:
        registry: ToolRegistry instance
        pc_manager: PCManager instance
        memory_manager: Optional MemoryManager instance (unused, kept for compatibility)
    """
    register_file_tools(registry, pc_manager)
    register_command_tools(registry, pc_manager)
    register_system_tools(registry, pc_manager)
    register_gitlab_tools(registry, pc_manager)
    register_web_search_tools(registry, pc_manager)


__all__ = [
    "Tool",
    "ToolContext",
    "ToolRegistry",
    "register_file_tools",
    "register_command_tools",
    "register_system_tools",
    "register_gitlab_tools",
    "register_web_search_tools",
    "register_all_tools",
]
