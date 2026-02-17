"""File operation tools.

Tools for listing, reading, writing, and deleting files in the PC.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from ..pc_manager import PCManager


def create_list_files_tool(pc_manager: "PCManager"):
    """Create list_files tool.

    Args:
        pc_manager: PCManager instance for file operations

    Returns:
        Tool instance for list_files
    """
    from .base import Tool

    def execute_list_files(args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute list_files tool.

        Args:
            args: Dictionary containing path and recursive options

        Returns:
            Dictionary with file listing result
        """
        path = args.get("path", "")
        recursive = args.get("recursive", False)

        try:
            files = pc_manager.list_files(path)

            # If recursive, we need to implement recursive listing
            if recursive and path == "":
                # Simple recursive implementation using rglob
                all_files = []
                base_path = Path(pc_manager.files_dir)
                for file_path in base_path.rglob("*"):
                    if file_path.is_file():
                        rel_path = file_path.relative_to(base_path)
                        all_files.append(
                            {
                                "name": str(rel_path),
                                "type": "file",
                                "size": file_path.stat().st_size,
                                "modified": file_path.stat().st_mtime,
                            }
                        )
                files = all_files

            return {"success": True, "files": files, "count": len(files), "path": path}
        except Exception as e:
            return {"success": False, "error": str(e), "path": path}

    return Tool(
        name="list_files",
        description="List files in the PC's file system",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to list (relative to PC root)",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Whether to list files recursively",
                    "default": False,
                },
            },
        },
        execute_func=execute_list_files,
        category="file",
        dangerous=False,
        allowed_by_default=True,
    )


def create_read_file_tool(pc_manager: "PCManager"):
    """Create read_file tool.

    Args:
        pc_manager: PCManager instance for file operations

    Returns:
        Tool instance for read_file
    """
    from .base import Tool

    def execute_read_file(args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute read_file tool.

        Args:
            args: Dictionary containing file path

        Returns:
            Dictionary with file content or error
        """
        path = args["path"]

        try:
            content = pc_manager.read_file(path)
            if content is None:
                return {
                    "success": False,
                    "error": f"File not found or cannot read: {path}",
                    "path": path,
                }

            # Limit content size for response
            max_size = 100000  # 100KB
            if len(content) > max_size:
                content = (
                    content[:max_size]
                    + f"\n\n[Content truncated, total size: {len(content)} bytes]"
                )

            return {
                "success": True,
                "content": content,
                "size": len(content),
                "path": path,
            }
        except Exception as e:
            return {"success": False, "error": str(e), "path": path}

    return Tool(
        name="read_file",
        description="Read the content of a file",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file (relative to PC root)",
                },
            },
            "required": ["path"],
        },
        execute_func=execute_read_file,
        category="file",
        dangerous=False,
        allowed_by_default=True,
    )


def create_write_file_tool(pc_manager: "PCManager"):
    """Create write_file tool.

    Args:
        pc_manager: PCManager instance for file operations

    Returns:
        Tool instance for write_file
    """
    from .base import Tool

    def execute_write_file(args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute write_file tool.

        Args:
            args: Dictionary containing path, content, and append options

        Returns:
            Dictionary with write result
        """
        path = args["path"]
        content = args["content"]
        append = args.get("append", False)

        try:
            if append:
                # Read existing content
                existing = pc_manager.read_file(path) or ""
                content = existing + content

            success = pc_manager.write_file(path, content)
            if not success:
                return {
                    "success": False,
                    "error": f"Failed to write file: {path}",
                    "path": path,
                }

            # Get file size
            file_path = Path(pc_manager.files_dir) / path
            size = file_path.stat().st_size if file_path.exists() else 0

            return {
                "success": True,
                "path": path,
                "size": size,
                "message": "File written successfully",
            }
        except Exception as e:
            return {"success": False, "error": str(e), "path": path}

    return Tool(
        name="write_file",
        description="Write content to a file (creates or overwrites)",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file (relative to PC root)",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file",
                },
                "append": {
                    "type": "boolean",
                    "description": "Whether to append to existing content",
                    "default": False,
                },
            },
            "required": ["path", "content"],
        },
        execute_func=execute_write_file,
        category="file",
        dangerous=True,  # Write operations are dangerous
        allowed_by_default=False,
    )


def create_delete_file_tool(pc_manager: "PCManager"):
    """Create delete_file tool.

    Args:
        pc_manager: PCManager instance for file operations

    Returns:
        Tool instance for delete_file
    """
    from .base import Tool

    def execute_delete_file(args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute delete_file tool.

        Args:
            args: Dictionary containing file path

        Returns:
            Dictionary with delete result
        """
        path = args["path"]
        # TODO: recursive parameter is accepted but not yet implemented
        # NOTE: args.get("recursive", False) is intentionally unused

        # Additional security check for dangerous delete operations
        dangerous_patterns = ["/", "..", "*.", ".*"]
        for pattern in dangerous_patterns:
            if pattern in path:
                return {
                    "success": False,
                    "error": f"Potentially dangerous path pattern: {pattern}",
                    "path": path,
                }

        try:
            success = pc_manager.delete_file(path)
            if not success:
                return {
                    "success": False,
                    "error": f"Failed to delete file: {path}",
                    "path": path,
                }

            return {
                "success": True,
                "path": path,
                "message": "File deleted successfully",
            }
        except Exception as e:
            return {"success": False, "error": str(e), "path": path}

    return Tool(
        name="delete_file",
        description="Delete a file from the PC",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to delete",
                },
            },
            "required": ["path"],
        },
        execute_func=execute_delete_file,
        category="file",
        dangerous=True,  # Delete operations are dangerous
        allowed_by_default=False,
    )


def register_file_tools(registry, pc_manager: "PCManager"):
    """Register all file tools with the registry.

    Args:
        registry: ToolRegistry instance
        pc_manager: PCManager instance
    """
    registry.register_tool(create_list_files_tool(pc_manager))
    registry.register_tool(create_read_file_tool(pc_manager))
    registry.register_tool(create_write_file_tool(pc_manager))
    registry.register_tool(create_delete_file_tool(pc_manager))
