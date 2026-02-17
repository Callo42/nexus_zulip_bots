"""Command execution routes for PC API.

Provides shell command execution with security validation and audit logging.
"""

import logging
import subprocess  # nosec B404

from flask import Blueprint, current_app, jsonify, request

from ..pc_utils.security import filter_sensitive_content, validate_command

logger = logging.getLogger(__name__)

bp = Blueprint("commands", __name__)


def _get_pc_manager():
    """Get PC manager from app context."""
    return current_app.pc_manager


def _get_auth_manager():
    """Get auth manager from app context."""
    return current_app.auth_manager


@bp.route("/execute", methods=["POST"])
def execute_command():
    """Execute a shell command.

    Request body:
        command: Command string to execute (required)
        timeout: Timeout in seconds (default: 30)
        cwd: Working directory (default: /pc/files)

    Headers:
        X-User: User identifier for audit logging

    Returns:
        JSON with execution results
    """
    pc_manager = _get_pc_manager()
    auth_manager = _get_auth_manager()

    data = request.get_json()
    if not data or "command" not in data:
        return jsonify({"error": "Missing command"}), 400

    command = data["command"]
    timeout = data.get("timeout", 30)
    cwd = data.get("cwd", str(pc_manager.files_dir))

    # Security: validate command using enhanced security functions
    is_valid, validation_msg = validate_command(command)
    if not is_valid:
        auth_manager.log_audit_event(
            event_type="command_rejected",
            user="unknown",
            command=command,
            success=False,
            details={"reason": validation_msg},
        )
        return jsonify({"error": f"Command validation failed: {validation_msg}"}), 400

    # Change to working directory if exists
    if not pc_manager.exists(cwd):
        cwd = str(pc_manager.files_dir)

    # Get user from headers (if provided)
    user = request.headers.get("X-User", "unknown")

    logger.info(f"Executing command: {filter_sensitive_content(command)} in {cwd}")
    auth_manager.log_audit_event(
        event_type="command_execution_started", user=user, command=command, success=True
    )

    try:
        # Execute command with timeout
        process = subprocess.run(
            command,
            shell=True,  # nosec B602
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        response = {
            "success": process.returncode == 0,
            "return_code": process.returncode,
            "stdout": process.stdout,
            "stderr": process.stderr,
            "command": command,
        }

        logger.info(f"Command executed with return code {process.returncode}")
        # Log successful command execution
        auth_manager.log_audit_event(
            event_type="command_execution_completed",
            user=user,
            command=command,
            success=process.returncode == 0,
            details={"return_code": process.returncode},
        )
        return jsonify(response)

    except subprocess.TimeoutExpired:
        logger.warning(f"Command timed out: {command}")
        auth_manager.log_audit_event(
            event_type="command_execution_timeout",
            user=user,
            command=command,
            success=False,
            details={"timeout": timeout},
        )
        return jsonify({"error": "Command timed out", "command": command}), 408
    except Exception as e:
        logger.error(f"Command execution failed: {e}")
        auth_manager.log_audit_event(
            event_type="command_execution_failed",
            user=user,
            command=command,
            success=False,
            details={"error": str(e)},
        )
        return jsonify({"error": str(e), "command": command}), 500
