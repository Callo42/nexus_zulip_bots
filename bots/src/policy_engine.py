"""Manages bot policies and configurations."""

import json
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import yaml

from .model_registry import ModelRegistry

if TYPE_CHECKING:
    from .formatters import ModelFormatter

logger = logging.getLogger(__name__)


class PolicyEngine:
    """Handles policy configuration and assignment."""

    def __init__(self, config_path: str, model_registry: Optional[ModelRegistry] = None):
        """Initialize policy engine.

        Args:
            config_path: Path to policies.yml configuration file
            model_registry: Optional model registry for model configurations
        """
        self.config_path = config_path
        self.policies: Dict[str, Any] = {}
        self.default_policy: Optional[str] = None
        self.stream_policies: Dict[str, str] = {}  # stream_name -> policy_name
        self.admin_dm_policies: Dict[str, str] = {}  # admin_email -> policy_name
        self.state_file = config_path.replace("policies.yml", "state.json")

        # Model registry for model parameters and formatting
        if model_registry is None:
            config_dir = "/".join(config_path.split("/")[:-1])
            self.model_registry = ModelRegistry(config_dir)
        else:
            self.model_registry = model_registry

        self.reload_policies()
        self._load_state()

    def reload_policies(self) -> None:
        """Reload policies from YAML file.

        Returns:
            None

        Raises:
            Exception: If failed to load policies from file.
        """
        try:
            with open(self.config_path, "r") as f:
                config = yaml.safe_load(f)
                self.policies = config.get("policies", {})
                self.default_policy = config.get("default_policy", "pc-enabled")
                logger.info(f"Loaded {len(self.policies)} policies")
        except Exception as e:
            logger.error(f"Failed to load policies: {e}", exc_info=True)
            # Set minimal default
            self.policies = {
                "default": {
                    "description": "Default policy",
                    "system_prompt": "You are a helpful assistant.",
                    "model": "gpt-4o",  # Will be resolved via model registry
                    "triggers": {"mention_required": True, "keywords": []},
                }
            }
            self.default_policy = "default"

    def _load_state(self) -> None:
        """Load all state mappings from state file.

        Raises:
            FileNotFoundError: If state file does not exist.
            json.JSONDecodeError: If state file contains invalid JSON.
        """
        try:
            with open(self.state_file, "r") as f:
                state = json.load(f)
                self.stream_policies = state.get("stream_policies", {})
                self.admin_dm_policies = state.get("admin_dm_policies", {})

                # Migrate helpful-assistant to pc-enabled
                for stream, policy in list(self.stream_policies.items()):
                    if policy == "helpful-assistant":
                        self.stream_policies[stream] = "pc-enabled"
                        logger.info(
                            f"Migrated stream '{stream}' policy from "
                            f"'helpful-assistant' to 'pc-enabled'"
                        )

                for admin, policy in list(self.admin_dm_policies.items()):
                    if policy == "helpful-assistant":
                        self.admin_dm_policies[admin] = "pc-enabled"
                        logger.info(
                            f"Migrated admin DM policy for '{admin}' from "
                            f"'helpful-assistant' to 'pc-enabled'"
                        )

                # Save migrated state if changes were made
                if (
                    state.get("stream_policies") != self.stream_policies
                    or state.get("admin_dm_policies") != self.admin_dm_policies
                ):
                    self._save_state()

        except FileNotFoundError:
            self.stream_policies = {}
            self.admin_dm_policies = {}

    def _save_state(self) -> None:
        """Save all state mappings to state file.

        Raises:
            Exception: If failed to write state to file.
        """
        try:
            # Load existing state
            try:
                with open(self.state_file, "r") as f:
                    state = json.load(f)
            except FileNotFoundError:
                state = {}

            # Update all state sections
            state["stream_policies"] = self.stream_policies
            state["admin_dm_policies"] = self.admin_dm_policies

            # Save
            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def _get_model_name(self, policy: Dict[str, Any], policy_name: str) -> str:
        """Get model name from policy with fallback to default.

        Args:
            policy: Policy dictionary
            policy_name: Name of the policy

        Returns:
            Model name string
        """
        model_name = policy.get("model")
        if not model_name:
            logger.warning(f"Policy '{policy_name}' has no model specified, using default")
            model_name = "gpt-4o"
        return model_name

    def _merge_model_params(self, policy: Dict[str, Any], model_name: str) -> None:
        """Merge model parameters from registry into policy.

        Args:
            policy: Policy dictionary to modify
            model_name: Name of the model
        """
        model_params = self.model_registry.get_model_params(
            model_name,
            override_params={k: v for k, v in policy.items() if k in ["temperature", "max_tokens"]},
        )

        for key, value in model_params.items():
            if key != "model" and key not in policy:
                policy[key] = value

    def _apply_memory_defaults(self, policy: Dict[str, Any]) -> None:
        """Apply default memory configuration to policy.

        Args:
            policy: Policy dictionary to modify
        """
        if "memory" not in policy:
            policy["memory"] = {}

        if "enabled" not in policy["memory"]:
            policy["memory"]["enabled"] = True
        if "lookback_messages" not in policy["memory"]:
            policy["memory"]["lookback_messages"] = 100

    def _apply_tools_defaults(self, policy: Dict[str, Any]) -> None:
        """Apply default tools configuration to policy.

        Args:
            policy: Policy dictionary to modify
        """
        if "tools" not in policy:
            policy["tools"] = {}

        tools_defaults: Dict[str, Any] = {
            "enabled": True,
            "granularity": "fine",
            "max_iterations": 10,
            "allowed_tools": [
                "list_files",
                "read_file",
                "execute_command",
                "get_system_info",
                "check_disk_space",
            ],
            "dangerous_tools": [],
            "auto_detect": True,
        }

        for key, default in tools_defaults.items():
            if key not in policy["tools"]:
                policy["tools"][key] = default

    def get_policy(self, policy_name: str) -> Optional[Dict[str, Any]]:
        """Get policy configuration by name with defaults.

        Args:
            policy_name: Name of the policy to retrieve.

        Returns:
            Policy configuration dict with defaults applied, or None if not found.
        """
        policy_raw = self.policies.get(policy_name)
        if not policy_raw:
            return None

        policy: Dict[str, Any] = dict(policy_raw)

        model_name = self._get_model_name(policy, policy_name)
        self._merge_model_params(policy, model_name)
        self._apply_memory_defaults(policy)
        self._apply_tools_defaults(policy)

        if "context" not in policy:
            policy["context"] = {}

        return policy

    def policy_exists(self, policy_name: str) -> bool:
        """Check if policy exists.

        Args:
            policy_name: Name of the policy to check.

        Returns:
            True if the policy exists, False otherwise.
        """
        return policy_name in self.policies

    def list_policies(self) -> List[str]:
        """List all available policy names.

        Returns:
            List of policy names.
        """
        return list(self.policies.keys())

    def set_policy_for_stream(self, stream_name: str, policy_name: str) -> None:
        """Assign a policy to a stream.

        Args:
            stream_name: Name of the stream to assign policy to.
            policy_name: Name of the policy to assign.

        Returns:
            None

        Raises:
            ValueError: If the policy does not exist.
        """
        if not self.policy_exists(policy_name):
            raise ValueError(f"Policy '{policy_name}' does not exist")

        self.stream_policies[stream_name] = policy_name
        self._save_state()
        logger.info(f"Set policy '{policy_name}' for stream '{stream_name}'")

    def get_policy_for_stream(self, stream_name: str) -> Optional[Dict[str, Any]]:
        """Get the policy configuration for a stream.

        Args:
            stream_name: Name of the stream to get policy for.

        Returns:
            Policy configuration dict, or None if not found.
        """
        policy_name = self.stream_policies.get(stream_name, self.default_policy)
        if policy_name is None:
            return None
        return self.get_policy(policy_name)

    def get_policy_name_for_stream(self, stream_name: str) -> Optional[str]:
        """Get the policy name assigned to a stream.

        Args:
            stream_name: Name of the stream to get policy name for.

        Returns:
            Name of the assigned policy, or None if not set.
        """
        return self.stream_policies.get(stream_name)

    def remove_policy_for_stream(self, stream_name: str) -> None:
        """Remove policy assignment for a stream.

        Args:
            stream_name: Name of the stream to remove policy from.

        Returns:
            None
        """
        if stream_name in self.stream_policies:
            del self.stream_policies[stream_name]
            self._save_state()
            logger.info(f"Removed policy for stream '{stream_name}'")

    def set_policy_for_admin_dm(self, admin_email: str, policy_name: str) -> None:
        """Assign a policy to an admin's DM conversations.

        Args:
            admin_email: Email address of the admin.
            policy_name: Name of the policy to assign.

        Returns:
            None

        Raises:
            ValueError: If the policy does not exist.
        """
        if not self.policy_exists(policy_name):
            raise ValueError(f"Policy '{policy_name}' does not exist")

        self.admin_dm_policies[admin_email] = policy_name
        self._save_state()
        logger.info(f"Set DM policy '{policy_name}' for admin '{admin_email}'")

    def get_policy_for_admin_dm(self, admin_email: str) -> Optional[Dict[str, Any]]:
        """Get the policy configuration for an admin's DM conversations.

        Args:
            admin_email: Email address of the admin.

        Returns:
            Policy configuration dict for admin DMs.
        """
        # Default to 'pc-enabled' if not set
        policy_name = self.admin_dm_policies.get(admin_email, "pc-enabled")
        return self.get_policy(policy_name)

    def get_policy_name_for_admin_dm(self, admin_email: str) -> Optional[str]:
        """Get the policy name assigned to an admin's DM conversations.

        Args:
            admin_email: Email address of the admin.

        Returns:
            Name of the assigned policy, or None if not set.
        """
        return self.admin_dm_policies.get(admin_email)

    def remove_policy_for_admin_dm(self, admin_email: str) -> None:
        """Remove policy assignment for an admin's DM conversations.

        Args:
            admin_email: Email address of the admin.

        Returns:
            None
        """
        if admin_email in self.admin_dm_policies:
            del self.admin_dm_policies[admin_email]
            self._save_state()
            logger.info(f"Removed DM policy for admin '{admin_email}'")

    def get_model_config(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific model from registry.

        Args:
            model_name: Name of the model to get configuration for.

        Returns:
            Model configuration dict, or None if not found.
        """
        result: Optional[Dict[str, Any]] = self.model_registry.get_model_config(model_name)
        return result

    def get_formatter(self, model_name: str) -> Optional["ModelFormatter"]:
        """Get formatter for a model.

        Args:
            model_name: Name of the model to get formatter for.

        Returns:
            ModelFormatter instance, or None if not found.
        """
        from .formatters import get_formatter

        # Load models config directly from registry
        models_config = {
            "models": self.model_registry.models_config.get("models", {}),
            "default_formatting": self.model_registry.get_default_formatting(),
        }
        return get_formatter(model_name, models_config)

    def get_lookback_for_stream(self, stream_name: str) -> int:
        """Get the lookback message count for a stream.

        Priority:
        1. Dynamic config from state.json (lookback_settings)
        2. Policy default from policies.yml (memory.lookback_messages, defaults to 100)
        3. Hardcoded fallback (100)

        Args:
            stream_name: Name of the stream to get lookback for.

        Returns:
            Number of messages to look back.
        """
        # 1. Check dynamic config from state
        try:
            with open(self.state_file, "r") as f:
                state = json.load(f)
                lookback_settings = state.get("lookback_settings", {})
                if stream_name in lookback_settings:
                    lookback = lookback_settings[stream_name]
                    if isinstance(lookback, dict):
                        # Legacy format with topic support (not used anymore)
                        lookback = lookback.get("default", 100)
                    if isinstance(lookback, int) and lookback > 0:
                        return lookback
        except (FileNotFoundError, json.JSONDecodeError):
            pass

        # 2. Get from current policy
        policy = self.get_policy_for_stream(stream_name)
        if policy and "memory" in policy:
            lookback = policy["memory"].get("lookback_messages", 100)
            if isinstance(lookback, int) and lookback > 0:
                return lookback

        # 3. Fallback
        return 100

    def set_lookback_for_stream(self, stream_name: str, lookback_count: int) -> None:
        """Set the lookback message count for a stream in state.json.

        Args:
            stream_name: Stream/channel name.
            lookback_count: Number of messages to look back (must be positive).

        Returns:
            None

        Raises:
            ValueError: If lookback_count is not positive.
        """
        if not isinstance(lookback_count, int) or lookback_count <= 0:
            raise ValueError("Lookback count must be a positive integer")

        try:
            with open(self.state_file, "r") as f:
                state = json.load(f)
        except FileNotFoundError:
            state = {}

        if "lookback_settings" not in state:
            state["lookback_settings"] = {}

        state["lookback_settings"][stream_name] = lookback_count

        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=2)

        logger.info(f"Set lookback to {lookback_count} for stream '{stream_name}'")

    def reset_lookback_for_stream(self, stream_name: str) -> None:
        """Reset the lookback message count for a stream to policy default.

        Args:
            stream_name: Name of the stream to reset lookback for.

        Returns:
            None
        """
        try:
            with open(self.state_file, "r") as f:
                state = json.load(f)
        except FileNotFoundError:
            return  # Nothing to reset

        if "lookback_settings" in state and stream_name in state["lookback_settings"]:
            del state["lookback_settings"][stream_name]
            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=2)
            logger.info(f"Reset lookback for stream '{stream_name}' to policy default")

    def get_lookback_for_dm(self, admin_email: str) -> int:
        """Get the lookback message count for a DM conversation.

        Priority:
        1. Dynamic config from state.json (dm_lookback_settings)
        2. Policy default from policies.yml (memory.lookback_messages, defaults to 100)
        3. Hardcoded fallback (100)

        Args:
            admin_email: Admin email address for DM conversation.

        Returns:
            Number of messages to look back (defaults to 100).
        """
        # 1. Check dynamic config from state
        try:
            with open(self.state_file, "r") as f:
                state = json.load(f)
                dm_lookback_settings = state.get("dm_lookback_settings", {})
                if admin_email in dm_lookback_settings:
                    lookback = dm_lookback_settings[admin_email]
                    if isinstance(lookback, int) and lookback > 0:
                        return lookback
        except (FileNotFoundError, json.JSONDecodeError):
            pass

        # 2. Get from current DM policy
        policy = self.get_policy_for_admin_dm(admin_email)
        if policy and "memory" in policy:
            lookback = policy["memory"].get("lookback_messages", 100)
            if isinstance(lookback, int) and lookback > 0:
                return lookback

        # 3. Fallback
        return 100

    def set_lookback_for_dm(self, admin_email: str, lookback_count: int) -> None:
        """Set the lookback message count for a DM conversation in state.json.

        Args:
            admin_email: Admin email address for DM conversation.
            lookback_count: Number of messages to look back (must be positive).

        Returns:
            None

        Raises:
            ValueError: If lookback_count is not positive.
        """
        if not isinstance(lookback_count, int) or lookback_count <= 0:
            raise ValueError("Lookback count must be a positive integer")

        try:
            with open(self.state_file, "r") as f:
                state = json.load(f)
        except FileNotFoundError:
            state = {}

        if "dm_lookback_settings" not in state:
            state["dm_lookback_settings"] = {}

        state["dm_lookback_settings"][admin_email] = lookback_count

        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=2)

        logger.info(f"Set lookback to {lookback_count} for DM with '{admin_email}'")

    def reset_lookback_for_dm(self, admin_email: str) -> None:
        """Reset the lookback message count for a DM conversation to policy default.

        Args:
            admin_email: Admin email address for DM conversation.

        Returns:
            None
        """
        try:
            with open(self.state_file, "r") as f:
                state = json.load(f)
        except FileNotFoundError:
            return  # Nothing to reset

        if "dm_lookback_settings" in state and admin_email in state["dm_lookback_settings"]:
            del state["dm_lookback_settings"][admin_email]
            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=2)
            logger.info(f"Reset lookback for DM with '{admin_email}' to policy default")
