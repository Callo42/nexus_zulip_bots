"""Interface definitions for Zulip LLM Bot.

Provides Protocol types for dependency injection and improved testability.
All interfaces use runtime_checkable for isinstance() checks.

Example:
    from interfaces import IPolicyEngine, IMessageHandler

    def process_message(handler: IMessageHandler, policy_engine: IPolicyEngine):
        # Works with any implementation
        pass
"""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class IModelRegistry(Protocol):
    """Model registry interface.

    Provides access to model configurations and formatting rules.
    """

    def list_models(self) -> Dict[str, str]:
        """List available models.

        Returns:
            Dict mapping model name to description
        """
        ...

    def get_model_config(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a model.

        Args:
            model_name: Model identifier

        Returns:
            Model configuration dict or None
        """
        ...

    def get_storage_info(self) -> Dict[str, Any]:
        """Get storage information about the registry.

        Returns:
            Storage information dict
        """
        ...


@runtime_checkable
class IPolicyEngine(Protocol):
    """Policy engine interface for policy management.

    Provides policy retrieval, assignment, and configuration management.
    """

    @property
    def model_registry(self) -> "IModelRegistry":
        """Get the model registry.

        Returns:
            Model registry instance
        """
        ...

    def get_policy(self, policy_name: str) -> Optional[Dict[str, Any]]:
        """Get policy configuration by name.

        Args:
            policy_name: Name of the policy

        Returns:
            Policy configuration dict or None if not found
        """
        ...

    def get_policy_for_stream(self, stream_name: str) -> Optional[Dict[str, Any]]:
        """Get policy assigned to a stream.

        Args:
            stream_name: Stream/channel name

        Returns:
            Policy configuration for the stream
        """
        ...

    def get_policy_for_admin_dm(self, admin_email: str) -> Optional[Dict[str, Any]]:
        """Get policy for admin DM conversations.

        Args:
            admin_email: Admin email address

        Returns:
            Policy configuration for admin DMs
        """
        ...

    def set_policy_for_admin_dm(self, admin_email: str, policy_name: str) -> None:
        """Set policy for admin DM conversations.

        Args:
            admin_email: Admin email address
            policy_name: Policy name to assign

        Returns:
            None
        """
        ...

    def get_policy_name_for_admin_dm(self, admin_email: str) -> Optional[str]:
        """Get the policy name assigned to admin DMs.

        Args:
            admin_email: Admin email address

        Returns:
            Policy name or None if not set
        """
        ...

    def set_policy_for_stream(self, stream_name: str, policy_name: str) -> None:
        """Assign a policy to a stream.

        Args:
            stream_name: Stream/channel name
            policy_name: Policy name to assign

        Returns:
            None
        """
        ...

    def reload_policies(self) -> None:
        """Reload policies from configuration file.

        Returns:
            None
        """
        ...

    def list_policies(self) -> List[str]:
        """List all available policy names.

        Returns:
            List of policy names
        """
        ...

    def policy_exists(self, policy_name: str) -> bool:
        """Check if a policy exists.

        Args:
            policy_name: Policy name to check

        Returns:
            True if policy exists
        """
        ...

    def remove_policy_for_stream(self, stream_name: str) -> None:
        """Remove policy assignment from a stream.

        Args:
            stream_name: Stream to remove policy from

        Returns:
            None
        """
        ...

    def get_policy_name_for_stream(self, stream_name: str) -> Optional[str]:
        """Get the policy name assigned to a stream.

        Args:
            stream_name: Stream name

        Returns:
            Policy name or None if not set
        """
        ...

    def get_lookback_for_stream(self, stream_name: str) -> int:
        """Get lookback message count for a stream.

        Args:
            stream_name: Stream name

        Returns:
            Number of messages to look back
        """
        ...

    def set_lookback_for_stream(self, stream_name: str, count: int) -> None:
        """Set lookback message count for a stream.

        Args:
            stream_name: Stream name
            count: Number of messages to look back

        Returns:
            None
        """
        ...

    def reset_lookback_for_stream(self, stream_name: str) -> None:
        """Reset lookback to policy default for a stream.

        Args:
            stream_name: Stream name

        Returns:
            None
        """
        ...

    def get_lookback_for_dm(self, admin_email: str) -> int:
        """Get lookback message count for DM conversations.

        Args:
            admin_email: Admin email address

        Returns:
            Number of messages to look back
        """
        ...

    def set_lookback_for_dm(self, admin_email: str, count: int) -> None:
        """Set lookback message count for DM conversations.

        Args:
            admin_email: Admin email address
            count: Number of messages to look back

        Returns:
            None
        """
        ...

    def reset_lookback_for_dm(self, admin_email: str) -> None:
        """Reset lookback to policy default for DM conversations.

        Args:
            admin_email: Admin email address

        Returns:
            None
        """
        ...

    def get_formatter(self, model_name: str) -> Optional[Any]:
        """Get formatter for a model.

        Args:
            model_name: Model identifier

        Returns:
            Formatter instance or None
        """
        ...


@runtime_checkable
class IMessageHandler(Protocol):
    """Message handler interface for Zulip interactions.

    Handles message sending and stream subscriptions.
    """

    @property
    def bot_email(self) -> str:
        """Get bot's email address.

        Returns:
            Bot's email address as string
        """
        ...

    @property
    def subscribed_streams(self) -> set:
        """Get set of subscribed stream names.

        Returns:
            Set of subscribed stream names
        """
        ...

    def subscribe_to_stream(self, stream_name: str) -> Dict[str, Any]:
        """Subscribe bot to a stream.

        Args:
            stream_name: Stream name to subscribe to

        Returns:
            Subscription result
        """
        ...

    def unsubscribe_from_stream(self, stream_name: str) -> Dict[str, Any]:
        """Unsubscribe bot from a stream.

        Args:
            stream_name: Stream name to unsubscribe from

        Returns:
            Unsubscription result
        """
        ...

    def send_message(
        self, message_type: str, to: str, content: str, subject: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send a message to Zulip.

        Args:
            message_type: 'private' or 'stream'
            to: Recipient (email or stream name)
            content: Message content
            subject: Topic name (for stream messages)

        Returns:
            Send result
        """
        ...


@runtime_checkable
class IPCClient(Protocol):
    """PC client interface for sidecar operations.

    Provides access to PC sidecar capabilities.
    """

    def health_check(self) -> bool:
        """Check if PC API is healthy.

        Returns:
            True if healthy
        """
        ...

    def list_tools(self) -> Dict[str, Any]:
        """List available tools.

        Returns:
            Tool definitions
        """
        ...

    def execute_tool_call(
        self, tool_name: str, arguments: Dict[str, Any], user: str = "unknown"
    ) -> Dict[str, Any]:
        """Execute a tool call.

        Args:
            tool_name: Tool to execute
            arguments: Tool arguments
            user: User identifier for audit

        Returns:
            Tool execution result
        """
        ...

    def add_stream_message(
        self,
        stream_id: str,
        topic: str,
        role: str,
        content: str,
        user: str,
        message_id: Optional[int] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Add message to stream history.

        Args:
            stream_id: Stream identifier
            topic: Topic name
            role: Message role (user/assistant)
            content: Message content
            user: User identifier
            message_id: Optional message ID
            config: Optional memory configuration

        Returns:
            Storage result
        """
        ...

    def get_stream_messages(
        self, stream_id: str, topic: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get messages from stream history.

        Args:
            stream_id: Stream identifier
            topic: Topic name
            limit: Maximum messages to return

        Returns:
            List of messages
        """
        ...

    def get_stream_history_info(self, stream_id: str, topic: str) -> Dict[str, Any]:
        """Get history info for a stream/topic.

        Args:
            stream_id: Stream identifier
            topic: Topic name

        Returns:
            History info dict with message_count, total_tokens, etc.
        """
        ...

    def list_stream_topics(self, stream_id: str) -> Dict[str, Any]:
        """List all topics with history for a stream.

        Args:
            stream_id: Stream identifier

        Returns:
            Dict with topics list
        """
        ...

    def get_private_messages(
        self, user_email: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get private conversation messages.

        Args:
            user_email: User email address
            limit: Maximum messages to return

        Returns:
            List of messages
        """
        ...

    def add_private_message(
        self,
        user_email: str,
        role: str,
        content: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Add message to private conversation history.

        Args:
            user_email: User email address
            role: Message role (user/assistant)
            content: Message content
            config: Optional memory configuration

        Returns:
            Storage result
        """
        ...

    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics.

        Returns:
            Storage statistics dict
        """
        ...

    def execute_command(self, command: str) -> Dict[str, Any]:
        """Execute shell command.

        Args:
            command: Shell command to execute

        Returns:
            Execution result with stdout, stderr, return_code
        """
        ...

    def list_files(self) -> List[Dict[str, Any]]:
        """List files in PC storage.

        Returns:
            List of file information dicts
        """
        ...

    def read_file(self, path: str) -> str:
        """Read file content.

        Args:
            path: File path

        Returns:
            File content
        """
        ...

    def write_file(self, path: str, content: str) -> Dict[str, Any]:
        """Write file content.

        Args:
            path: File path
            content: File content

        Returns:
            Write result
        """
        ...

    def run_python_script(self, script: str) -> Dict[str, Any]:
        """Run Python script.

        Args:
            script: Python script to run

        Returns:
            Execution result
        """
        ...

    def rotate_key(self) -> Dict[str, Any]:
        """Generate new API key.

        Returns:
            Result with new_key and total_keys
        """
        ...

    def list_keys(self) -> Dict[str, Any]:
        """List API keys.

        Returns:
            Dict with keys list and count
        """
        ...

    def get_audit_logs(self, limit: int = 50) -> Dict[str, Any]:
        """Get security audit logs.

        Args:
            limit: Maximum number of logs

        Returns:
            Dict with logs list and count
        """
        ...

    def delete_stream_history(
        self, stream_name: str, topic: Optional[str] = None
    ) -> Dict[str, Any]:
        """Delete stream conversation history.

        Args:
            stream_name: Stream name
            topic: Optional topic name (None for all topics)

        Returns:
            Deletion result
        """
        ...

    def delete_private_history(self, user_email: str) -> Dict[str, Any]:
        """Delete private conversation history.

        Args:
            user_email: User email address

        Returns:
            Deletion result
        """
        ...


@runtime_checkable
class ILLMClient(Protocol):
    """LLM client interface for generating responses.

    Handles LLM API calls and response generation.
    """

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        policy: Dict[str, Any],
        user: str = "unknown",
        stream_id: Optional[str] = None,
        topic: Optional[str] = None,
        user_email: Optional[str] = None,
    ) -> str:
        """Generate response from LLM.

        Args:
            messages: Conversation messages
            policy: Policy configuration
            user: User identifier
            stream_id: Optional stream ID for history
            topic: Optional topic for history
            user_email: Optional user email for private history

        Returns:
            Generated response text
        """
        ...


@runtime_checkable
class IAdminCommandHandler(Protocol):
    """Admin command handler interface.

    Processes admin commands from DM messages.
    """

    def is_admin(self, email: str) -> bool:
        """Check if email is admin.

        Args:
            email: Email to check

        Returns:
            True if admin
        """
        ...

    def process_command(
        self, command: str, zulip_handler: IMessageHandler, sender_email: str
    ) -> str:
        """Process admin command.

        Args:
            command: Command string
            zulip_handler: Message handler
            sender_email: Sender email

        Returns:
            Response text
        """
        ...


# TypeGuard for PC client availability checking
def ensure_pc_client(ctx) -> bool:
    """Check that PC client is available.

    This function checks if a CommandContext has a PC client available.
    When used in an if statement, mypy will narrow the type to exclude None.

    Args:
        ctx: CommandContext instance to check

    Returns:
        True if PC client is available

    Example:
        if not ensure_pc_client(context):
            return "❌ PC client not available"
        # context.pc_client is now IPCClient, not Optional[IPCClient]
        result = context.pc_client.health_check()
    """
    return ctx.pc_client is not None
