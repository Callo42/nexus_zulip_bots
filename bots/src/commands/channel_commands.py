"""Channel management commands.

Commands for subscribing/unsubscribing from streams and viewing status.
"""

import re

from .base import BaseCommand, CommandContext


class JoinCommand(BaseCommand):
    """Subscribe bot to a channel."""

    name = "join"
    description = "Subscribe bot to a channel"

    def execute(self, args: str, context: CommandContext) -> str:
        """Handle /join #channel command.

        Args:
            args: Channel name (with or without #)
            context: Command execution context

        Returns:
            Response message
        """
        # Extract channel name
        match = re.search(r"#?(\S+)", args.strip())
        if not match:
            return "❌ Usage: `/join #channel-name`"

        stream_name = match.group(1)

        # Sanitize stream name
        stream_name = stream_name.strip().lstrip("#")

        if not stream_name:
            return "❌ Invalid channel name"

        # Subscribe to stream
        result = context.zulip_handler.subscribe_to_stream(stream_name)

        if result["result"] == "success":
            return (
                f"✅ Joined #{stream_name}\n\n"
                f"Use `/policy #{stream_name} [policy-name]` to set response policy."
            )
        else:
            return f"❌ Failed to join #{stream_name}: {result.get('msg', 'Unknown error')}"


class LeaveCommand(BaseCommand):
    """Unsubscribe bot from a channel."""

    name = "leave"
    description = "Unsubscribe bot from a channel"

    def execute(self, args: str, context: CommandContext) -> str:
        """Handle /leave #channel command.

        Args:
            args: Channel name (with or without #)
            context: Command execution context

        Returns:
            Response message
        """
        match = re.search(r"#?(\S+)", args.strip())
        if not match:
            return "❌ Usage: `/leave #channel-name`"

        stream_name = match.group(1).strip().lstrip("#")

        if not stream_name:
            return "❌ Invalid channel name"

        result = context.zulip_handler.unsubscribe_from_stream(stream_name)

        if result["result"] == "success":
            # Also remove policy
            context.policy_engine.remove_policy_for_stream(stream_name)
            return f"✅ Left #{stream_name}"
        else:
            return f"❌ Failed to leave #{stream_name}: {result.get('msg', 'Unknown error')}"


class StatusCommand(BaseCommand):
    """Show bot status and subscribed channels."""

    name = "status"
    description = "Show bot status and subscribed channels"

    def execute(self, args: str, context: CommandContext) -> str:
        """Handle /status command.

        Args:
            args: Empty (no arguments)
            context: Command execution context

        Returns:
            Formatted status message
        """
        subscriptions = sorted(context.zulip_handler.subscribed_streams)

        if not subscriptions:
            return "ℹ️ Not subscribed to any channels.\n\nUse `/join #channel-name` to start."

        status_lines = ["📊 **Bot Status**\n"]
        status_lines.append(f"🤖 Bot: {context.zulip_handler.bot_email}\n")
        status_lines.append("**Subscribed Channels:**")

        for stream in subscriptions:
            policy_name = context.policy_engine.get_policy_name_for_stream(stream)
            if policy_name:
                status_lines.append(f"  • #{stream} → `{policy_name}`")
            else:
                status_lines.append(f"  • #{stream} → ⚠️ *no policy set*")

        return "\n".join(status_lines)
