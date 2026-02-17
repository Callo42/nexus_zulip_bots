"""Base classes and protocols for command system.

This module provides the foundation for the modular command system,
including abstract base classes, protocols, and shared context.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from interfaces import IPCClient, IPolicyEngine


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
        zulip_handler: Any,  # IMessageHandler
        sender_email: str,
        policy_engine: "IPolicyEngine",
        pc_client: Optional["IPCClient"] = None,
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


class BaseCommand(ABC):
    """Abstract base class for all commands.

    Commands are self-contained units that handle a specific admin command.
    Each command defines its name, description, and execution logic.

    Example:
        class JoinCommand(BaseCommand):
            name = "join"
            description = "Subscribe bot to a channel"

            def execute(self, args: str, context: CommandContext) -> str:
                # Command implementation
                pass
    """

    name: str = ""
    description: str = ""
    aliases: list[str] = []

    def __init__(self, policy_engine: "IPolicyEngine", pc_client: Optional["IPCClient"] = None):
        """Initialize command with dependencies.

        Args:
            policy_engine: Policy engine for policy-related operations
            pc_client: Optional PC client for tool/memory operations
        """
        self.policy_engine = policy_engine
        self.pc_client = pc_client

    @abstractmethod
    def execute(self, args: str, context: CommandContext) -> str:
        """Execute the command.

        Args:
            args: Command arguments (everything after the command name)
            context: Execution context with all dependencies

        Returns:
            Response string to send back to user
        """
        pass

    def is_available(self) -> bool:
        """Check if command is available in current configuration.

        Override this to make commands conditional on configuration
        (e.g., PC commands only available when PC_API_URL is set).

        Returns:
            True if command can be used
        """
        return True

    def get_help(self) -> str:
        """Get help text for this command.

        Returns:
            Formatted help text
        """
        return f"**/{self.name}** - {self.description}"
