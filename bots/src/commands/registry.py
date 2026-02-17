"""Command registry for managing and dispatching commands.

This module provides a central registry for all commands, enabling
dynamic command discovery and execution.
"""

import logging
from typing import Dict, List, Optional, Type

from .base import BaseCommand

logger = logging.getLogger(__name__)


class CommandRegistry:
    """Registry for all available commands.

    The registry manages command instances and provides lookup by name
    or alias. It also handles command availability based on configuration.

    Example:
        registry = CommandRegistry()
        registry.register(JoinCommand, policy_engine, pc_client)

        command = registry.get("join")
        if command:
            response = command.execute(args, context)
    """

    def __init__(self):
        """Initialize empty registry."""
        self._commands: Dict[str, BaseCommand] = {}
        self._aliases: Dict[str, str] = {}
        self._categories: Dict[str, List[str]] = {
            "channel": [],
            "policy": [],
            "status": [],
            "memory": [],
            "system": [],
            "pc": [],
        }

    def register(
        self,
        command_class: Type[BaseCommand],
        policy_engine,
        pc_client=None,
        category: str = "system",
    ) -> bool:
        """Register a command class.

        Args:
            command_class: The command class to instantiate and register
            policy_engine: Policy engine to pass to command
            pc_client: Optional PC client to pass to command
            category: Command category for help organization

        Returns:
            True if registration succeeded, False if command unavailable
        """
        try:
            instance = command_class(policy_engine, pc_client)

            # Check if command is available
            if not instance.is_available():
                logger.debug(f"Command '{instance.name}' is not available, skipping")
                return False

            # Register main name
            self._commands[instance.name] = instance

            # Register aliases
            for alias in instance.aliases:
                self._aliases[alias] = instance.name

            # Add to category
            if category in self._categories:
                self._categories[category].append(instance.name)

            logger.debug(f"Registered command: {instance.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to register command {command_class}: {e}")
            return False

    def get(self, name: str) -> Optional[BaseCommand]:
        """Get a command by name or alias.

        Args:
            name: Command name or alias

        Returns:
            Command instance or None if not found
        """
        # Try direct lookup
        if name in self._commands:
            return self._commands[name]

        # Try alias lookup
        if name in self._aliases:
            actual_name = self._aliases[name]
            return self._commands.get(actual_name)

        return None

    def list_commands(self) -> List[str]:
        """List all registered command names.

        Returns:
            Sorted list of command names
        """
        return sorted(self._commands.keys())

    def list_category(self, category: str) -> List[str]:
        """List commands in a category.

        Args:
            category: Category name (channel, policy, status, memory, system, pc)

        Returns:
            List of command names in category
        """
        return self._categories.get(category, [])

    def get_categories(self) -> Dict[str, List[str]]:
        """Get all categories and their commands.

        Returns:
            Dictionary mapping category names to command lists
        """
        return self._categories.copy()

    def get_help_text(self, category: Optional[str] = None) -> str:
        """Generate help text for commands.

        Args:
            category: Optional category to filter by

        Returns:
            Formatted help text
        """
        if category:
            commands = self.list_category(category)
            lines = [f"**{category.title()} Commands:**", ""]
            for name in commands:
                cmd = self.get(name)
                if cmd:
                    lines.append(f"  `/{name}` - {cmd.description}")
            return "\n".join(lines)
        else:
            lines = ["**Available Commands:**", ""]
            for name in self.list_commands():
                cmd = self.get(name)
                if cmd:
                    lines.append(f"  `/{name}` - {cmd.description}")
            return "\n".join(lines)
