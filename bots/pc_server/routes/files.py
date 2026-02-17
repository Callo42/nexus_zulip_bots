"""File management routes for PC API.

Provides file CRUD operations with security controls and audit logging.
"""

import logging
import shutil
import time
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

logger = logging.getLogger(__name__)

bp = Blueprint("files", __name__)


def _get_pc_manager():
    """Get PC manager from app context."""
    return current_app.pc_manager


def _get_auth_manager():
    """Get auth manager from app context."""
    return current_app.auth_manager


def _resolve_path(filepath: str, files_dir: Path):
    """Resolve and validate file path within FILES_DIR.

    Args:
        filepath: Relative file path
        files_dir: Base files directory

    Returns:
        Resolved Path object

    Raises:
        ValueError: If path traversal detected
    """
    target_path = (files_dir / filepath).resolve()

    # Ensure path is within FILES_DIR
    if files_dir not in target_path.parents and target_path != files_dir:
        raise ValueError(f"Path traversal not allowed: {filepath}")

    return target_path


@bp.route("/files", methods=["GET", "POST"])
@bp.route("/files/<path:filepath>", methods=["GET", "PUT", "DELETE"])
def manage_files(filepath: str = ""):
    """Manage files in the PC's file system.

    Routes:
        GET /files - List all files
        GET /files/<path> - Read file content
        PUT /files/<path> - Create or update file
        DELETE /files/<path> - Delete file
        POST /files - Create new file with auto-generated name

    Args:
        filepath: File path (optional for list/create)

    Returns:
        JSON response with file data or error
    """
    pc_manager = _get_pc_manager()
    auth_manager = _get_auth_manager()
    files_dir = pc_manager.files_dir

    # Get user from headers
    user = request.headers.get("X-User", "unknown")

    # Resolve path if provided
    if filepath:
        try:
            target_path = _resolve_path(filepath, files_dir)
        except ValueError:
            auth_manager.log_audit_event(
                event_type="path_traversal_attempt",
                user=user,
                command="",
                success=False,
                details={"path": filepath},
            )
            return jsonify({"error": "Path traversal not allowed"}), 403
        except Exception as e:
            auth_manager.log_audit_event(
                event_type="invalid_path",
                user=user,
                command="",
                success=False,
                details={"path": filepath, "error": str(e)},
            )
            return jsonify({"error": f"Invalid path: {e}"}), 400

    if request.method == "GET":
        if not filepath:
            # List files in directory
            return _list_files(files_dir, auth_manager, user)

        # Get file content
        return _read_file(target_path, filepath, auth_manager, user)

    elif request.method == "PUT":
        # Create or update file
        return _write_file(target_path, filepath, auth_manager, user)

    elif request.method == "DELETE":
        # Delete file
        return _delete_file(target_path, filepath, auth_manager, user)

    else:
        # POST to /files - create new file with auto-generated name
        return _create_file(files_dir, auth_manager, user)


def _list_files(files_dir: Path, auth_manager, user: str):
    """List files in directory."""
    try:
        files = []
        for item in files_dir.iterdir():
            files.append(
                {
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else 0,
                    "modified": item.stat().st_mtime,
                }
            )

        auth_manager.log_audit_event(
            event_type="file_list",
            user=user,
            command="",
            success=True,
            details={"count": len(files)},
        )
        return jsonify({"files": files})

    except Exception as e:
        logger.error(f"Failed to list files: {e}")
        auth_manager.log_audit_event(
            event_type="file_list_error",
            user=user,
            command="",
            success=False,
            details={"error": str(e)},
        )
        return jsonify({"error": str(e)}), 500


def _read_file(target_path: Path, filepath: str, auth_manager, user: str):
    """Read file content."""
    if not target_path.exists():
        auth_manager.log_audit_event(
            event_type="file_not_found",
            user=user,
            command="",
            success=False,
            details={"path": filepath},
        )
        return jsonify({"error": "File not found"}), 404

    if target_path.is_dir():
        auth_manager.log_audit_event(
            event_type="path_is_directory",
            user=user,
            command="",
            success=False,
            details={"path": filepath},
        )
        return jsonify({"error": "Path is a directory"}), 400

    try:
        with open(target_path, "r") as f:
            content = f.read()

        auth_manager.log_audit_event(
            event_type="file_read",
            user=user,
            command="",
            success=True,
            details={"path": filepath, "size": target_path.stat().st_size},
        )
        return jsonify({"path": filepath, "content": content, "size": target_path.stat().st_size})

    except Exception as e:
        logger.error(f"Failed to read file: {e}")
        auth_manager.log_audit_event(
            event_type="file_read_error",
            user=user,
            command="",
            success=False,
            details={"path": filepath, "error": str(e)},
        )
        return jsonify({"error": str(e)}), 500


def _write_file(target_path: Path, filepath: str, auth_manager, user: str):
    """Create or update file."""
    data = request.get_json()
    if not data or "content" not in data:
        auth_manager.log_audit_event(
            event_type="missing_content",
            user=user,
            command="",
            success=False,
            details={"path": filepath},
        )
        return jsonify({"error": "Missing content"}), 400

    try:
        # Ensure parent directory exists
        target_path.parent.mkdir(parents=True, exist_ok=True)

        with open(target_path, "w") as f:
            f.write(data["content"])

        logger.info(f"File saved: {filepath}")
        auth_manager.log_audit_event(
            event_type="file_write",
            user=user,
            command="",
            success=True,
            details={"path": filepath, "size": target_path.stat().st_size},
        )
        return jsonify({"success": True, "path": filepath, "size": target_path.stat().st_size})

    except Exception as e:
        logger.error(f"Failed to write file: {e}")
        auth_manager.log_audit_event(
            event_type="file_write_error",
            user=user,
            command="",
            success=False,
            details={"path": filepath, "error": str(e)},
        )
        return jsonify({"error": str(e)}), 500


def _delete_file(target_path: Path, filepath: str, auth_manager, user: str):
    """Delete file or directory."""
    if not target_path.exists():
        auth_manager.log_audit_event(
            event_type="file_not_found",
            user=user,
            command="",
            success=False,
            details={"path": filepath},
        )
        return jsonify({"error": "File not found"}), 404

    try:
        if target_path.is_dir():
            shutil.rmtree(target_path)
            operation_type = "directory_delete"
        else:
            target_path.unlink()
            operation_type = "file_delete"

        logger.info(f"File deleted: {filepath}")
        auth_manager.log_audit_event(
            event_type=operation_type,
            user=user,
            command="",
            success=True,
            details={"path": filepath},
        )
        return jsonify({"success": True, "path": filepath})

    except Exception as e:
        logger.error(f"Failed to delete file: {e}")
        auth_manager.log_audit_event(
            event_type="file_delete_error",
            user=user,
            command="",
            success=False,
            details={"path": filepath, "error": str(e)},
        )
        return jsonify({"error": str(e)}), 500


def _create_file(files_dir: Path, auth_manager, user: str):
    """Create new file with auto-generated name."""
    data = request.get_json()
    if not data or "content" not in data:
        auth_manager.log_audit_event(
            event_type="missing_content",
            user=user,
            command="",
            success=False,
            details={"path": ""},
        )
        return jsonify({"error": "Missing content"}), 400

    filename = data.get("filename", f"file_{int(time.time())}.txt")
    target_path = files_dir / filename

    try:
        with open(target_path, "w") as f:
            f.write(data["content"])

        auth_manager.log_audit_event(
            event_type="file_create",
            user=user,
            command="",
            success=True,
            details={"path": filename, "size": target_path.stat().st_size},
        )
        return jsonify({"success": True, "path": filename, "size": target_path.stat().st_size})

    except Exception as e:
        logger.error(f"Failed to create file: {e}")
        auth_manager.log_audit_event(
            event_type="file_create_error",
            user=user,
            command="",
            success=False,
            details={"path": filename, "error": str(e)},
        )
        return jsonify({"error": str(e)}), 500
