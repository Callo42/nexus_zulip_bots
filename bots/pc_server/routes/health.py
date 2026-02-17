"""Health check routes for PC API.

Provides simple health check endpoint for monitoring.
"""

import logging

from flask import Blueprint, jsonify

logger = logging.getLogger(__name__)

# Create blueprint
bp = Blueprint("health", __name__)


@bp.route("/health", methods=["GET"])
def health():
    """Health check endpoint.

    Returns:
        JSON with status 'healthy'
    """
    return jsonify({"status": "healthy"})
