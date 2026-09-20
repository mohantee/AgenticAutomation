"""Trigger / Orchestrator — the core workflow execution engine.

Supports two entry points:
  • lambda_handler(event, context) — for AWS Lambda with S3 events
  • simulate_trigger(file_path)     — for local dev CLI / API usage
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

from agenticautomation.config import config
from agenticautomation.processor.bedrock_client import invoke_model
from agenticautomation.processor.file_reader import read_file
from agenticautomation.processor.models import (
    ExtractedObject,
    WorkflowRun,
    WorkflowStatus,
    WorkflowStep,
    _now_iso,
)
from agenticautomation.processor.registry import resolve_model
from agenticautomation.storage.store import get_store

logger = logging.getLogger(__name__)


def _run_workflow(file_name: str, file_key: str) -> WorkflowRun:
    """Execute the full document processing workflow.

    This is the shared core logic used by both lambda_handler and
    simulate_trigger. Each step is persisted incrementally so the
    UI can observe partial progress.

    Args:
        file_name: The basename of the file (e.g. 'invoice_Q3.txt').
        file_key: The full path/key to read the file (local path or S3 key).

    Returns:
        The completed WorkflowRun object.
    """
    store = get_store()
    workflow = WorkflowRun(file_name=file_name, file_key=file_key)
    steps: list[WorkflowStep] = []

    def _record_step(
        step_name: str,
        status: str,
        detail: str,
        *,
        workflow_status: str | None = None,
        error: str | None = None,
    ) -> None:
        """Append a step and persist the updated state."""
        steps.append(WorkflowStep(step_name=step_name, status=status, detail=detail))
        if workflow_status:
            workflow.status = workflow_status
        if error:
            workflow.error_message = error
        workflow.updated_at = _now_iso()
        store.save_workflow(workflow)
        store.save_steps(workflow.workflow_id, steps)

    try:
        # Step 1 — FILE_LANDED
        _record_step(
            WorkflowStatus.FILE_LANDED.value,
            "SUCCESS",
            f"File detected: {file_name}",
            workflow_status=WorkflowStatus.FILE_LANDED.value,
        )
        logger.info("[%s] FILE_LANDED — %s", workflow.workflow_id, file_name)

        # Step 2 — REGISTRY_MATCHED
        entry = resolve_model(file_name)
        workflow.model_id = entry.model_id
        _record_step(
            WorkflowStatus.REGISTRY_MATCHED.value,
            "SUCCESS",
            f"Matched pattern '{entry.pattern}' → {entry.model_label} ({entry.model_id})",
            workflow_status=WorkflowStatus.REGISTRY_MATCHED.value,
        )
        logger.info("[%s] REGISTRY_MATCHED — %s → %s", workflow.workflow_id, entry.pattern, entry.model_label)

        # Step 3 — CONTENT_READ
        content = read_file(file_key)
        byte_count = len(content.encode("utf-8"))
        _record_step(
            WorkflowStatus.CONTENT_READ.value,
            "SUCCESS",
            f"Read {byte_count:,} bytes",
            workflow_status=WorkflowStatus.CONTENT_READ.value,
        )
        logger.info("[%s] CONTENT_READ — %d bytes", workflow.workflow_id, byte_count)

        # Step 4 — AGENT_PARSING
        prompt = entry.prompt_template.format(content=content)
        _record_step(
            WorkflowStatus.AGENT_PARSING.value,
            "SUCCESS",
            f"Bedrock model invoked: {entry.model_label}",
            workflow_status=WorkflowStatus.AGENT_PARSING.value,
        )
        logger.info("[%s] AGENT_PARSING — invoking %s", workflow.workflow_id, entry.model_id)

        extracted_data = invoke_model(entry.model_id, prompt, content)

        # Step 5 — PARSED
        _record_step(
            WorkflowStatus.PARSED.value,
            "SUCCESS",
            "Extracted JSON payload valid",
            workflow_status=WorkflowStatus.PARSED.value,
        )
        logger.info("[%s] PARSED — extraction complete", workflow.workflow_id)

        # Step 6 — POSTED
        extracted_obj = ExtractedObject(
            workflow_id=workflow.workflow_id,
            model_id=entry.model_id,
            data=extracted_data,
        )
        store.save_extracted(extracted_obj)
        _record_step(
            WorkflowStatus.POSTED.value,
            "SUCCESS",
            "Saved to store",
            workflow_status=WorkflowStatus.POSTED.value,
        )
        logger.info("[%s] POSTED — workflow complete ✓", workflow.workflow_id)

    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        _record_step(
            WorkflowStatus.FAILED.value,
            "FAILED",
            error_msg,
            workflow_status=WorkflowStatus.FAILED.value,
            error=error_msg,
        )
        logger.exception("[%s] FAILED — %s", workflow.workflow_id, error_msg)

    return workflow


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def lambda_handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """AWS Lambda handler — triggered by S3 ObjectCreated events.

    Parses the S3 event record and runs the workflow.
    """
    from urllib.parse import unquote_plus

    record = event["Records"][0]
    bucket = record["s3"]["bucket"]["name"]
    key = unquote_plus(record["s3"]["object"]["key"])
    file_name = os.path.basename(key)

    logger.info("Lambda triggered — s3://%s/%s", bucket, key)
    workflow = _run_workflow(file_name, key)

    return {
        "statusCode": 200,
        "body": {
            "workflow_id": workflow.workflow_id,
            "status": workflow.status,
        },
    }


def simulate_trigger(file_path: str) -> WorkflowRun:
    """Local dev entry point — simulate an S3 trigger from a local file.

    Args:
        file_path: Path to a local file (absolute or relative).

    Returns:
        The completed WorkflowRun.
    """
    config.ensure_local_dirs()
    file_name = os.path.basename(file_path)
    logger.info("Local trigger — processing %s", file_path)
    return _run_workflow(file_name, file_path)


# ---------------------------------------------------------------------------
# CLI support: python -m agenticautomation.processor.trigger <file_path>
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    if len(sys.argv) < 2:
        print("Usage: python -m agenticautomation.processor.trigger <file_path>")
        sys.exit(1)

    result = simulate_trigger(sys.argv[1])
    print(f"\n{'=' * 60}")
    print(f"  Workflow: {result.workflow_id}")
    print(f"  File:     {result.file_name}")
    print(f"  Status:   {result.status}")
    print(f"  Model:    {result.model_id}")
    if result.error_message:
        print(f"  Error:    {result.error_message}")
    print(f"{'=' * 60}")
