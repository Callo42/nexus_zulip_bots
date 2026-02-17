#!/usr/bin/env python3
"""PC API Server for bot sidecar.

Entry point for the PC sidecar API server.
Initializes managers and creates Flask application using blueprint architecture.

Refactored to use modular routes package with:
- health: Health check endpoint
- tools: Tool listing and OpenAI-compatible endpoints
- commands: Shell command execution
- files: File management
- history: Conversation history storage
- keys: API key management and audit logs

Example:
    PC_API_KEY=secret python api.py
"""

import logging
import os
from pathlib import Path

from pc_server.history_manager import HistoryManager
from pc_server.pc_manager import PCManager
from pc_server.routes import create_app
from pc_server.tool_manager import ToolManager

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Start PC API server."""
    pc_root = Path(os.getenv("PC_ROOT", "/pc"))

    (pc_root / "files").mkdir(parents=True, exist_ok=True)
    (pc_root / "history").mkdir(parents=True, exist_ok=True)
    (pc_root / "logs").mkdir(parents=True, exist_ok=True)
    (pc_root / "keys").mkdir(parents=True, exist_ok=True)

    logger.info("Initializing PC managers...")
    pc_manager = PCManager(str(pc_root))
    history_manager = HistoryManager(str(pc_root))
    tool_manager = ToolManager(pc_manager, history_manager)

    logger.info(f"PC Root: {pc_root}")
    logger.info(f"Files directory: {pc_manager.files_dir}")
    logger.info(f"History directory: {history_manager.history_dir}")

    app = create_app(pc_manager, history_manager, tool_manager)

    host = os.getenv("PC_HOST", "0.0.0.0")  # nosec B104
    port = int(os.getenv("PC_PORT", "8080"))

    logger.info(f"PC API starting on {host}:{port}")
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
