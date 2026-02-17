"""Tool routes for PC API.

Provides tool listing and OpenAI-compatible endpoints.
"""

import logging

from flask import Blueprint, current_app, jsonify, request

logger = logging.getLogger(__name__)

bp = Blueprint("tools", __name__)


def _get_tool_manager():
    """Get tool manager from app context."""
    return current_app.tool_manager


@bp.route("/tools", methods=["GET"])
def list_tools():
    """List available tools in the PC.

    Returns:
        JSON with available tools and endpoints
    """
    tools = {
        "command_execution": {
            "endpoint": "/execute",
            "method": "POST",
            "description": "Execute shell commands",
        },
        "file_management": {
            "endpoint": "/files",
            "methods": ["GET", "POST", "PUT", "DELETE"],
            "description": "Manage files in /pc/files",
        },
        "memory": {
            "endpoint": "/memory",
            "methods": ["GET", "POST"],
            "description": "Key-value storage across sessions",
        },
    }
    return jsonify(tools)


@bp.route("/v1/tools", methods=["GET"])
def list_openai_tools():
    """List tools in OpenAI-compatible format.

    Query params:
        include_dangerous: Whether to include dangerous tools (default: false)
        allowed_only: Whether to only return allowed tools (default: true)

    Returns:
        OpenAI-compatible tool definitions
    """
    tool_manager = _get_tool_manager()

    include_dangerous = request.args.get("include_dangerous", "false").lower() == "true"
    allowed_only = request.args.get("allowed_only", "true").lower() == "true"

    result = tool_manager.list_tools_openai_format(
        include_dangerous=include_dangerous, allowed_only=allowed_only
    )

    return jsonify(result)


@bp.route("/v1/chat/completions", methods=["POST"])
def openai_chat_completions():
    """OpenAI-compatible chat completions endpoint with tool support.

    This endpoint mimics the OpenAI API format for compatibility with
    clients expecting OpenAI-style responses.

    Request body:
        model: Model name (placeholder, not used)
        messages: List of message objects
        tools: Optional list of available tools

    Returns:
        OpenAI-compatible response with tool calls or content
    """
    tool_manager = _get_tool_manager()
    request.headers.get("X-User", "unknown")

    data = request.get_json() or {}
    messages = data.get("messages", [])

    # Check if this is a tool call request
    if "tool_calls" in str(messages):
        # Extract tool calls from the last message
        last_message = messages[-1] if messages else {}
        tool_calls = last_message.get("tool_calls", [])

        if tool_calls:
            # Execute tool calls
            tool_results = []
            for tool_call in tool_calls:
                tool_name = tool_call.get("function", {}).get("name", "")
                tool_id = tool_call.get("id", "")

                try:
                    arguments_str = tool_call.get("function", {}).get("arguments", "{}")
                    import json

                    arguments = json.loads(arguments_str)
                except json.JSONDecodeError:
                    arguments = {}

                # Execute tool
                result = tool_manager.execute_tool(tool_name, arguments)

                tool_results.append(
                    {
                        "tool_call_id": tool_id,
                        "role": "tool",
                        "name": tool_name,
                        "content": json.dumps(result),
                    }
                )

            # Return OpenAI-compatible response
            return jsonify(
                {
                    "id": "chatcmpl-tool-call",
                    "object": "chat.completion",
                    "created": 0,
                    "model": data.get("model", "gpt-4"),
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": None,
                                "tool_calls": tool_calls,
                            },
                            "finish_reason": "tool_calls",
                        }
                    ],
                    "tool_results": tool_results,
                }
            )

    # Regular response (no tool calls)
    return jsonify(
        {
            "id": "chatcmpl-regular",
            "object": "chat.completion",
            "created": 0,
            "model": data.get("model", "gpt-4"),
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Tool execution completed",
                    },
                    "finish_reason": "stop",
                }
            ],
        }
    )
