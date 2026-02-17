"""History management commands.

Commands for viewing and managing conversation history.
"""

import logging
import re
from datetime import datetime
from typing import Optional

from .base import BaseCommand, CommandContext

logger = logging.getLogger(__name__)


class HistoryCommand(BaseCommand):
    """View conversation history for a channel/topic."""

    name = "history"
    description = "View conversation history for a channel/topic"

    def is_available(self) -> bool:
        """Check if command is available (requires PC client).

        Returns:
            True if PC client is available, False otherwise.
        """
        return self.pc_client is not None

    def _parse_history_args(self, args: str) -> tuple[Optional[str], Optional[str], int]:
        """Parse history command arguments.

        Args:
            args: Command arguments string

        Returns:
            Tuple of (stream_name, topic, limit) or (None, None, 0) if invalid
        """
        # Parse command with support for quoted topic names
        # Pattern: #channel ["topic with spaces"|topic_without_spaces] [limit]
        pattern = r'#?(\S+)(?:\s+"([^"]+)"|\s+(\S+))?(?:\s+(\d+))?'
        match = re.match(pattern, args.strip())

        if not match:
            return None, None, 0

        stream_name = match.group(1)
        # Topic can be in group 2 (quoted) or group 3 (unquoted)
        topic = match.group(2) if match.group(2) else match.group(3)
        # Limit is in group 4
        limit = int(match.group(4)) if match.group(4) else 20

        return stream_name, topic, limit

    def _format_topic_history(
        self, stream_name: str, topic: str, messages: list, history_info: dict
    ) -> str:
        """Format history for a specific topic.

        Args:
            stream_name: Name of the stream
            topic: Topic name
            messages: List of messages
            history_info: History metadata

        Returns:
            Formatted history string
        """
        if not messages:
            return f"📝 No history found for **#{stream_name}** / **{topic}**"

        lines = [f"📝 **History for #{stream_name} / {topic}**", ""]
        lines.append(
            f"Total messages: {history_info.get('message_count', 0)} | "
            f"Showing: {len(messages)} | "
            f"Total tokens: {history_info.get('total_tokens', 0)}"
        )
        lines.append("")

        for i, msg in enumerate(reversed(messages), 1):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            user = msg.get("sender_id", msg.get("user", "unknown"))
            timestamp = msg.get("timestamp", 0)

            dt = datetime.fromtimestamp(timestamp)
            time_str = dt.strftime("%Y-%m-%d %H:%M:%S")

            if len(content) > 200:
                content = content[:200] + "..."

            lines.append(f"**{i}.** [{time_str}] **{role}** ({user})")
            lines.append(f"   {content}")
            lines.append("")

        return "\n".join(lines)

    def _format_stream_summary(
        self, stream_name: str, topics: list, context: CommandContext
    ) -> str:
        """Format summary of all topics in a stream.

        Args:
            stream_name: Name of the stream
            topics: List of topic info dicts
            context: Command execution context

        Returns:
            Formatted summary string
        """
        if not topics:
            return (
                f"📝 No history found for **#{stream_name}**\n\n"
                f"This channel has no stored messages yet."
            )

        lines = [f"📝 **History Summary for #{stream_name}**", ""]
        lines.append(f"Total topics with history: {len(topics)}")
        lines.append("")

        # Show first few messages from each topic
        for topic_info in topics[:5]:  # Limit to 5 topics
            topic_hash = topic_info.get("topic_hash", "unknown")
            msg_count = topic_info.get("message_count", 0)
            tokens = topic_info.get("total_tokens", 0)

            lines.append(f"📁 **{topic_hash}** ({msg_count} messages, {tokens} tokens)")

            # Get recent messages from this topic
            try:
                assert context.pc_client is not None  # nosec
                messages = context.pc_client.get_stream_messages(stream_name, topic_hash, limit=3)
                if messages:
                    for msg in reversed(messages):
                        content = msg.get("content", "")
                        role = msg.get("role", "user")
                        if len(content) > 100:
                            content = content[:100] + "..."
                        lines.append(f"  • [{role}] {content}")
            except Exception as e:
                lines.append(f"  ⚠️ Error loading messages: {e}")

            lines.append("")

        if len(topics) > 5:
            lines.append(f"... and {len(topics) - 5} more topics")
            lines.append("")

        lines.append(f"To view full messages, use: `/history #{stream_name} <topic-name>`")
        lines.append(f'For topics with spaces, use quotes: `/history #{stream_name} "topic name"`')

        return "\n".join(lines)

    def _handle_clear_stream(self, args: str, context: CommandContext) -> str:
        """Handle clearing stream history.

        Args:
            args: Stream clear arguments (#channel [topic])
            context: Command execution context

        Returns:
            Success or error message
        """
        parts = args.split(None, 2)
        if len(parts) < 2:
            return "❌ Usage: `/history clear stream #channel-name [topic-name]`"

        stream_name = parts[1].lstrip("#")
        topic_name = parts[2].strip("\"'") if len(parts) > 2 else None

        try:
            assert context.pc_client is not None  # nosec
            result = context.pc_client.delete_stream_history(stream_name, topic_name)
            if result.get("success"):
                if topic_name:
                    return f"🗑️ History cleared for #{stream_name} / {topic_name}"
                return f"🗑️ All history cleared for stream #{stream_name}"
            return f"⚠️ {result.get('message', 'Failed to clear history')}"
        except Exception as e:
            logger.error(f"Failed to clear stream history: {e}", exc_info=True)
            return f"❌ Failed to clear history: {str(e)}"

    def _handle_clear_private(self, args: str, context: CommandContext) -> str:
        """Handle clearing private history.

        Args:
            args: Private clear arguments (<email>)
            context: Command execution context

        Returns:
            Success or error message
        """
        parts = args.split(None, 1)
        if len(parts) < 2:
            return "❌ Usage: `/history clear private <user-email>`"

        user_email = parts[1]

        try:
            assert context.pc_client is not None  # nosec
            result = context.pc_client.delete_private_history(user_email)
            if result.get("success"):
                return f"🗑️ Private history cleared for {user_email}"
            return f"⚠️ {result.get('message', 'Failed to clear history')}"
        except Exception as e:
            logger.error(f"Failed to clear private history: {e}", exc_info=True)
            return f"❌ Failed to clear history: {str(e)}"

    def _handle_clear(self, args: str, context: CommandContext) -> str:
        """Handle clearing history.

        Args:
            args: Clear arguments (stream #channel [topic] or private <email>)
            context: Command execution context

        Returns:
            Success or error message
        """
        if not context.pc_client:
            return "❌ PC functionality not configured."

        parts = args.split(None, 1)
        if not parts:
            return (
                "❌ Usage: `/history clear stream #channel [topic]`\n"
                "Or: `/history clear private <user-email>`"
            )

        clear_type = parts[0].lower()

        if clear_type == "stream":
            return self._handle_clear_stream(args, context)

        if clear_type == "private":
            return self._handle_clear_private(args, context)

        return f"❌ Unknown clear type: `{clear_type}`. Use `stream` or `private`."

    def execute(self, args: str, context: CommandContext) -> str:
        """Handle /history #channel [topic] [limit] or /history clear ... command.

        Args:
            args: #channel-name [topic] [limit] or clear stream/private ...
            context: Command execution context

        Returns:
            Formatted history content
        """
        if not context.pc_client:
            return "❌ PC functionality not configured. Set PC_API_URL environment variable."

        args = args.strip()

        if args.lower().startswith("clear "):
            return self._handle_clear(args[6:], context)

        stream_name, topic, limit = self._parse_history_args(args)

        if stream_name is None:
            return (
                "❌ Usage: `/history #channel-name [topic] [limit]`\n\n"
                "Examples:\n"
                "  `/history #test-channel` - List all topics in the channel\n"
                "  `/history #test-channel my-topic` - View messages in a specific topic\n"
                '  `/history #test-channel "channel events"` - Topic names with spaces\n'
                "  `/history #test-channel my-topic 10` - View last 10 messages in topic"
            )

        try:
            if topic:
                # Get messages for specific topic
                messages = context.pc_client.get_stream_messages(stream_name, topic, limit=limit)
                history_info = context.pc_client.get_stream_history_info(stream_name, topic)
                return self._format_topic_history(stream_name, topic, messages, history_info)
            else:
                # No topic specified - list all topics
                topics_info = context.pc_client.list_stream_topics(stream_name)
                topics = topics_info.get("topics", [])
                return self._format_stream_summary(stream_name, topics, context)

        except Exception as e:
            logger.error(f"Failed to get history: {e}", exc_info=True)
            return f"❌ Failed to retrieve history: {str(e)}"


class LookbackCommand(BaseCommand):
    """Set or view lookback message count for history."""

    name = "lookback"
    description = "Set or view lookback message count for a channel or DM"

    def _parse_lookback_args(self, args: str) -> tuple[Optional[str], Optional[str], bool]:
        """Parse lookback command arguments.

        Args:
            args: Command arguments string

        Returns:
            Tuple of (target, action, is_valid)
        """
        # Parse: /lookback #channel-name [number|show|reset]
        match = re.search(r"(#?\S+)(?:\s+(\S+))?", args.strip())
        if not match:
            return None, None, False

        target = match.group(1).strip()
        action = match.group(2)
        return target, action, True

    def _get_lookback_info(
        self,
        is_dm: bool,
        admin_email: Optional[str],
        stream_name: Optional[str],
        context: CommandContext,
    ) -> tuple[int, int]:
        """Get current lookback and policy default values.

        Args:
            is_dm: Whether this is a DM target
            admin_email: Email for DM target
            stream_name: Stream name for channel target
            context: Command execution context

        Returns:
            Tuple of (current_lookback, policy_default)
        """
        policy_default = 100
        current_lookback = 0

        if is_dm and admin_email:
            current_lookback = context.policy_engine.get_lookback_for_dm(admin_email)
            policy = context.policy_engine.get_policy_for_admin_dm(admin_email)
            if policy and "memory" in policy:
                policy_default = policy["memory"].get("lookback_messages", 100)
        elif stream_name:
            current_lookback = context.policy_engine.get_lookback_for_stream(stream_name)
            policy = context.policy_engine.get_policy_for_stream(stream_name)
            if policy and "memory" in policy:
                policy_default = policy["memory"].get("lookback_messages", 100)

        return current_lookback, policy_default

    def _handle_show_action(
        self,
        is_dm: bool,
        admin_email: Optional[str],
        stream_name: Optional[str],
        target_display: str,
        target_type: str,
        context: CommandContext,
    ) -> str:
        """Handle 'show' action for lookback command.

        Args:
            is_dm: Whether the target is a DM.
            admin_email: Admin email for DM targets.
            stream_name: Stream name for channel targets.
            target_display: Display name for the target.
            target_type: Type of target ('DM' or 'channel').
            context: Command execution context.

        Returns:
            Formatted lookback information message.
        """
        current_lookback, policy_default = self._get_lookback_info(
            is_dm, admin_email, stream_name, context
        )

        response = f"📋 **Lookback for {target_display} ({target_type}):**\n\n"
        response += f"Current: **{current_lookback}** messages\n"
        response += f"Policy default: **{policy_default}** messages"
        return response

    def _handle_reset_action(
        self,
        is_dm: bool,
        admin_email: Optional[str],
        stream_name: Optional[str],
        target_display: str,
        context: CommandContext,
    ) -> str:
        """Handle 'reset' action for lookback command.

        Args:
            is_dm: Whether the target is a DM.
            admin_email: Admin email for DM targets.
            stream_name: Stream name for channel targets.
            target_display: Display name for the target.
            context: Command execution context.

        Returns:
            Success or error message for the reset operation.
        """
        try:
            policy_default = 100
            if is_dm and admin_email:
                context.policy_engine.reset_lookback_for_dm(admin_email)
                policy = context.policy_engine.get_policy_for_admin_dm(admin_email)
                if policy and "memory" in policy:
                    policy_default = policy["memory"].get("lookback_messages", 100)
            elif stream_name:
                context.policy_engine.reset_lookback_for_stream(stream_name)
                policy = context.policy_engine.get_policy_for_stream(stream_name)
                if policy and "memory" in policy:
                    policy_default = policy["memory"].get("lookback_messages", 100)

            return (
                f"✅ Lookback reset to policy default "
                f"(**{policy_default}**) for {target_display}"
            )
        except Exception as e:
            logger.error(f"Failed to reset lookback: {e}", exc_info=True)
            return f"❌ Failed to reset: {str(e)}"

    def _handle_set_action(
        self,
        is_dm: bool,
        admin_email: Optional[str],
        stream_name: Optional[str],
        target_display: str,
        target_type: str,
        lookback_count: int,
        action: str,
        context: CommandContext,
    ) -> str:
        """Handle setting a specific lookback count.

        Args:
            is_dm: Whether the target is a DM.
            admin_email: Admin email for DM targets.
            stream_name: Stream name for channel targets.
            target_display: Display name for the target.
            target_type: Type of target ('DM' or 'channel').
            lookback_count: The lookback count value to set.
            action: The action string containing the lookback value.
            context: Command execution context.

        Returns:
            Success or error message for the set operation.
        """
        try:
            lookback_value = int(action)
            if lookback_value <= 0:
                return "❌ Lookback count must be a positive integer (e.g., 50, 100, 200)"

            if is_dm and admin_email:
                context.policy_engine.set_lookback_for_dm(admin_email, lookback_value)
            elif stream_name:
                context.policy_engine.set_lookback_for_stream(stream_name, lookback_value)

            return (
                f"✅ Set lookback to **{lookback_value}** messages for {target_display}\n\n"
                f"The bot will now remember up to {lookback_value} "
                f"previous messages in this {target_type}."
            )
        except ValueError:
            return f"❌ Invalid lookback value: '{action}'. Use a number, 'show', or 'reset'."
        except Exception as e:
            logger.error(f"Failed to set lookback: {e}", exc_info=True)
            return f"❌ Failed to set lookback: {str(e)}"

    def execute(self, args: str, context: CommandContext) -> str:
        """Handle /lookback #channel [number|show|reset] command.

        Args:
            args: #channel-name|email [number|show|reset]
            context: Command execution context

        Returns:
            Response message
        """
        target, action, is_valid = self._parse_lookback_args(args)

        if not is_valid or target is None:
            return (
                "❌ Usage: `/lookback #channel-name [number|show|reset]`\n\n"
                "Examples:\n"
                "  `/lookback #test-channel show` - Show current lookback setting\n"
                "  `/lookback #test-channel 50` - Set lookback to 50 messages\n"
                "  `/lookback #test-channel reset` - Reset to policy default (100)"
            )

        if not action:
            return "❌ Usage: `/lookback #channel-name [number|show|reset]`"

        # Determine if target is a DM (email address) or a stream (channel name)
        is_dm = "@" in target
        admin_email: Optional[str]
        stream_name: Optional[str]
        if is_dm:
            # It's a DM - use admin email directly
            admin_email = target
            stream_name = None
            target_display = admin_email
            target_type = "DM"
        else:
            # It's a stream - remove leading '#' if present
            stream_name = target.lstrip("#")
            admin_email = None
            target_display = f"#{stream_name}"
            target_type = "channel"

        # Route to appropriate handler based on action
        action_lower = action.lower()
        if action_lower == "show":
            return self._handle_show_action(
                is_dm, admin_email, stream_name, target_display, target_type, context
            )
        elif action_lower == "reset":
            return self._handle_reset_action(
                is_dm, admin_email, stream_name, target_display, context
            )
        else:
            # Try to set lookback count
            return self._handle_set_action(
                is_dm,
                admin_email,
                stream_name,
                target_display,
                target_type,
                0,
                action,
                context,
            )
