"""Command system for Zulip LLM Bot.

This package provides a modular command system for admin commands.
All commands inherit from BaseCommand and are registered with CommandRegistry.

Example:
    from commands import CommandRegistry, JoinCommand, LeaveCommand

    registry = CommandRegistry()
    registry.register(JoinCommand, policy_engine, pc_client)
    registry.register(LeaveCommand, policy_engine, pc_client)

    command = registry.get("join")
    response = command.execute("#general", context)
"""

from .base import BaseCommand, CommandContext

# Channel commands
from .channel_commands import JoinCommand, LeaveCommand, StatusCommand
from .context import ZulipHandlerProtocol

# History commands
from .history_commands import HistoryCommand, LookbackCommand

# Model commands
from .model_commands import ModelCommand

# PC commands
from .pc_commands import PcCommand

# Policy commands
from .policy_commands import DmPolicyCommand, ListPoliciesCommand, PolicyCommand
from .registry import CommandRegistry

# System commands
from .system_commands import HelpCommand, ReloadCommand

__all__ = [
    # Base classes
    "BaseCommand",
    "CommandContext",
    "ZulipHandlerProtocol",
    "CommandRegistry",
    # Channel commands
    "JoinCommand",
    "LeaveCommand",
    "StatusCommand",
    # Policy commands
    "PolicyCommand",
    "ListPoliciesCommand",
    "DmPolicyCommand",
    # Model commands
    "ModelCommand",
    # System commands
    "ReloadCommand",
    "HelpCommand",
    # History commands
    "HistoryCommand",
    "LookbackCommand",
    # PC commands
    "PcCommand",
]
