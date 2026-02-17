"""Model registry for loading and managing model configurations."""

import logging
import os
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Manages model configurations and provides model parameters."""

    def __init__(self, config_dir: str):
        """Initialize model registry.

        Args:
            config_dir: Directory containing models.yml configuration file.
        """
        self.config_dir = config_dir
        self.models_config: Dict[str, Any] = {}
        self._load_models()

    def _load_models(self) -> None:
        """Load models configuration from YAML file.

        Raises:
            Exception: If failed to load models configuration.
        """
        models_file = os.path.join(self.config_dir, "models.yml")

        if not os.path.exists(models_file):
            logger.warning(f"Models configuration not found at {models_file}, using defaults")
            self.models_config = self._get_default_config()
            return

        try:
            with open(models_file, "r") as f:
                self.models_config = yaml.safe_load(f) or {}
            model_count = len(self.models_config.get("models", {}))
            logger.info(f"Loaded {model_count} model configurations from {models_file}")
        except Exception as e:
            logger.error(f"Failed to load models configuration: {e}", exc_info=True)
            self.models_config = self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration when models.yml is missing."""
        return {
            "models": {
                "gpt-4o-mini": {
                    "description": "Default GPT-4o Mini",
                    "default_params": {"temperature": 0.7, "max_tokens": 500},
                    "formatting": {},
                }
            },
            "default_formatting": {
                "trim_whitespace": True,
                "markdown_code_blocks": True,
            },
        }

    def get_model_config(self, model_name: str) -> Optional[Dict[str, Any]]:
        """
        Get configuration for a specific model.

        Args:
            model_name: Name of the model

        Returns:
            Model configuration dict or None if not found
        """
        models = self.models_config.get("models", {})
        result: Optional[Dict[str, Any]] = models.get(model_name)
        return result

    def get_model_params(
        self, model_name: str, override_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get model parameters with optional overrides.

        Args:
            model_name: Name of the model
            override_params: Parameters to override model defaults

        Returns:
            Merged parameters dict
        """
        model_config = self.get_model_config(model_name)
        if not model_config:
            logger.warning(f"Model '{model_name}' not found, using default parameters")
            base_params = {"model": model_name, "temperature": 0.7, "max_tokens": 500}
        else:
            base_params = model_config.get("default_params", {}).copy()
            base_params["model"] = model_name

        # Apply overrides from policy
        if override_params:
            for key, value in override_params.items():
                if key not in ["model", "formatting", "description"]:
                    base_params[key] = value

        return base_params

    def get_default_formatting(self) -> Dict[str, Any]:
        """Get default formatting rules.

        Returns:
            Dict containing default formatting configuration.
        """
        result: Dict[str, Any] = self.models_config.get("default_formatting", {}).copy()
        return result

    def list_models(self) -> Dict[str, str]:
        """List all available models with descriptions.

        Returns:
            Dict mapping model names to their descriptions.
        """
        models = self.models_config.get("models", {})
        return {
            name: config.get("description", "No description") for name, config in models.items()
        }

    def model_exists(self, model_name: str) -> bool:
        """Check if a model exists in the registry.

        Args:
            model_name: Name of the model to check.

        Returns:
            True if model exists in registry, False otherwise.
        """
        models = self.models_config.get("models", {})
        return model_name in models

    def get_storage_info(self) -> Dict[str, Any]:
        """Get storage information for observability.

        Returns:
            Dict containing storage information including config path,
            model count, and raw configuration.
        """
        models_file = os.path.join(self.config_dir, "models.yml")

        info = {
            "config_path": models_file,
            "config_exists": os.path.exists(models_file),
            "model_count": 0,
            "models": {},
            "default_formatting": {},
            "raw_content": None,
        }

        # Get model summary
        models = self.list_models()
        info["model_count"] = len(models)
        info["models"] = models

        # Get default formatting
        info["default_formatting"] = self.get_default_formatting()

        # Load raw content if file exists
        if info["config_exists"]:
            try:
                with open(models_file, "r") as f:
                    info["raw_content"] = f.read()
            except Exception as e:
                logger.error(f"Failed to read models.yml: {e}")
                info["raw_content"] = f"Error reading file: {e}"

        return info
