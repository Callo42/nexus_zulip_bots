"""Handles admin commands sent via DM.

This module provides command processing for admin users. It uses the modular
command system from the commands package for extensibility.
"""

import logging
from typing import TYPE_CHECKING, List, Optional

import yaml

from .commands import (
    CommandContext,
    CommandRegistry,
    DmPolicyCommand,
    HelpCommand,
    HistoryCommand,
    JoinCommand,
    LeaveCommand,
    ListPoliciesCommand,
    LookbackCommand,
    ModelCommand,
    PcCommand,
    PolicyCommand,
    ReloadCommand,
    StatusCommand,
)

if TYPE_CHECKING:
    from .interfaces import IMessageHandler, IPCClient, IPolicyEngine

logger = logging.getLogger(__name__)


class AdminCommandHandler:
    """Processes admin commands using the modular command system.

    This handler maintains backward compatibility while using the new
    CommandRegistry for dispatch. All commands are registered during
    initialization and dispatched based on the command prefix.
    """

    def __init__(
        self,
        admins_file: str,
        policy_engine: "IPolicyEngine",
        pc_client: Optional["IPCClient"] = None,
    ):
        """Initialize handler with command registry.

        Args:
            admins_file: Path to YAML file containing admin list
            policy_engine: PolicyEngine instance for policy operations
            pc_client: Optional PCClient for tool/memory operations
        """
        self.admins_file = admins_file
        self.policy_engine = policy_engine
        self.pc_client = pc_client
        self.admins = self._load_admins()

        # Initialize command registry and register all commands
        self.registry = CommandRegistry()
        self._register_commands()

    def _load_admins(self) -> List[str]:
        """Load admin emails from config file.

        Returns:
            List of admin email addresses
        """
        try:
            with open(self.admins_file, "r") as f:
                config = yaml.safe_load(f)
                admins = config.get("admins", [])
                admin_emails = [admin["email"] for admin in admins]
                logger.info(f"Loaded {len(admin_emails)} admin(s)")
                return admin_emails
        except Exception as e:
            logger.error(f"Failed to load admins: {e}")
            return []

    def _register_commands(self):
        """Register all available commands with the registry."""
        # Channel management
        self.registry.register(JoinCommand, self.policy_engine, self.pc_client, category="channel")
        self.registry.register(LeaveCommand, self.policy_engine, self.pc_client, category="channel")
        self.registry.register(StatusCommand, self.policy_engine, self.pc_client, category="status")

        # Policy commands
        self.registry.register(PolicyCommand, self.policy_engine, self.pc_client, category="policy")
        self.registry.register(
            ListPoliciesCommand, self.policy_engine, self.pc_client, category="policy"
        )
        self.registry.register(
            DmPolicyCommand, self.policy_engine, self.pc_client, category="policy"
        )

        # Model commands
        self.registry.register(ModelCommand, self.policy_engine, self.pc_client, category="status")

        # History commands
        self.registry.register(
            HistoryCommand, self.policy_engine, self.pc_client, category="history"
        )
        self.registry.register(
            LookbackCommand, self.policy_engine, self.pc_client, category="status"
        )
        self.registry.register(
            LookbackCommand, self.policy_engine, self.pc_client, category="status"
        )

        # PC commands
        self.registry.register(PcCommand, self.policy_engine, self.pc_client, category="pc")

        # System commands (special handling for help and reload)
        self.registry.register(ReloadCommand, self.policy_engine, self.pc_client, category="system")

        # Help command needs reference to registry
        help_cmd = HelpCommand(self.policy_engine, self.pc_client, self.registry)
        self.registry._commands["help"] = help_cmd
        self.registry._categories["system"].append("help")

        logger.info(f"Registered {len(self.registry.list_commands())} commands")

    def is_admin(self, email: str) -> bool:
        """Check if email is in admin list.

        Args:
            email: Email address to check

        Returns:
            True if the email is an admin
        """
        return email in self.admins

    def process_command(
        self, command: str, zulip_handler: "IMessageHandler", sender_email: str
    ) -> str:
        """Process admin command and return response.

        Args:
            command: Full command string (e.g., "/join #general")
            zulip_handler: ZulipHandler instance for Zulip operations
            sender_email: Email of the command sender

        Returns:
            Response message to send back to user
        """
        command = command.strip()

        # Parse command name and arguments
        parts = command.split(None, 1)
        command_name = parts[0].lstrip("/").lower()
        args = parts[1] if len(parts) > 1 else ""

        # Special case: handle 'model storage' as part of model command
        if command_name == "model" and args.startswith("storage"):
            # Pass 'storage' as argument to model command
            pass

        # Look up command in registry
        cmd = self.registry.get(command_name)

        if cmd:
            # Create execution context
            context = CommandContext(
                zulip_handler=zulip_handler,
                sender_email=sender_email,
                policy_engine=self.policy_engine,
                pc_client=self.pc_client,
            )

            # Execute command
            try:
                response: str = cmd.execute(args, context)

                # Special handling for reload command: also reload admins
                if command_name == "reload":
                    self.reload_admins()

                return response
            except Exception as e:
                logger.error(f"Command execution failed: {e}", exc_info=True)
                return f"❌ Command failed: {str(e)}"
        else:
            return "❓ Unknown command. Type `/help` for available commands."

    def reload_admins(self):
        """Reload admin list from file.

        Called when configuration is reloaded.
        """
        self.admins = self._load_admins()
