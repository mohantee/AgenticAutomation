"""AgenticAutomation — Agentic Document Processing Workflow."""

from agenticautomation.config import config  # noqa: F401


def main() -> None:
    """CLI entry point for AgenticAutomation."""
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        from agenticautomation.api.server import create_app

        app = create_app()
        app.run(host="0.0.0.0", port=config.api_port, debug=config.is_dev)
    elif len(sys.argv) > 1 and sys.argv[1] == "process":
        from agenticautomation.processor.trigger import simulate_trigger

        if len(sys.argv) < 3:
            print("Usage: agenticautomation process <file_path>")
            sys.exit(1)
        simulate_trigger(sys.argv[2])
    else:
        print("Usage: agenticautomation <serve|process> [args...]")
        print("  serve              Start the Flask API + UI server")
        print("  process <file>     Process a document file locally")
        sys.exit(1)
