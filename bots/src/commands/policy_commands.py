"""Policy configuration commands.

Commands for managing and viewing policies for channels and DM conversations.
"""

import logging
import re

import yaml

from .base import BaseCommand, CommandContext

logger = logging.getLogger(__name__)


class PolicyCommand(BaseCommand):
    """Set or view policy for a channel."""

    name = "policy"
    description = "Set or view policy for a channel"

    def execute(self, args: str, context: CommandContext) -> str:
        """Handle /policy #channel [policy-name|show] command.

        Args:
            args: #channel-name [policy-name|show]
            context: Command execution context

        Returns:
            Response message
        """
        # Parse: /policy #channel-name policy-name
        # Or: /policy #channel-name show
        match = re.search(r"#?(\S+)(?:\s+(\S+))?", args.strip())
        if not match:
            return "❌ Usage: `/policy #channel-name [policy-name|show]`"

        stream_name = match.group(1).strip().lstrip("#")
        action = match.group(2)

        if not action:
            return "❌ Usage: `/policy #channel-name [policy-name|show]`"

        # Show current policy
        if action == "show":
            current_policy = context.policy_engine.get_policy_for_stream(stream_name)
            if current_policy:
                policy_name = context.policy_engine.get_policy_name_for_stream(stream_name)
                yaml_content = yaml.dump(current_policy, default_flow_style=False)
                return (
                    f"📋 Current policy for #{stream_name}: **{policy_name}**\n\n"
                    f"```yaml\n{yaml_content}```"
                )
            else:
                return f"ℹ️ No policy set for #{stream_name}"

        # Set policy
        policy_name = action

        # Validate policy exists
        if not context.policy_engine.policy_exists(policy_name):
            available = ", ".join(context.policy_engine.list_policies())
            return f"❌ Policy '{policy_name}' not found.\n\nAvailable policies: {available}"

        # Set the policy
        context.policy_engine.set_policy_for_stream(stream_name, policy_name)

        policy_config = context.policy_engine.get_policy(policy_name)
        if policy_config is None:
            return (
                f"✅ Set policy **{policy_name}** for #{stream_name}\n\n"
                f"📝 No description available"
            )
        description = policy_config.get("description", "No description")
        return f"✅ Set policy **{policy_name}** for #{stream_name}\n\n📝 {description}"


class ListPoliciesCommand(BaseCommand):
    """List all available policies."""

    name = "policies"
    description = "List all available policies"

    def execute(self, args: str, context: CommandContext) -> str:
        """Handle /policies command.

        Args:
            args: Empty (no arguments)
            context: Command execution context

        Returns:
            Formatted policy list
        """
        try:
            policies = context.policy_engine.list_policies()
            if not policies:
                return "ℹ️ No policies configured. Add policies to `/app/config/policies.yml`"

            policy_details = []
            for policy_name in sorted(policies):
                policy_config = context.policy_engine.get_policy(policy_name)
                if policy_config:
                    description = policy_config.get("description", "No description")
                    model = policy_config.get("model", "default")
                    temp = policy_config.get("temperature", 0.7)
                    policy_details.append(
                        f"**{policy_name}**\n"
                        f"  • Model: `{model}`\n"
                        f"  • Temperature: `{temp}`\n"
                        f"  • Description: {description}\n"
                    )

            return f"📋 **Available Policies** ({len(policies)}):\n\n" + "\n".join(policy_details)
        except Exception as e:
            logger.error(f"Failed to list policies: {e}", exc_info=True)
            return f"❌ Failed to list policies: {str(e)}"


class DmPolicyCommand(BaseCommand):
    """Set or view policy for DM conversations."""

    name = "dm-policy"
    description = "Set or view policy for your DM conversations"

    def execute(self, args: str, context: CommandContext) -> str:
        """Handle /dm-policy [policy-name|show] command.

        Args:
            args: [policy-name|show]
            context: Command execution context

        Returns:
            Response message
        """
        action = args.strip()
        sender_email = context.sender_email

        # Show current policy if no action or 'show'
        if not action or action == "show":
            current_policy = context.policy_engine.get_policy_for_admin_dm(sender_email)
            current_policy_name = (
                context.policy_engine.get_policy_name_for_admin_dm(sender_email)
                or "pc-enabled (default)"
            )

            if current_policy:
                yaml_content = yaml.dump(current_policy, default_flow_style=False)
                return (
                    f"📋 Current DM policy for {sender_email}: "
                    f"**{current_policy_name}**\n\n"
                    f"```yaml\n{yaml_content}```"
                )
            else:
                return f"ℹ️ Using default DM policy for {sender_email}: **pc-enabled**"

        # Set policy
        policy_name = action

        # Validate policy exists
        if not context.policy_engine.policy_exists(policy_name):
            available = ", ".join(context.policy_engine.list_policies())
            return f"❌ Policy '{policy_name}' not found.\n\nAvailable policies: {available}"

        # Set the policy
        try:
            context.policy_engine.set_policy_for_admin_dm(sender_email, policy_name)
            policy_config = context.policy_engine.get_policy(policy_name)
            if policy_config is None:
                return (
                    f"✅ Set DM policy **{policy_name}** for {sender_email}\n\n"
                    f"📝 No description available"
                )
            description = policy_config.get("description", "No description")
            return f"✅ Set DM policy **{policy_name}** for {sender_email}\n\n" f"📝 {description}"
        except ValueError as e:
            return f"❌ {str(e)}"
        except Exception as e:
            logger.error(f"Failed to set DM policy: {e}", exc_info=True)
            return f"❌ Failed to set DM policy: {str(e)}"
