"""Key management and audit log routes for PC API.

Provides API key rotation and security audit log retrieval.
"""

import logging

from flask import Blueprint, current_app, jsonify, request

logger = logging.getLogger(__name__)

bp = Blueprint("keys", __name__)


def _get_auth_manager():
    """Get auth manager from app context.

    Returns:
        AuthManager instance from current app
    """
    return current_app.auth_manager


@bp.route("/keys", methods=["GET"])
def list_keys():
    """List valid API keys (without revealing full keys).

    Returns masked key identifiers for security.

    Returns:
        JSON with keys array, count, and max_keys limit
    """
    auth_manager = _get_auth_manager()
    valid_keys = auth_manager.load_valid_keys()

    if not valid_keys:
        return jsonify({"keys": [], "count": 0})

    # Show only first 8 chars of each key for identification
    masked_keys = [f"{key[:8]}..." if len(key) > 8 else "***" for key in valid_keys]
    return jsonify({"keys": masked_keys, "count": len(valid_keys), "max_keys": 5})


@bp.route("/keys/rotate", methods=["POST"])
def rotate_key():
    """Generate a new API key and add to valid keys.

    The new key is returned only once in the response.
    Clients must save it immediately.

    Returns:
        JSON with new_key (shown only once), total_keys count, and note
    """
    auth_manager = _get_auth_manager()
    valid_keys = auth_manager.load_valid_keys()

    # Generate new key
    new_key = auth_manager.generate_new_key(32)

    # Add to front of list (most recent first)
    valid_keys.insert(0, new_key)

    # Keep only last 5 keys (prevent unlimited growth)
    MAX_KEYS = 5
    if len(valid_keys) > MAX_KEYS:
        removed_keys = valid_keys[MAX_KEYS:]
        valid_keys = valid_keys[:MAX_KEYS]
        logger.info(f"Removed {len(removed_keys)} old keys")

    # Save updated keys
    auth_manager.save_valid_keys(valid_keys)

    # Log audit event
    user = request.headers.get("X-User", "unknown")
    auth_manager.log_audit_event(
        event_type="key_rotated",
        user=user,
        command="",
        success=True,
        details={"new_key_prefix": new_key[:8], "total_keys": len(valid_keys)},
    )

    # Return the new key (only this time)
    return jsonify(
        {
            "success": True,
            "new_key": new_key,
            "total_keys": len(valid_keys),
            "note": "Save this key immediately. It will not be shown again.",
        }
    )


@bp.route("/audit-logs", methods=["GET"])
def get_audit_logs():
    """Retrieve audit logs with optional limit.

    Query params:
        limit: Maximum number of logs to return (default: 50, max: 1000)

    Args:
        limit: Maximum number of logs to return

    Returns:
        JSON with logs array, count, and limit
    """
    auth_manager = _get_auth_manager()

    limit = request.args.get("limit", default=50, type=int)
    if limit <= 0 or limit > 1000:
        limit = 50

    try:
        logs = auth_manager.get_audit_logs(limit)

        return jsonify({"logs": logs, "count": len(logs), "limit": limit})
    except Exception as e:
        logger.error(f"Failed to retrieve audit logs: {e}")
        return jsonify({"error": str(e)}), 500
