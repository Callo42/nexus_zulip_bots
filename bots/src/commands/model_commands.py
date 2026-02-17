"""Model management commands.

Commands for listing and viewing model configurations.
"""

import logging

from .base import BaseCommand, CommandContext

logger = logging.getLogger(__name__)


class ModelCommand(BaseCommand):
    """List models or view model details."""

    name = "model"
    description = "List models or view model details"

    def _list_models(self, context: CommandContext) -> str:
        """List all available models."""
        try:
            model_registry = context.policy_engine.model_registry
            models = model_registry.list_models()

            if not models:
                return "ℹ️ No models configured in models.yml"

            response = "**Available Models:**\n\n"
            for name, description in sorted(models.items()):
                response += f"• **{name}** - {description}\n"

            response += (
                "\nUse `/model <model-name>` for details, or set in policy with "
                "`/policy #channel <policy-name>`"
            )
            return response

        except AttributeError:
            return "ℹ️ Model registry not available. Check models.yml configuration."

    def _format_default_params(self, params: dict) -> str:
        """Format default parameters section.

        Args:
            params: Dictionary of default parameters

        Returns:
            Formatted string
        """
        if not params:
            return ""
        lines = ["**Default Parameters:**"]
        for key, value in params.items():
            lines.append(f"• {key}: {value}")
        return "\n".join(lines) + "\n"

    def _format_formatting_rules(self, formatting: dict) -> str:
        """Format formatting rules section.

        Args:
            formatting: Dictionary of formatting rules

        Returns:
            Formatted string
        """
        if not formatting:
            return ""
        lines = ["\n**Formatting Rules:**"]
        for field, rule in formatting.items():
            if rule.get("enabled", False):
                line = f"• {field}: {rule.get('format', 'plain')}"
                if "header" in rule:
                    line += f" (header: {rule['header']})"
                lines.append(line)
        return "\n".join(lines) + "\n"

    def _show_model_details(self, model_name: str, context: CommandContext) -> str:
        """Show details for a specific model."""
        try:
            model_registry = context.policy_engine.model_registry
            model_config = model_registry.get_model_config(model_name)

            if not model_config:
                return f"❌ Model '{model_name}' not found in registry."

            lines = [
                f"**Model: {model_name}**",
                f"Description: {model_config.get('description', 'No description')}",
                "",
            ]

            # Default parameters
            lines.append(self._format_default_params(model_config.get("default_params", {})))

            # Formatting rules
            lines.append(self._format_formatting_rules(model_config.get("formatting", {})))

            return "".join(lines)

        except AttributeError:
            return f"ℹ️ Model details not available. Check models.yml for '{model_name}'."

    def execute(self, args: str, context: CommandContext) -> str:
        """Handle /model [model-name] command.

        Args:
            args: Optional model name
            context: Command execution context

        Returns:
            Model list or details
        """
        model_name = args.strip()

        if not model_name:
            # List all available models
            return self._list_models(context)

        # Special case: 'storage' subcommand
        if model_name == "storage":
            return self._handle_storage(context)

        # Show model details
        return self._show_model_details(model_name, context)

    def _format_storage_models(self, models: dict) -> str:
        """Format models list section for storage display.

        Args:
            models: Dictionary of model names and descriptions

        Returns:
            Formatted string
        """
        if not models:
            return ""
        lines = ["**Configured Models:**"]
        for name, desc in sorted(models.items()):
            lines.append(f"  • `{name}` - {desc}")
        return "\n".join(lines) + "\n\n"

    def _format_storage_formatting(self, formatting: dict) -> str:
        """Format default formatting rules section.

        Args:
            formatting: Dictionary of formatting rules

        Returns:
            Formatted string
        """
        if not formatting:
            return ""
        lines = ["**Default Formatting Rules:**"]
        for key, value in formatting.items():
            lines.append(f"  • {key}: {value}")
        return "\n".join(lines) + "\n\n"

    def _format_storage_raw_content(self, content: str) -> str:
        """Format raw configuration content section.

        Args:
            content: Raw configuration content

        Returns:
            Formatted string
        """
        if not content:
            return ""
        if len(content) > 1500:
            content = content[:1500] + "\n... (truncated)"
        return f"**Raw Configuration:**\n```yaml\n{content}\n```"

    def _handle_storage(self, context: CommandContext) -> str:
        """Handle /model storage command."""
        try:
            model_registry = context.policy_engine.model_registry
            storage_info = model_registry.get_storage_info()

            lines = [
                "📦 **Model Registry Storage**",
                "",
                f"Config Path: `{storage_info['config_path']}`",
                f"Config Exists: {'✅' if storage_info['config_exists'] else '❌'}",
                f"Model Count: **{storage_info['model_count']}**",
                "",
            ]

            # Show model list
            lines.append(self._format_storage_models(storage_info.get("models", {})))

            # Show default formatting
            lines.append(
                self._format_storage_formatting(storage_info.get("default_formatting", {}))
            )

            # Show raw content
            lines.append(self._format_storage_raw_content(storage_info.get("raw_content", "")))

            return "".join(lines)

        except AttributeError:
            return "❌ Model registry not available. Check models.yml configuration."
        except Exception as e:
            logger.error(f"Failed to get model storage info: {e}", exc_info=True)
            return f"❌ Failed to get model storage info: {str(e)}"
