"""History management routes for PC API.

Provides conversation history storage for streams and private DMs.
"""

import logging
from typing import Any, Dict

from flask import Blueprint, current_app, jsonify, request

logger = logging.getLogger(__name__)

bp = Blueprint("history", __name__)


def _get_history_manager():
    """Get history manager from app context.

    Returns:
        HistoryManager instance from current app
    """
    return current_app.history_manager


def _get_auth_manager():
    """Get auth manager from app context.

    Returns:
        AuthManager instance from current app
    """
    return current_app.auth_manager


# ============================================================================
# Stream History (per topic)
# ============================================================================


def _handle_stream_post(
    history_manager, stream_id: str, topic: str, user: str
) -> tuple[Dict[str, Any], int]:
    """Handle POST request to add stream message.

    Args:
        history_manager: History manager instance
        stream_id: Zulip stream ID or name
        topic: Topic name
        user: User identifier from header

    Returns:
        Tuple of (response dict, status code)
    """
    data = request.get_json()
    if not data:
        return {"error": "Missing JSON data"}, 400

    role = data.get("role")
    content = data.get("content")
    sender_id = data.get("sender_id") or data.get("sender", user)
    message_id = data.get("message_id")
    config = data.get("config")
    sender_full_name = data.get("sender_full_name")

    if not role or not content:
        return {"error": "Missing role or content"}, 400

    try:
        result = history_manager.add_stream_message(
            stream_id=stream_id,
            topic=topic,
            role=role,
            content=content,
            sender_id=sender_id,
            message_id=message_id,
            config=config,
            sender_full_name=sender_full_name,
        )
        return result, 200
    except Exception as e:
        logger.error(f"Failed to add stream message: {e}", exc_info=True)
        return {"error": str(e)}, 500


def _handle_stream_get(history_manager, stream_id: str, topic: str) -> tuple[Dict[str, Any], int]:
    """Handle GET request to retrieve stream messages.

    Args:
        history_manager: History manager instance
        stream_id: Zulip stream ID or name
        topic: Topic name

    Returns:
        Tuple of (response dict, status code)
    """
    limit = request.args.get("limit", default=None, type=int)
    try:
        messages = history_manager.get_stream_messages(
            stream_id=stream_id, topic=topic, limit=limit
        )
        return {"messages": messages}, 200
    except Exception as e:
        logger.error(f"Failed to get stream messages: {e}", exc_info=True)
        return {"error": str(e)}, 500


def _handle_stream_cleanup(
    history_manager, stream_id: str, topic: str
) -> tuple[Dict[str, Any], int]:
    """Handle POST request to cleanup stream history.

    Args:
        history_manager: History manager instance
        stream_id: Zulip stream ID or name
        topic: Topic name

    Returns:
        Tuple of (response dict, status code)
    """
    force = request.args.get("force", default=False, type=bool)
    try:
        result = history_manager.cleanup_stream_history(
            stream_id=stream_id, topic=topic, force=force
        )
        return result, 200
    except Exception as e:
        logger.error(f"Failed to cleanup stream history: {e}", exc_info=True)
        return {"error": str(e)}, 500


def _handle_stream_delete(
    history_manager, stream_id: str, topic: str
) -> tuple[Dict[str, Any], int]:
    """Handle DELETE request to delete stream history.

    Args:
        history_manager: History manager instance
        stream_id: Zulip stream ID or name
        topic: Topic name

    Returns:
        Tuple of (response dict, status code)
    """
    try:
        success = history_manager.delete_stream_history(stream_id, topic)
        if success:
            return {
                "success": True,
                "message": f"History deleted for {stream_id}/{topic}",
            }, 200
        return {
            "success": False,
            "message": "History not found or deletion failed",
        }, 404
    except Exception as e:
        logger.error(f"Failed to delete stream history: {e}", exc_info=True)
        return {"error": str(e)}, 500


@bp.route("/history/streams/<stream_id>/topics/<topic>", methods=["POST", "GET", "DELETE"])
@bp.route("/history/streams/<stream_id>/topics/<topic>/cleanup", methods=["POST"])
def manage_stream_history(stream_id: str, topic: str):
    """Manage stream/topic conversation history.

    Supports POST (add message), GET (retrieve messages),
    and DELETE (clear history for stream/topic).

    Args:
        stream_id: Zulip stream ID or name
        topic: Topic name

    Returns:
        JSON response with operation result

    Routes:
        POST /history/streams/<id>/topics/<topic> - Add message
        GET /history/streams/<id>/topics/<topic> - Get messages
        DELETE /history/streams/<id>/topics/<topic> - Delete all messages
        POST /history/streams/<id>/topics/<topic>/cleanup - Cleanup old messages
    """
    history_manager = _get_history_manager()
    user = request.headers.get("X-User", "unknown")

    is_cleanup = request.method == "POST" and "cleanup" in request.path
    is_regular_post = request.method == "POST" and not is_cleanup

    if is_regular_post:
        result, status = _handle_stream_post(history_manager, stream_id, topic, user)
        return jsonify(result), status

    if request.method == "GET":
        result, status = _handle_stream_get(history_manager, stream_id, topic)
        return jsonify(result), status

    if is_cleanup:
        result, status = _handle_stream_cleanup(history_manager, stream_id, topic)
        return jsonify(result), status

    if request.method == "DELETE":
        result, status = _handle_stream_delete(history_manager, stream_id, topic)
        return jsonify(result), status

    return jsonify({"error": "Method not allowed"}), 405


@bp.route("/history/streams/<stream_id>", methods=["GET", "DELETE"])
def manage_stream_all_topics(stream_id: str):
    """Manage all history for a stream (all topics).

    Args:
        stream_id: Zulip stream ID or name

    Returns:
        JSON with stream topics or deletion result

    Routes:
        GET /history/streams/<id> - List all topics
        DELETE /history/streams/<id> - Delete entire stream history
    """
    history_manager = _get_history_manager()

    if request.method == "GET":
        try:
            topics = history_manager.list_stream_topics(stream_id)
            return jsonify({"stream_id": stream_id, "topics": topics, "total_topics": len(topics)})
        except Exception as e:
            logger.error(f"Failed to list stream topics: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    elif request.method == "DELETE":
        try:
            success = history_manager.delete_stream_history(stream_id)
            if success:
                return jsonify(
                    {
                        "success": True,
                        "message": f"All history deleted for stream {stream_id}",
                    }
                )
            else:
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": "Stream history not found or deletion failed",
                        }
                    ),
                    404,
                )
        except Exception as e:
            logger.error(f"Failed to delete stream history: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500


@bp.route("/history/streams/<stream_id>/topics/<topic>/info", methods=["GET"])
def get_stream_history_info(stream_id: str, topic: str):
    """Get history info for a stream/topic.

    Args:
        stream_id: Zulip stream ID or name
        topic: Topic name

    Returns:
        JSON with history metadata (message count, tokens, etc.)
    """
    history_manager = _get_history_manager()
    try:
        info = history_manager.get_stream_history_info(stream_id, topic)
        return jsonify(info)
    except Exception as e:
        logger.error(f"Failed to get stream history info: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


# ============================================================================
# Private History (per user)
# ============================================================================


def _handle_private_post(history_manager, user_email: str, user: str) -> tuple[Dict[str, Any], int]:
    """Handle POST request to add private message.

    Args:
        history_manager: History manager instance
        user_email: User email
        user: User identifier from header

    Returns:
        Tuple of (response dict, status code)
    """
    data = request.get_json()
    if not data:
        return {"error": "Missing JSON data"}, 400

    role = data.get("role")
    content = data.get("content")
    sender_id = data.get("sender_id") or data.get("sender", user)
    message_id = data.get("message_id")
    config = data.get("config")
    sender_full_name = data.get("sender_full_name")

    if not role or not content:
        return {"error": "Missing role or content"}, 400

    try:
        result = history_manager.add_private_message(
            user_email=user_email,
            role=role,
            content=content,
            sender_id=sender_id,
            message_id=message_id,
            config=config,
            sender_full_name=sender_full_name,
        )
        return result, 200
    except Exception as e:
        logger.error(f"Failed to add private message: {e}", exc_info=True)
        return {"error": str(e)}, 500


def _handle_private_get(history_manager, user_email: str) -> tuple[Dict[str, Any], int]:
    """Handle GET request to retrieve private messages.

    Args:
        history_manager: History manager instance
        user_email: User email

    Returns:
        Tuple of (response dict, status code)
    """
    limit = request.args.get("limit", default=None, type=int)
    try:
        messages = history_manager.get_private_messages(user_email=user_email, limit=limit)
        return {"messages": messages}, 200
    except Exception as e:
        logger.error(f"Failed to get private messages: {e}", exc_info=True)
        return {"error": str(e)}, 500


def _handle_private_cleanup(history_manager, user_email: str) -> tuple[Dict[str, Any], int]:
    """Handle POST request to cleanup private history.

    Args:
        history_manager: History manager instance
        user_email: User email

    Returns:
        Tuple of (response dict, status code)
    """
    force = request.args.get("force", default=False, type=bool)
    try:
        result = history_manager.cleanup_private_history(user_email=user_email, force=force)
        return result, 200
    except Exception as e:
        logger.error(f"Failed to cleanup private history: {e}", exc_info=True)
        return {"error": str(e)}, 500


def _handle_private_delete(history_manager, user_email: str) -> tuple[Dict[str, Any], int]:
    """Handle DELETE request to delete private history.

    Args:
        history_manager: History manager instance
        user_email: User email

    Returns:
        Tuple of (response dict, status code)
    """
    try:
        success = history_manager.delete_private_history(user_email)
        if success:
            return {
                "success": True,
                "message": f"Private history deleted for {user_email}",
            }, 200
        return {
            "success": False,
            "message": "Private history not found or deletion failed",
        }, 404
    except Exception as e:
        logger.error(f"Failed to delete private history: {e}", exc_info=True)
        return {"error": str(e)}, 500


@bp.route("/history/private/<user_email>", methods=["POST", "GET", "DELETE"])
@bp.route("/history/private/<user_email>/cleanup", methods=["POST"])
def manage_private_history(user_email: str):
    """Manage private DM conversation history.

    Args:
        user_email: User email

    Returns:
        JSON with operation result or messages

    Routes:
        POST /history/private/<email> - Add message
        GET /history/private/<email> - Get messages
        DELETE /history/private/<email> - Delete all messages
        POST /history/private/<email>/cleanup - Cleanup old messages
    """
    history_manager = _get_history_manager()
    user = request.headers.get("X-User", "unknown")

    is_cleanup = request.method == "POST" and "cleanup" in request.path
    is_regular_post = request.method == "POST" and not is_cleanup

    if is_regular_post:
        result, status = _handle_private_post(history_manager, user_email, user)
        return jsonify(result), status

    if request.method == "GET":
        result, status = _handle_private_get(history_manager, user_email)
        return jsonify(result), status

    if is_cleanup:
        result, status = _handle_private_cleanup(history_manager, user_email)
        return jsonify(result), status

    if request.method == "DELETE":
        result, status = _handle_private_delete(history_manager, user_email)
        return jsonify(result), status

    return jsonify({"error": "Method not allowed"}), 405


@bp.route("/history/private/<user_email>/info", methods=["GET"])
def get_private_history_info(user_email: str):
    """Get history info for a private DM.

    Args:
        user_email: User email

    Returns:
        JSON with history metadata (message count, tokens, etc.)
    """
    history_manager = _get_history_manager()
    try:
        info = history_manager.get_private_history_info(user_email)
        return jsonify(info)
    except Exception as e:
        logger.error(f"Failed to get private history info: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


# ============================================================================
# History Statistics
# ============================================================================


@bp.route("/history/stats", methods=["GET"])
def get_history_stats():
    """Get storage statistics for observability.

    Returns comprehensive statistics about history usage including:
    - Stream history counts and tokens
    - Private history counts and tokens
    - Top active streams and users

    Returns:
        JSON with storage statistics
    """
    history_manager = _get_history_manager()
    try:
        stats = history_manager.get_storage_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Failed to get history stats: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500
