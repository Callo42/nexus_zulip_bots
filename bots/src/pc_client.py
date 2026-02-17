"""PC Client for interacting with the bot's sidecar PC."""

import json
import logging
import os
import time
import urllib.parse
from typing import Any, Dict, List, Optional, cast

import requests

logger = logging.getLogger(__name__)


class PCClient:
    """Client for PC sidecar API."""

    def __init__(self, api_url: str, api_key: str):
        """Initialize PC client with API URL and key.

        Args:
            api_url: URL of the PC sidecar API
            api_key: API key for authentication
        """
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.headers = {"Content-Type": "application/json", "X-API-Key": api_key}
        logger.info(f"PC Client initialized for {api_url}")

    def _request(
        self,
        method: str,
        endpoint: str,
        extra_headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Make a request to the PC API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            endpoint: API endpoint path.
            extra_headers: Optional additional headers to include.
            **kwargs: Additional arguments for the request.

        Returns:
            Dict containing the JSON response.

        Raises:
            Exception: If the request fails.
        """
        url = f"{self.api_url}{endpoint}"
        try:
            headers = self.headers.copy()
            if extra_headers:
                headers.update(extra_headers)

            response = requests.request(
                method=method, url=url, headers=headers, timeout=30, **kwargs
            )
            response.raise_for_status()
            return cast(Dict[str, Any], response.json())
        except requests.exceptions.RequestException as e:
            logger.error(f"PC API request failed: {e}")
            raise Exception(f"PC API error: {e}")

    def health_check(self) -> bool:
        """Check if PC API is healthy.

        Returns:
            True if PC API is healthy, False otherwise.
        """
        try:
            result = self._request("GET", "/health")
            return result.get("status") == "healthy"
        except Exception:
            return False

    def list_tools(self) -> Dict[str, Any]:
        """List available tools in the PC.

        Returns:
            Dict containing available tools information.
        """
        return self._request("GET", "/tools")

    def execute_command(
        self, command: str, timeout: int = 30, cwd: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute a shell command in the PC.

        Args:
            command: Shell command to execute.
            timeout: Command timeout in seconds.
            cwd: Optional working directory for command execution.

        Returns:
            Dict containing command execution results.
        """
        data = {"command": command, "timeout": timeout}
        if cwd:
            data["cwd"] = cwd
        return self._request("POST", "/execute", json=data)

    def list_files(self) -> List[Dict[str, Any]]:
        """List files in the PC's file system.

        Returns:
            List of dicts containing file information.
        """
        result = self._request("GET", "/files")
        files: List[Dict[str, Any]] = result.get("files", [])
        return files

    def read_file(self, path: str) -> str:
        """Read a file from the PC.

        Args:
            path: Path to the file to read.

        Returns:
            File content as string.
        """
        result = self._request("GET", f"/files/{path}")
        content: str = result.get("content", "")
        return content

    def write_file(self, path: str, content: str) -> Dict[str, Any]:
        """Write content to a file in the PC.

        Args:
            path: Path to the file to write.
            content: Content to write to the file.

        Returns:
            Dict containing write operation result.
        """
        return self._request("PUT", f"/files/{path}", json={"content": content})

    def delete_file(self, path: str) -> Dict[str, Any]:
        """Delete a file from the PC.

        Args:
            path: Path to the file to delete.

        Returns:
            Dict containing delete operation result.
        """
        return self._request("DELETE", f"/files/{path}")

    def create_file(self, filename: str, content: str) -> Dict[str, Any]:
        """Create a new file with auto-generated name.

        Args:
            filename: Name for the new file.
            content: Content to write to the file.

        Returns:
            Dict containing create operation result.
        """
        return self._request("POST", "/files", json={"filename": filename, "content": content})

    def list_keys(self) -> Dict[str, Any]:
        """List valid API keys (masked).

        Returns:
            Dict containing list of masked API keys.
        """
        return self._request("GET", "/keys")

    def rotate_key(self) -> Dict[str, Any]:
        """Generate a new API key and add to valid keys.

        Returns:
            Dict containing new key information.
        """
        return self._request("POST", "/keys/rotate")

    def get_audit_logs(self, limit: int = 50) -> Dict[str, Any]:
        """Retrieve audit logs with optional limit.

        Args:
            limit: Maximum number of audit logs to retrieve.

        Returns:
            Dict containing audit logs.
        """
        return self._request("GET", f"/audit-logs?limit={limit}")

    def run_python_script(self, script: str, timeout: int = 30) -> Dict[str, Any]:
        """Run a Python script in the PC.

        Args:
            script: Python script content to execute.
            timeout: Script execution timeout in seconds.

        Returns:
            Dict containing script execution results.

        Raises:
            Exception: If script execution fails.
        """
        import uuid

        temp_filename = f"temp_script_{uuid.uuid4().hex[:8]}.py"

        try:
            self.write_file(temp_filename, script)
            result = self.execute_command(f"python3 {temp_filename}", timeout=timeout)
            try:
                self.delete_file(temp_filename)
            except Exception:
                pass  # nosec B110

            return result
        except Exception as e:
            try:
                self.delete_file(temp_filename)
            except Exception:
                pass  # nosec B110
            raise e

    # History management methods
    def add_stream_message(
        self,
        stream_id: str,
        topic: str,
        role: str,
        content: str,
        sender_id: str,
        message_id: Optional[int] = None,
        config: Optional[Dict[str, Any]] = None,
        sender_full_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add a message to stream/topic history.

        Args:
            stream_id: Stream identifier.
            topic: Topic name.
            role: Message role (user/assistant).
            content: Message content.
            sender_id: Sender identifier.
            message_id: Optional message ID.
            config: Optional history configuration.
            sender_full_name: Optional sender display name.

        Returns:
            Dict containing operation result.
        """
        data: Dict[str, Any] = {
            "role": role,
            "content": content,
            "sender_id": sender_id,
            "message_id": message_id,
        }
        if config:
            data["config"] = config
        if sender_full_name:
            data["sender_full_name"] = sender_full_name

        return self._request("POST", f"/history/streams/{stream_id}/topics/{topic}", json=data)

    def get_stream_messages(
        self, stream_id: str, topic: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get recent messages from stream/topic history.

        Args:
            stream_id: Stream identifier.
            topic: Topic name.
            limit: Optional maximum number of messages to retrieve.

        Returns:
            List of message dicts.
        """
        params = {}
        if limit:
            params["limit"] = limit

        response = self._request(
            "GET", f"/history/streams/{stream_id}/topics/{topic}", params=params
        )
        messages: List[Dict[str, Any]] = response.get("messages", [])
        return messages

    def add_private_message(
        self,
        user_email: str,
        role: str,
        content: str,
        sender_id: str,
        message_id: Optional[int] = None,
        config: Optional[Dict[str, Any]] = None,
        sender_full_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add a message to private DM history.

        Args:
            user_email: User email address.
            role: Message role (user/assistant).
            content: Message content.
            sender_id: Sender identifier.
            message_id: Optional message ID.
            config: Optional history configuration.
            sender_full_name: Optional sender display name.

        Returns:
            Dict containing operation result.
        """
        data: Dict[str, Any] = {
            "role": role,
            "content": content,
            "sender_id": sender_id,
            "message_id": message_id,
        }
        if config:
            data["config"] = config
        if sender_full_name:
            data["sender_full_name"] = sender_full_name

        return self._request("POST", f"/history/private/{user_email}", json=data)

    def get_private_messages(
        self, user_email: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get recent messages from private DM history.

        Args:
            user_email: User email address.
            limit: Optional maximum number of messages to retrieve.

        Returns:
            List of message dicts.
        """
        params = {}
        if limit:
            params["limit"] = limit

        response = self._request("GET", f"/history/private/{user_email}", params=params)
        messages: List[Dict[str, Any]] = response.get("messages", [])
        return messages

    def cleanup_stream_history(
        self, stream_id: str, topic: str, force: bool = False
    ) -> Dict[str, Any]:
        """Cleanup stream history (manual trigger).

        Args:
            stream_id: Stream identifier.
            topic: Topic name.
            force: Whether to force cleanup.

        Returns:
            Dict containing cleanup result.
        """
        params = {"force": force} if force else {}
        return self._request(
            "POST",
            f"/history/streams/{stream_id}/topics/{topic}/cleanup",
            params=params,
        )

    def cleanup_private_history(self, user_email: str, force: bool = False) -> Dict[str, Any]:
        """Cleanup private history (manual trigger).

        Args:
            user_email: User email address.
            force: Whether to force cleanup.

        Returns:
            Dict containing cleanup result.
        """
        params = {"force": force} if force else {}
        return self._request("POST", f"/history/private/{user_email}/cleanup", params=params)

    def get_stream_history_info(self, stream_id: str, topic: str) -> Dict[str, Any]:
        """Get history info for a stream/topic.

        Args:
            stream_id: Stream identifier.
            topic: Topic name.

        Returns:
            Dict containing history information.
        """
        return self._request("GET", f"/history/streams/{stream_id}/topics/{topic}/info")

    def list_stream_topics(self, stream_id: str) -> Dict[str, Any]:
        """List all topics with history for a stream.

        Args:
            stream_id: Stream/channel name

        Returns:
            Dict with topics list and metadata.
        """
        return self._request("GET", f"/history/streams/{stream_id}")

    def get_private_history_info(self, user_email: str) -> Dict[str, Any]:
        """Get history info for a private DM.

        Args:
            user_email: User email address.

        Returns:
            Dict containing history information.
        """
        return self._request("GET", f"/history/private/{user_email}/info")

    def delete_stream_history(self, stream_id: str, topic: Optional[str] = None) -> Dict[str, Any]:
        """Delete stream history.

        Args:
            stream_id: Stream/channel name
            topic: Optional topic name. If None, deletes all topics in the stream.

        Returns:
            Dict with deletion status.
        """
        if topic:
            encoded_topic = urllib.parse.quote(topic, safe="")
            return self._request("DELETE", f"/history/streams/{stream_id}/topics/{encoded_topic}")
        else:
            return self._request("DELETE", f"/history/streams/{stream_id}")

    def delete_private_history(self, user_email: str) -> Dict[str, Any]:
        """Delete private history for a user.

        Args:
            user_email: User email address

        Returns:
            Dict with deletion status.
        """
        return self._request("DELETE", f"/history/private/{user_email}")

    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics for observability.

        Returns:
            Dict containing storage statistics including stream and private history stats.
        """
        return self._request("GET", "/history/stats")

    # Backward compatibility aliases
    def delete_stream_memory(self, stream_id: str, topic: Optional[str] = None) -> Dict[str, Any]:
        """Delete stream history (backward compatibility alias).

        Args:
            stream_id: Stream/channel name
            topic: Optional topic name. If None, deletes all topics in the stream.

        Returns:
            Dict with deletion status.
        """
        return self.delete_stream_history(stream_id, topic)

    def delete_private_memory(self, user_email: str) -> Dict[str, Any]:
        """Delete private history (backward compatibility alias).

        Args:
            user_email: User email address

        Returns:
            Dict with deletion status.
        """
        return self.delete_private_history(user_email)

    # OpenAI-compatible tool methods
    def list_tools_openai(
        self, include_dangerous: bool = False, allowed_only: bool = True
    ) -> Dict[str, Any]:
        """List available tools in OpenAI-compatible format.

        Args:
            include_dangerous: Whether to include dangerous tools.
            allowed_only: Whether to return only allowed tools.

        Returns:
            Dict containing tools in OpenAI-compatible format.
        """
        params = {"include_dangerous": include_dangerous, "allowed_only": allowed_only}
        return self._request("GET", "/v1/tools", params=params)

    def execute_tool_call(
        self, tool_name: str, arguments: Dict[str, Any], user: str = "unknown"
    ) -> Dict[str, Any]:
        """Execute a single tool call.

        Args:
            tool_name: Name of the tool to execute.
            arguments: Tool arguments.
            user: User identifier for audit logging.

        Returns:
            Dict containing tool execution result.
        """
        tool_call_id = f"call_{int(time.time())}_{tool_name}"
        tool_calls = [
            {
                "id": tool_call_id,
                "type": "function",
                "function": {
                    "name": tool_name,
                    "arguments": (
                        json.dumps(arguments) if isinstance(arguments, dict) else arguments
                    ),
                },
            }
        ]

        messages = [{"role": "assistant", "content": None, "tool_calls": tool_calls}]
        request_data = {"model": "gpt-4", "messages": messages}
        extra_headers = {"X-User": user}

        response = self._request(
            "POST",
            "/v1/chat/completions",
            json=request_data,
            extra_headers=extra_headers,
        )

        if "tool_results" in response and response["tool_results"]:
            tool_result = response["tool_results"][0]
            if "content" in tool_result:
                try:
                    result: Dict[str, Any] = json.loads(tool_result["content"])
                    return result
                except json.JSONDecodeError:
                    return {
                        "success": False,
                        "error": "Failed to parse tool result",
                        "raw": tool_result["content"],
                    }
            elif "error" in tool_result:
                return {"success": False, "error": tool_result["error"]}
            else:
                return {
                    "success": False,
                    "error": "Unknown tool response format",
                    "raw": tool_result,
                }
        else:
            return self.execute_command(json.dumps({"tool": tool_name, "arguments": arguments}))


def get_pc_client() -> Optional[PCClient]:
    """Get a PC client from environment variables.

    Returns:
        PCClient instance if PC_API_URL is set, None otherwise.
    """
    api_url = os.getenv("PC_API_URL")
    api_key = os.getenv("PC_API_KEY")

    if not api_url:
        logger.warning("PC_API_URL not set - PC functionality disabled")
        return None

    return PCClient(api_url, api_key or "")
