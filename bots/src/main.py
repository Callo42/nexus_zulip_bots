#!/usr/bin/env python3
"""Main entry point for Zulip LLM Bot.

This module handles bot initialization and the main event loop.
Components are initialized in a specific order to satisfy dependencies.

Initialization Order:
    1. PC Client (optional) - Provides memory and tool execution capabilities
    2. Policy Engine - Loads policies and model configurations
    3. LLM Client - Interfaces with LiteLLM, uses PC client for tools
    4. Admin Handler - Processes DM commands
    5. Zulip Handler - Main message processing loop

Component Dependencies:
    - PC Client: No dependencies (optional)
    - Policy Engine: No dependencies
    - LLM Client: Optional PC Client, optional Policy Engine
    - Admin Handler: Policy Engine, optional PC Client
    - Zulip Handler: LLM Client, Policy Engine, Admin Handler

Environment Variables:
    BOT_NAME: Bot identifier (default: 'bot')
    LITELLM_URL: LiteLLM API endpoint (default: 'http://litellm:4000')
    OLLAMA_URL: Ollama API endpoint (default: 'http://ollama:11434')
    LITELLM_MASTER_KEY: Authentication key for LiteLLM
    PC_API_URL: PC sidecar URL (optional)
    PC_API_KEY: PC sidecar authentication (optional)
    LOG_LEVEL: Logging level (default: 'INFO')

Example:
    Run the bot locally for development:

    $ export BOT_NAME=testbot1
    $ export LITELLM_URL=http://localhost:4000
    $ export LOG_LEVEL=DEBUG
    $ python -m src.main
"""

import logging
import os
import sys

from .admin_commands import AdminCommandHandler
from .llm_client import LLMClient
from .pc_client import get_pc_client
from .policy_engine import PolicyEngine
from .zulip_handler import ZulipHandler

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def main():
    """Initialize bot and start event loop.

    Initializes all components in dependency order and starts the Zulip
    message processing loop. The bot runs indefinitely until interrupted.

    Component Initialization:
        1. PC Client: Optional sidecar for memory/tools (requires PC_API_URL)
        2. Policy Engine: Loads policies from /app/config/policies.yml
        3. LLM Client: Connects to LiteLLM, uses PC client for tool calls
        4. Admin Handler: Processes DM commands (/join, /leave, etc.)
        5. Zulip Handler: Main message loop, routes to appropriate handlers

    Raises:
        SystemExit: On fatal initialization errors (exit code 1)

    Note:
        Gracefully handles KeyboardInterrupt for clean shutdown.
        All exceptions are logged with exc_info=True for debugging.
    """
    bot_name = os.getenv("BOT_NAME", "bot")
    logger.info(f"Starting Zulip LLM Bot: {bot_name}")

    try:
        # Initialize components
        logger.info("Initializing bot components...")

        # PC Client (optional sidecar) - must be initialized before LLM Client
        pc_client = get_pc_client()
        if pc_client:
            logger.info("PC sidecar client initialized")
        else:
            logger.info("PC sidecar not configured (set PC_API_URL)")

        # Policy Engine (needed for LLM Client formatting)
        policy_engine = PolicyEngine(config_path="/app/config/policies.yml")

        # LLM Client (with optional PC client for tool calls and policy engine for formatting)
        llm_client = LLMClient(
            litellm_url=os.getenv("LITELLM_URL", "http://litellm:4000"),
            ollama_url=os.getenv("OLLAMA_URL", "http://ollama:11434"),
            pc_client=pc_client,
            policy_engine=policy_engine,
        )

        # Admin Command Handler
        admin_handler = AdminCommandHandler(
            admins_file="/app/admins.yml",
            policy_engine=policy_engine,
            pc_client=pc_client,
        )

        # Zulip Handler
        zulip_handler = ZulipHandler(
            zuliprc_path="/app/zuliprc",
            config_path="/app/config",
            llm_client=llm_client,
            policy_engine=policy_engine,
            admin_handler=admin_handler,
        )

        logger.info("Bot initialized successfully")
        logger.info(f"Bot user: {zulip_handler.get_bot_email()}")
        logger.info("Waiting for messages...")

        # Start listening
        zulip_handler.start()

    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
