"""Workflow persistence — LocalStore (filesystem) and S3Store (AWS S3).

Both backends expose the same WorkflowStore interface and store data in
an identical JSON hierarchy:

    [root]/
    ├── index.json
    └── {workflow_id}/
        ├── workflow.json
        ├── steps.json
        └── extracted.json
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from agenticautomation.config import config
from agenticautomation.processor.models import (
    ExtractedObject,
    WorkflowRun,
    WorkflowStep,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------


class WorkflowStore(ABC):
    """Abstract interface for persisting workflow state."""

    @abstractmethod
    def save_workflow(self, workflow: WorkflowRun) -> None:
        """Create or update a workflow record and its index entry."""

    @abstractmethod
    def save_steps(self, workflow_id: str, steps: list[WorkflowStep]) -> None:
        """Overwrite the steps list for a workflow."""

    @abstractmethod
    def save_extracted(self, extracted: ExtractedObject) -> None:
        """Save the extracted object for a workflow."""

    @abstractmethod
    def get_workflow(self, workflow_id: str) -> dict[str, Any] | None:
        """Return the workflow.json dict, or None if not found."""

    @abstractmethod
    def get_steps(self, workflow_id: str) -> list[dict[str, Any]]:
        """Return the steps.json list, or empty list if not found."""

    @abstractmethod
    def get_extracted(self, workflow_id: str) -> dict[str, Any] | None:
        """Return the extracted.json dict, or None if not found."""

    @abstractmethod
    def list_workflows(self) -> list[dict[str, Any]]:
        """Return all workflow summaries from index.json."""


# ---------------------------------------------------------------------------
# Local filesystem implementation
# ---------------------------------------------------------------------------


class LocalStore(WorkflowStore):
    """Store workflow state as JSON files on the local filesystem."""

    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or config.local_storage_path)
        self.root.mkdir(parents=True, exist_ok=True)

    def _workflow_dir(self, workflow_id: str) -> Path:
        d = self.root / workflow_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _index_path(self) -> Path:
        return self.root / "index.json"

    def _read_json(self, path: Path) -> Any:
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _write_json(self, path: Path, data: Any) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # --- Index management ---

    def _update_index(self, workflow: WorkflowRun) -> None:
        """Upsert a workflow summary into index.json."""
        index: list[dict[str, Any]] = self._read_json(self._index_path()) or []
        entry = {
            "workflow_id": workflow.workflow_id,
            "file_name": workflow.file_name,
            "model_id": workflow.model_id,
            "status": workflow.status,
            "created_at": workflow.created_at,
            "updated_at": workflow.updated_at,
        }
        # Update existing or append
        for i, item in enumerate(index):
            if item["workflow_id"] == workflow.workflow_id:
                index[i] = entry
                break
        else:
            index.append(entry)

        self._write_json(self._index_path(), index)

    # --- Interface implementation ---

    def save_workflow(self, workflow: WorkflowRun) -> None:
        path = self._workflow_dir(workflow.workflow_id) / "workflow.json"
        self._write_json(path, workflow.to_dict())
        self._update_index(workflow)
        logger.info("Saved workflow %s → %s", workflow.workflow_id, path)

    def save_steps(self, workflow_id: str, steps: list[WorkflowStep]) -> None:
        path = self._workflow_dir(workflow_id) / "steps.json"
        self._write_json(path, [s.to_dict() for s in steps])

    def save_extracted(self, extracted: ExtractedObject) -> None:
        path = self._workflow_dir(extracted.workflow_id) / "extracted.json"
        self._write_json(path, extracted.to_dict())

    def get_workflow(self, workflow_id: str) -> dict[str, Any] | None:
        path = self.root / workflow_id / "workflow.json"
        return self._read_json(path)

    def get_steps(self, workflow_id: str) -> list[dict[str, Any]]:
        path = self.root / workflow_id / "steps.json"
        return self._read_json(path) or []

    def get_extracted(self, workflow_id: str) -> dict[str, Any] | None:
        path = self.root / workflow_id / "extracted.json"
        return self._read_json(path)

    def list_workflows(self) -> list[dict[str, Any]]:
        return self._read_json(self._index_path()) or []


# ---------------------------------------------------------------------------
# S3 implementation
# ---------------------------------------------------------------------------


class S3Store(WorkflowStore):
    """Store workflow state as JSON objects in an S3 bucket."""

    def __init__(self, bucket: str | None = None) -> None:
        import boto3

        self.bucket = bucket or config.s3_data_bucket
        self.client = boto3.client("s3", region_name=config.aws_region)
        self.prefix = "workflows"

    def _key(self, *parts: str) -> str:
        return "/".join([self.prefix, *parts])

    def _read_json(self, key: str) -> Any:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            return json.loads(response["Body"].read())
        except self.client.exceptions.NoSuchKey:
            return None
        except Exception:
            logger.exception("Failed to read s3://%s/%s", self.bucket, key)
            return None

    def _write_json(self, key: str, data: Any) -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=json.dumps(data, indent=2, ensure_ascii=False),
            ContentType="application/json",
        )

    def _update_index(self, workflow: WorkflowRun) -> None:
        key = self._key("index.json")
        index: list[dict[str, Any]] = self._read_json(key) or []
        entry = {
            "workflow_id": workflow.workflow_id,
            "file_name": workflow.file_name,
            "model_id": workflow.model_id,
            "status": workflow.status,
            "created_at": workflow.created_at,
            "updated_at": workflow.updated_at,
        }
        for i, item in enumerate(index):
            if item["workflow_id"] == workflow.workflow_id:
                index[i] = entry
                break
        else:
            index.append(entry)
        self._write_json(key, index)

    def save_workflow(self, workflow: WorkflowRun) -> None:
        key = self._key(workflow.workflow_id, "workflow.json")
        self._write_json(key, workflow.to_dict())
        self._update_index(workflow)
        logger.info("Saved workflow %s → s3://%s/%s", workflow.workflow_id, self.bucket, key)

    def save_steps(self, workflow_id: str, steps: list[WorkflowStep]) -> None:
        key = self._key(workflow_id, "steps.json")
        self._write_json(key, [s.to_dict() for s in steps])

    def save_extracted(self, extracted: ExtractedObject) -> None:
        key = self._key(extracted.workflow_id, "extracted.json")
        self._write_json(key, extracted.to_dict())

    def get_workflow(self, workflow_id: str) -> dict[str, Any] | None:
        return self._read_json(self._key(workflow_id, "workflow.json"))

    def get_steps(self, workflow_id: str) -> list[dict[str, Any]]:
        return self._read_json(self._key(workflow_id, "steps.json")) or []

    def get_extracted(self, workflow_id: str) -> dict[str, Any] | None:
        return self._read_json(self._key(workflow_id, "extracted.json"))

    def list_workflows(self) -> list[dict[str, Any]]:
        return self._read_json(self._key("index.json")) or []


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_store_instance: WorkflowStore | None = None


def get_store() -> WorkflowStore:
    """Return the appropriate store based on the current configuration.

    Returns a singleton instance — safe for use across Flask requests.
    """
    global _store_instance
    if _store_instance is None:
        if config.storage_backend == "local":
            _store_instance = LocalStore()
        else:
            _store_instance = S3Store()
        logger.info("Initialized %s store", type(_store_instance).__name__)
    return _store_instance
