"""Command execution tools.

Tools for executing shell commands in the PC.
"""

from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from ..pc_manager import PCManager


def create_execute_command_tool(pc_manager: "PCManager"):
    """Create execute_command tool.

    Args:
        pc_manager: PCManager instance for command execution

    Returns:
        Tool instance for execute_command
    """
    from .base import Tool

    def execute_command(args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a shell command.

        Args:
            args: Dictionary containing command arguments

        Returns:
            Dictionary with execution result
        """
        command = args["command"]
        timeout = args.get("timeout", 30)
        cwd = args.get("cwd", "")

        # Security validation
        from ..pc_utils.security import validate_command

        is_valid, validation_msg = validate_command(command)
        if not is_valid:
            return {
                "success": False,
                "error": f"Command validation failed: {validation_msg}",
                "command": command,
            }

        try:
            result = pc_manager.execute_command(command, timeout=timeout, cwd=cwd)
            return {
                "success": result["success"],
                "return_code": result["return_code"],
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "command": command,
            }
        except Exception as e:
            return {"success": False, "error": str(e), "command": command}

    return Tool(
        name="execute_command",
        description="Execute a shell command in the PC",
        parameters={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds",
                    "default": 30,
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory for the command",
                    "default": "",
                },
            },
            "required": ["command"],
        },
        execute_func=execute_command,
        category="command",
        dangerous=True,  # Command execution is dangerous
        allowed_by_default=False,
    )


def register_command_tools(registry, pc_manager: "PCManager"):
    """Register command tools with the registry.

    Args:
        registry: ToolRegistry instance
        pc_manager: PCManager instance
    """
    registry.register_tool(create_execute_command_tool(pc_manager))
