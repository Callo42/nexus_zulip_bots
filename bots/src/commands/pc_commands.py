"""PC sidecar commands.

Commands for interacting with the bot's PC sidecar.
"""

import json
import logging
import time

from .base import BaseCommand, CommandContext

logger = logging.getLogger(__name__)


class PcCommand(BaseCommand):
    """PC sidecar command dispatcher."""

    name = "pc"
    description = "PC sidecar commands (health, storage, files, exec, etc.)"

    def is_available(self) -> bool:
        """Check if command is available (requires PC client).

        Returns:
            True if PC client is available, False otherwise.
        """
        return self.pc_client is not None

    def execute(self, args: str, context: CommandContext) -> str:
        """Dispatch to subcommand handlers.

        Args:
            args: Subcommand and arguments
            context: Command execution context

        Returns:
            Response message
        """
        if not context.pc_client:
            return "❌ PC functionality not configured. Set PC_API_URL environment variable."

        parts = args.strip().split()
        if not parts:
            return self._get_help()

        subcommand = parts[0].lower()
        sub_args = " ".join(parts[1:]) if len(parts) > 1 else ""

        # Map subcommands to handlers
        handlers = {
            "health": self._handle_health,
            "storage": self._handle_storage,
            "tools": self._handle_tools,
            "exec": self._handle_exec,
            "files": self._handle_files,
            "python": self._handle_python,
            "write": self._handle_write,
            "rotate-key": self._handle_rotate_key,
            "keys": self._handle_keys,
            "audit-logs": self._handle_audit_logs,
        }

        handler = handlers.get(subcommand)
        if handler:
            return handler(sub_args, context)
        else:
            return f"❌ Unknown subcommand: `{subcommand}`. Use `/pc` for help."

    def _get_help(self) -> str:
        """Get help text for PC commands."""
        return """❌ Usage: `/pc <subcommand> [args...]`

**Subcommands:**
  `health` - Check PC health
  `storage` - View PC storage statistics
  `exec <command>` - Execute shell command
  `files [path]` - List files or read file
  `tools` - List available tools
  `python <script>` - Run Python script
  `write <path> <content>` - Write file
  `rotate-key` - Generate new API key
  `keys` - List masked API keys
  `audit-logs [limit]` - View security audit logs

💡 *Use `/history clear` to clear conversation history*
"""

    def _handle_health(self, args: str, context: CommandContext) -> str:
        """Check PC health.

        Args:
            args: Command arguments (unused).
            context: Command execution context.

        Returns:
            Health status message.
        """
        if (pc := context.pc_client) is None:
            return "❌ PC client not available"
        is_healthy = pc.health_check()
        return f"✅ PC API is {'healthy' if is_healthy else 'unhealthy'}"

    def _handle_storage(self, args: str, context: CommandContext) -> str:
        """View PC storage statistics.

        Args:
            args: Command arguments (unused).
            context: Command execution context.

        Returns:
            Formatted storage statistics message.
        """
        if (pc := context.pc_client) is None:
            return "❌ PC client not available"
        try:
            stats = pc.get_storage_stats()

            lines = ["📊 **PC Storage Statistics**", ""]
            lines.append(f"Storage Path: `{stats.get('storage_path', 'N/A')}`")
            lines.append(f"Total Files: **{stats.get('total_files', 0)}**")
            lines.append("")

            # Stream history stats
            stream_stats = stats.get("streams", {})
            lines.append("**Stream History:**")
            lines.append(f"  Streams: **{stream_stats.get('count', 0)}**")
            lines.append(f"  Total Messages: **{stream_stats.get('total_messages', 0)}**")
            lines.append(f"  Total Tokens: **{stream_stats.get('total_tokens', 0)}**")

            # Top streams
            stream_entries = stream_stats.get("entries", [])
            if stream_entries:
                lines.append("")
                lines.append(f"**Top {len(stream_entries)} Streams (by message count):**")
                for entry in stream_entries[:30]:
                    lines.append(
                        f"  • `{entry['stream_hash']}` - "
                        f"{entry['topics']} topics, "
                        f"{entry['messages']} messages, "
                        f"{entry['tokens']} tokens"
                    )
            lines.append("")

            # Private history stats
            private_stats = stats.get("private", {})
            lines.append("**Private History:**")
            lines.append(f"  Users: **{private_stats.get('count', 0)}**")
            lines.append(f"  Total Messages: **{private_stats.get('total_messages', 0)}**")
            lines.append(f"  Total Tokens: **{private_stats.get('total_tokens', 0)}**")

            # Top private histories
            private_entries = private_stats.get("entries", [])
            if private_entries:
                lines.append("")
                lines.append(f"**Top {len(private_entries)} Users (by message count):**")
                for entry in private_entries[:30]:
                    lines.append(
                        f"  • `{entry['user_hash']}` - "
                        f"{entry['messages']} messages, "
                        f"{entry['tokens']} tokens"
                    )

            lines.append("")
            lines.append("💡 *Use `/history #channel` to view conversation content*")

            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Failed to get PC storage stats: {e}", exc_info=True)
            return f"❌ Failed to get PC storage stats: {str(e)}"

    def _handle_tools(self, args: str, context: CommandContext) -> str:
        """List available tools.

        Args:
            args: Command arguments (unused).
            context: Command execution context.

        Returns:
            Formatted list of available tools.
        """
        if (pc := context.pc_client) is None:
            return "❌ PC client not available"
        tools = pc.list_tools()
        return f"🔧 Available tools:\n```json\n{json.dumps(tools, indent=2)}```"

    def _handle_exec(self, args: str, context: CommandContext) -> str:
        """Execute shell command.

        Args:
            args: Shell command to execute.
            context: Command execution context.

        Returns:
            Command execution result message.
        """
        if (pc := context.pc_client) is None:
            return "❌ PC client not available"
        if not args:
            return "❌ Usage: `/pc exec <shell command>`"

        result = pc.execute_command(args)
        response = []
        if result.get("success"):
            response.append("✅ Command executed successfully")
        else:
            response.append("⚠️ Command failed")
        response.append(f"**Return code:** {result.get('return_code')}")
        if result.get("stdout"):
            response.append(f"**Stdout:**\n```\n{result['stdout'][:1000]}\n```")
        if result.get("stderr"):
            response.append(f"**Stderr:**\n```\n{result['stderr'][:1000]}\n```")
        return "\n\n".join(response)

    def _handle_files(self, args: str, context: CommandContext) -> str:
        """List or read files.

        Args:
            args: File path to read, or empty to list all files.
            context: Command execution context.

        Returns:
            File listing or file content message.
        """
        if (pc := context.pc_client) is None:
            return "❌ PC client not available"
        if not args:
            # List all files
            files = pc.list_files()
            if not files:
                return "📁 No files in PC storage"
            file_list = []
            for f in files:
                file_list.append(f"  • {f['name']} ({f['type']}, {f['size']} bytes)")
            return "📁 Files in PC storage:\n" + "\n".join(file_list)
        else:
            # Read specific file
            path = args.split()[0]
            content = pc.read_file(path)
            return f"📄 **File:** {path}\n```\n{content[:2000]}\n```"

    def _handle_python(self, args: str, context: CommandContext) -> str:
        """Run Python script.

        Args:
            args: Python script to execute.
            context: Command execution context.

        Returns:
            Script execution result message.
        """
        if (pc := context.pc_client) is None:
            return "❌ PC client not available"
        if not args:
            return "❌ Usage: `/pc python <python script>`"

        result = pc.run_python_script(args)
        response = []
        if result.get("success"):
            response.append("✅ Python script executed successfully")
        else:
            response.append("⚠️ Script failed")
        response.append(f"**Return code:** {result.get('return_code')}")
        if result.get("stdout"):
            response.append(f"**Output:**\n```\n{result['stdout'][:1000]}\n```")
        if result.get("stderr"):
            response.append(f"**Errors:**\n```\n{result['stderr'][:1000]}\n```")
        return "\n\n".join(response)

    def _handle_write(self, args: str, context: CommandContext) -> str:
        """Write file.

        Args:
            args: File path and content separated by space.
            context: Command execution context.

        Returns:
            Success or error message for the write operation.
        """
        if (pc := context.pc_client) is None:
            return "❌ PC client not available"
        parts = args.split(None, 1)
        if len(parts) < 2:
            return "❌ Usage: `/pc write <path> <content>`"

        path = parts[0]
        content = parts[1]
        result = pc.write_file(path, content)
        if result.get("success"):
            return f"✅ File written: {path} ({result.get('size', 0)} bytes)"
        else:
            return f"❌ Failed to write file: {result.get('error', 'Unknown error')}"

    def _handle_rotate_key(self, args: str, context: CommandContext) -> str:
        """Generate new API key.

        Args:
            args: Command arguments (unused).
            context: Command execution context.

        Returns:
            New API key information message.
        """
        if (pc := context.pc_client) is None:
            return "❌ PC client not available"
        result = pc.rotate_key()
        if result.get("success"):
            new_key = result.get("new_key", "")
            total_keys = result.get("total_keys", 0)
            return (
                f"✅ New API key generated!\n\n"
                f"**New Key:** `{new_key}`\n\n"
                f"⚠️ **IMPORTANT:** Save this key immediately. It will not be shown again.\n"
                f"Update `PC_API_KEY` in your environment variables and restart bot containers.\n"
                f"Total active keys: {total_keys}"
            )
        else:
            return f"❌ Failed to rotate key: {result.get('error', 'Unknown error')}"

    def _handle_keys(self, args: str, context: CommandContext) -> str:
        """List masked API keys.

        Args:
            args: Command arguments (unused).
            context: Command execution context.

        Returns:
            List of masked API keys.
        """
        if (pc := context.pc_client) is None:
            return "❌ PC client not available"
        result = pc.list_keys()
        keys = result.get("keys", [])
        count = result.get("count", 0)
        if count == 0:
            return "🔑 No API keys configured. Use `/pc rotate-key` to generate one."
        key_list = "\n".join([f"  • `{key}`" for key in keys])
        return f"🔑 Active API keys ({count}):\n{key_list}"

    def _handle_audit_logs(self, args: str, context: CommandContext) -> str:
        """View security audit logs.

        Args:
            args: Optional limit for number of logs to display.
            context: Command execution context.

        Returns:
            Formatted audit logs.
        """
        if (pc := context.pc_client) is None:
            return "❌ PC client not available"
        limit = 50
        if args:
            try:
                limit = int(args.split()[0])
                if limit <= 0 or limit > 1000:
                    limit = 50
            except ValueError:
                pass

        result = pc.get_audit_logs(limit)
        logs = result.get("logs", [])
        count = result.get("count", 0)
        if count == 0:
            return "📊 No audit logs found."

        # Format logs for display
        log_entries = []
        for log in logs:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(log.get("timestamp", 0)))
            event_type = log.get("event_type", "unknown")
            user = log.get("user", "unknown")
            success = "✅" if log.get("success") else "❌"
            command = log.get("command", "")
            if command:
                command = f" - `{command[:50]}{'...' if len(command) > 50 else ''}`"
            log_entries.append(f"{success} **{timestamp}** - {event_type} by {user}{command}")

        return f"📊 Audit logs (showing {len(log_entries)} of {count}):\n\n" + "\n".join(
            log_entries
        )
