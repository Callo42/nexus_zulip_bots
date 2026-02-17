"""System information tools.

Tools for getting system information and checking disk space.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from ..pc_manager import PCManager


def create_get_system_info_tool(pc_manager: "PCManager"):
    """Create get_system_info tool.

    Args:
        pc_manager: PCManager instance for system operations

    Returns:
        Tool instance for get_system_info
    """
    from .base import Tool

    def execute_get_system_info(args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute get_system_info tool.

        Args:
            args: Empty dictionary (no arguments)

        Returns:
            Dictionary with system information
        """
        try:
            import platform

            import psutil

            info = {
                "system": platform.system(),
                "release": platform.release(),
                "processor": platform.processor(),
                "cpu_count": psutil.cpu_count(),
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_total": psutil.virtual_memory().total,
                "memory_available": psutil.virtual_memory().available,
                "memory_percent": psutil.virtual_memory().percent,
                "disk_usage": {},
            }

            # Get disk usage for PC root
            try:
                disk = psutil.disk_usage(str(pc_manager.root))
                info["disk_usage"]["pc_root"] = {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "percent": disk.percent,
                }
            except Exception:
                pass  # nosec B110

            return {"success": True, "system_info": info}
        except Exception as e:
            # Fallback if psutil not available
            import platform

            return {
                "success": True,
                "system_info": {
                    "system": platform.system(),
                    "release": platform.release(),
                    "processor": platform.processor(),
                    "note": "Limited system info (psutil not available)",
                    "error": str(e) if "e" in locals() else "Unknown",
                },
            }

    return Tool(
        name="get_system_info",
        description="Get system information including CPU, memory, and disk usage",
        parameters={
            "type": "object",
            "properties": {},
        },
        execute_func=execute_get_system_info,
        category="system",
        dangerous=False,
        allowed_by_default=True,
    )


def create_check_disk_space_tool(pc_manager: "PCManager"):
    """Create check_disk_space tool.

    Args:
        pc_manager: PCManager instance for system operations

    Returns:
        Tool instance for check_disk_space
    """
    from .base import Tool

    def execute_check_disk_space(args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute check_disk_space tool.

        Args:
            args: Dictionary containing optional path parameter

        Returns:
            Dictionary with disk space information
        """
        path = args.get("path", ".")

        try:
            import psutil

            # Resolve path relative to files dir
            target_path = Path(pc_manager.files_dir) / path
            if not target_path.exists():
                target_path = pc_manager.files_dir

            disk = psutil.disk_usage(str(target_path))

            return {
                "success": True,
                "path": str(target_path),
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "percent": disk.percent,
                "human_readable": {
                    "total": f"{disk.total / (1024**3):.2f} GB",
                    "used": f"{disk.used / (1024**3):.2f} GB",
                    "free": f"{disk.free / (1024**3):.2f} GB",
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e), "path": path}

    return Tool(
        name="check_disk_space",
        description="Check disk space usage for a path",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to check (relative to PC root)",
                    "default": ".",
                },
            },
        },
        execute_func=execute_check_disk_space,
        category="system",
        dangerous=False,
        allowed_by_default=True,
    )


def register_system_tools(registry, pc_manager: "PCManager"):
    """Register system tools with the registry.

    Args:
        registry: ToolRegistry instance
        pc_manager: PCManager instance
    """
    registry.register_tool(create_get_system_info_tool(pc_manager))
    registry.register_tool(create_check_disk_space_tool(pc_manager))
