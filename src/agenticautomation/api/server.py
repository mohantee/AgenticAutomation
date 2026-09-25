"""Flask REST API + static UI server for AgenticAutomation.

Endpoints:
  GET  /api/workflows           — List all workflow runs
  GET  /api/workflows/<id>      — Workflow detail with steps
  GET  /api/workflows/<id>/object — Extracted object JSON
  POST /api/trigger             — Manually trigger processing (dev/testing)

Static:
  /  — Serves the ui/ directory as the dashboard SPA
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from agenticautomation.config import config
from agenticautomation.processor.trigger import simulate_trigger
from agenticautomation.storage.store import get_store

logger = logging.getLogger(__name__)


def find_ui_dir() -> Path:
    """Locate the ui/ directory across development and Docker container environments."""
    candidates = [
        Path.cwd() / "ui",                           # Docker container: /app/ui (WORKDIR is /app)
        Path("/app/ui"),                             # Explicit Docker container path
        Path(__file__).resolve().parents[3] / "ui",  # Local repo development: root/ui
        Path(__file__).resolve().parents[2] / "ui",  # Editable install
    ]
    for candidate in candidates:
        if candidate.is_dir() and (candidate / "index.html").exists():
            return candidate
    return Path.cwd() / "ui"


def create_app() -> Flask:
    """Create and configure the Flask application."""
    ui_dir = find_ui_dir()
    logger.info("Using UI directory: %s", ui_dir)

    app = Flask(__name__, static_folder=str(ui_dir), static_url_path="")
    CORS(app)

    # --- Health Check (for ALB / ECS) ---

    @app.route("/health", methods=["GET"])
    def health_check():
        """Health check endpoint for ALB target group."""
        return jsonify({"status": "healthy", "service": "agenticautomation"}), 200

    # --- API Routes ---

    @app.route("/api/workflows", methods=["GET"])
    def list_workflows():
        """Return all workflow summaries."""
        store = get_store()
        workflows = store.list_workflows()
        # Sort by created_at descending (newest first)
        workflows.sort(key=lambda w: w.get("created_at", ""), reverse=True)
        return jsonify(workflows)

    @app.route("/api/workflows/<workflow_id>", methods=["GET"])
    def get_workflow(workflow_id: str):
        """Return workflow detail with steps."""
        store = get_store()
        workflow = store.get_workflow(workflow_id)
        if workflow is None:
            return jsonify({"error": "Workflow not found"}), 404

        steps = store.get_steps(workflow_id)
        return jsonify({"workflow": workflow, "steps": steps})

    @app.route("/api/workflows/<workflow_id>/object", methods=["GET"])
    def get_extracted_object(workflow_id: str):
        """Return the extracted object for a workflow."""
        store = get_store()
        extracted = store.get_extracted(workflow_id)
        if extracted is None:
            return jsonify({"error": "Extracted object not found"}), 404
        return jsonify(extracted)

    @app.route("/api/trigger", methods=["POST"])
    def trigger_processing():
        """Manually trigger document processing.

        Accepts JSON body with:
          - filename: name of a file in the input directory
          - file_path: full path to a file (takes precedence)
        """
        data = request.get_json(force=True, silent=True) or {}
        file_path = data.get("file_path")
        filename = data.get("filename")

        if not file_path and not filename:
            return jsonify({"error": "Provide 'filename' or 'file_path'"}), 400

        if not file_path:
            if config.storage_backend == "s3":
                file_path = filename
            else:
                file_path = os.path.join(config.local_input_path, filename)

        try:
            workflow = simulate_trigger(file_path)
            return jsonify({
                "workflow_id": workflow.workflow_id,
                "status": workflow.status,
                "file_name": workflow.file_name,
                "model_id": workflow.model_id,
                "error_message": workflow.error_message,
            }), 201
        except Exception as e:
            logger.exception("Trigger failed")
            return jsonify({"error": str(e)}), 500

    # --- Static UI ---

    @app.route("/")
    def serve_ui():
        """Serve the dashboard SPA."""
        index_file = ui_dir / "index.html"
        if not index_file.exists():
            return jsonify({
                "status": "healthy",
                "service": "agenticautomation",
                "message": f"API is running. UI assets not found at {ui_dir}"
            }), 200
        return send_from_directory(str(ui_dir), "index.html")

    @app.errorhandler(404)
    def not_found(e):
        """Fallback for SPA routing — return index.html for unmatched routes."""
        if request.path.startswith("/api/"):
            return jsonify({"error": "Not found"}), 404
        index_file = ui_dir / "index.html"
        if index_file.exists():
            return send_from_directory(str(ui_dir), "index.html")
        return jsonify({"error": "Not found", "path": request.path}), 404

    return app


# ---------------------------------------------------------------------------
# CLI: python -m agenticautomation.api.server
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    config.ensure_local_dirs()
    app = create_app()
    print(f"\n  🚀 AgenticAutomation API running at http://localhost:{config.api_port}\n")
    app.run(host="0.0.0.0", port=config.api_port, debug=config.is_dev)
