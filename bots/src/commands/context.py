"""Command context for execution.

This module provides the CommandContext class that encapsulates
the execution environment for commands.
"""

from typing import Any, Dict, Optional, Protocol, runtime_checkable


@runtime_checkable
class ZulipHandlerProtocol(Protocol):
    """Protocol for Zulip handler to avoid circular imports."""

    def subscribe_to_stream(self, stream_name: str) -> Dict[str, Any]:
        """Subscribe bot to a stream.

        Args:
            stream_name: Name of the stream to subscribe to.

        Returns:
            Dict containing the subscription result.
        """
        ...

    def unsubscribe_from_stream(self, stream_name: str) -> Dict[str, Any]:
        """Unsubscribe bot from a stream.

        Args:
            stream_name: Name of the stream to unsubscribe from.

        Returns:
            Dict containing the unsubscription result.
        """
        ...

    def send_message(
        self, message_type: str, to: str, content: str, subject: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send a message to Zulip.

        Args:
            message_type: Type of message ('private' or 'stream').
            to: Recipient identifier (email for private, stream name for stream).
            content: Message content to send.
            subject: Optional subject/topic for stream messages.

        Returns:
            Dict containing the send result.
        """
        ...

    @property
    def subscribed_streams(self) -> set:
        """Get set of subscribed streams.

        Returns:
            Set of stream names the bot is subscribed to.
        """
        ...

    @property
    def bot_email(self) -> str:
        """Get bot's email address.

        Returns:
            The bot's email address.
        """
        ...

    @property
    def bot_full_name(self) -> str:
        """Get bot's full name.

        Returns:
            The bot's full display name.
        """
        ...


class CommandContext:
    """Context passed to command execution.

    Encapsulates all dependencies needed by commands to perform their work,
    avoiding direct coupling to ZulipHandler or other concrete classes.

    Attributes:
        zulip_handler: Handler for Zulip interactions
        sender_email: Email of the command sender
        policy_engine: Engine for policy management
        pc_client: Optional PC client for tool/memory operations
    """

    def __init__(
        self,
        zulip_handler: ZulipHandlerProtocol,
        sender_email: str,
        policy_engine,
        pc_client=None,
    ):
        """Initialize command context.

        Args:
            zulip_handler: Handler for Zulip interactions
            sender_email: Email of the command sender
            policy_engine: Engine for policy management
            pc_client: Optional PC client for tool/memory operations
        """
        self.zulip_handler = zulip_handler
        self.sender_email = sender_email
        self.policy_engine = policy_engine
        self.pc_client = pc_client
