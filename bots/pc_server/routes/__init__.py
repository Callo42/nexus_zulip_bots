"""PC API routes package.

Provides Flask blueprint organization for PC sidecar API.
All routes are registered through create_app() factory function.

Example:
    from routes import create_app

    app = create_app(pc_manager, history_manager, tool_manager)
    app.run(host='0.0.0.0', port=5000)
"""

import os
from pathlib import Path

from flask import Flask
from flask_cors import CORS

from . import commands, files, health, history, keys, tools
from .auth import AuthManager


def create_app(pc_manager, history_manager, tool_manager):
    """Create and configure Flask application.

    Factory function that initializes the Flask app with all blueprints
    and shared resources.

    Args:
        pc_manager: PCManager instance for file/command operations
        history_manager: HistoryManager instance for history operations
        tool_manager: ToolManager instance for tool execution

    Returns:
        Configured Flask application instance
    """
    app = Flask(__name__)
    CORS(app)

    pc_root = Path(pc_manager.root)
    keys_file = pc_root / "keys" / "valid_keys.json"
    audit_log_file = pc_root / "logs" / "audit.log"
    legacy_api_key = os.getenv("PC_API_KEY", "")

    auth_manager = AuthManager(keys_file, audit_log_file, legacy_api_key)

    app.pc_manager = pc_manager
    app.history_manager = history_manager
    app.tool_manager = tool_manager
    app.auth_manager = auth_manager

    app.register_blueprint(health.bp)
    app.register_blueprint(tools.bp)
    app.register_blueprint(commands.bp)
    app.register_blueprint(files.bp)
    app.register_blueprint(history.bp)
    app.register_blueprint(keys.bp)

    @app.before_request
    def authenticate():
        """Authenticate requests before processing.

        Skips authentication for health checks.
        Validates API key from X-API-Key header.

        Returns:
            None if authentication succeeds, or a tuple of (error dict, status code) if failed
        """
        from flask import g, request

        if request.path == "/health":
            return

        api_key = request.headers.get("X-API-Key", "")

        if not auth_manager.validate_api_key(api_key):
            return {"error": "Unauthorized - invalid API key"}, 401

        g.user = api_key[:8] + "..." if api_key else "anonymous"

    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 not found errors.

        Args:
            error: The error that triggered this handler

        Returns:
            JSON response with error message and 404 status
        """
        return {"error": "Not found"}, 404

    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 internal server errors.

        Args:
            error: The error that triggered this handler

        Returns:
            JSON response with error message and 500 status
        """
        return {"error": "Internal server error"}, 500

    return app
