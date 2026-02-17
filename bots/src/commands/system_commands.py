"""System administration commands.

Commands for reloading configuration and help.
"""

import logging
from typing import Optional

from .base import BaseCommand, CommandContext
from .registry import CommandRegistry

logger = logging.getLogger(__name__)


class ReloadCommand(BaseCommand):
    """Reload configuration files."""

    name = "reload"
    description = "Reload configuration files (policies, admins)"

    def __init__(self, policy_engine, pc_client=None, admins_file: str = "/app/admins.yml"):
        """Initialize reload command.

        Args:
            policy_engine: Policy engine for policy-related operations
            pc_client: Optional PC client for tool/memory operations
            admins_file: Path to admins configuration file
        """
        super().__init__(policy_engine, pc_client)
        self.admins_file = admins_file

    def execute(self, args: str, context: CommandContext) -> str:
        """Handle /reload command.

        Note: Reloading the admin list is handled by AdminCommandHandler
        after this command executes.

        Args:
            args: Empty (no arguments)
            context: Command execution context

        Returns:
            Response message
        """
        try:
            context.policy_engine.reload_policies()
            return "✅ Configuration reloaded successfully"
        except Exception as e:
            logger.error(f"Failed to reload config: {e}", exc_info=True)
            return f"❌ Failed to reload: {str(e)}"


class HelpCommand(BaseCommand):
    """Show help information."""

    name = "help"
    description = "Show help information"

    def __init__(self, policy_engine, pc_client=None, registry: Optional[CommandRegistry] = None):
        """Initialize help command.

        Args:
            policy_engine: Policy engine for policy-related operations
            pc_client: Optional PC client for tool/memory operations
            registry: Optional command registry for listing available commands
        """
        super().__init__(policy_engine, pc_client)
        self.registry = registry

    def execute(self, args: str, context: CommandContext) -> str:
        """Handle /help [category] command.

        Args:
            args: Optional category name
            context: Command execution context

        Returns:
            Formatted help text
        """
        category = args.strip().lower() if args else None

        if category:
            return self._get_category_help(category, context)

        # Show main help with categories
        return self._get_main_help(context)

    def _get_main_help(self, context: CommandContext) -> str:
        """Generate main help with categories."""
        lines = [
            "🤖 **Bot Admin Commands**",
            "",
            "**Command Categories:**",
            "",
            "📁 **channel** - Channel management commands",
            "📋 **policy** - Policy configuration commands",
            "📊 **status** - Status and information commands",
            "🧠 **history** - Conversation history commands",
            "⚙️ **system** - System administration commands",
        ]

        if context.pc_client:
            lines.append("🔧 **pc** - PC sidecar commands")

        lines.extend(
            [
                "",
                "Use `/help <category>` to see detailed commands in each category.",
                "",
                "**Available Policies:**",
            ]
        )

        policies = context.policy_engine.list_policies()
        lines.append(", ".join(f"`{p}`" for p in sorted(policies)))

        lines.extend(
            [
                "",
                "📖 Edit policies in `/app/config/policies.yml`",
                "🌐 Manage LLM models at http://127.0.0.1:4000",
            ]
        )

        return "\n".join(lines)

    def _get_category_help(self, category: str, context: CommandContext) -> str:
        """Generate help for a specific category."""
        categories = {
            "channel": """📁 **Channel Management Commands**

**Subscribe/Unsubscribe:**
  `/join #channel-name` - Subscribe bot to a channel
  `/leave #channel-name` - Unsubscribe from a channel

Use `/help policy` to configure response policies for channels.
            """,
            "policy": """📋 **Policy Configuration Commands**

**Channel Policies:**
  `/policy #channel-name [policy-name]` - Set response policy for channel
  `/policy #channel-name show` - View current policy for channel
  `/policies` - List all available policies with details

**DM Policies:**
  `/dm-policy [policy-name|show]` - Set/view policy for your DM conversations

**Examples:**
  `/policy #general helpful-assistant`
  `/dm-policy show`
            """,
            "status": """📊 **Status & Information Commands**

**Overview:**
  `/status` - Show subscribed channels and policies

**Model Management:**
  `/model [model-name]` - List models or view model details
  `/model storage` - View model registry storage info

**Examples:**
  `/model gpt-4o-mini`
            """,
            "history": """🧠 **Conversation History Commands**

**View History:**
  `/history #channel [topic] [limit]` - View conversation history for channel/topic

**Clear History:**
  `/history clear stream #channel [topic]` - Clear stream conversation history
  `/history clear private <user-email>` - Clear private conversation history

**Examples:**
  `/history #general` - List all topics in channel
  `/history #general "topic name" 10` - View last 10 messages in topic
  `/history clear stream #general` - Clear all history in channel
  `/history clear stream #general "topic name"` - Clear specific topic
            """,
            "system": """⚙️ **System Administration Commands**

**Configuration:**
  `/reload` - Reload configuration files (policies, admins)
  `/help [category]` - Show this help message

**System Info:**
  Use `/help <category>` for other command categories.

**PC Sidecar:**
  Use `/help pc` for PC sidecar administration commands.
            """,
        }

        if category in categories:
            return categories[category].strip()

        if category == "pc" and context.pc_client:
            return """🔧 **PC Sidecar Commands**

**Health & Monitoring:**
  `/pc health` - Check PC sidecar health
  `/pc storage` - View PC storage statistics

**File Operations:**
  `/pc files [path]` - List files or read file
  `/pc write <path> <content>` - Write file

**Command Execution:**
  `/pc exec <command>` - Execute shell command
  `/pc python <script>` - Run Python script

**Security:**
  `/pc audit-logs [limit]` - View security audit logs
  `/pc keys` - List masked API keys
  `/pc rotate-key` - Generate new API key

**Tools:**
  `/pc tools` - List available tools
            """.strip()

        return f"❓ Unknown category: `{category}`. Use `/help` for available categories."
