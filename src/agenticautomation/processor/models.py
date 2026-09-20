"""Data models for AgenticAutomation workflow execution."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class WorkflowStatus(str, Enum):
    """Status codes tracking a workflow's lifecycle."""

    FILE_LANDED = "FILE_LANDED"
    REGISTRY_MATCHED = "REGISTRY_MATCHED"
    CONTENT_READ = "CONTENT_READ"
    AGENT_PARSING = "AGENT_PARSING"
    PARSED = "PARSED"
    POSTED = "POSTED"
    FAILED = "FAILED"


def _generate_workflow_id() -> str:
    """Generate a unique workflow ID like wf-20260918-123456-abc123."""
    now = datetime.now(timezone.utc)
    short_uuid = uuid.uuid4().hex[:6]
    return f"wf-{now.strftime('%Y%m%d-%H%M%S')}-{short_uuid}"


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class WorkflowStep:
    """A single step in a workflow's execution history."""

    step_name: str
    status: str  # "SUCCESS" or "FAILED"
    detail: str
    timestamp: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, str]:
        return {
            "step_name": self.step_name,
            "status": self.status,
            "detail": self.detail,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> WorkflowStep:
        return cls(
            step_name=data["step_name"],
            status=data["status"],
            detail=data["detail"],
            timestamp=data.get("timestamp", _now_iso()),
        )


@dataclass
class WorkflowRun:
    """Top-level metadata for a single document processing workflow."""

    workflow_id: str = field(default_factory=_generate_workflow_id)
    file_name: str = ""
    file_key: str = ""
    model_id: str = ""
    status: str = WorkflowStatus.FILE_LANDED.value
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "file_name": self.file_name,
            "file_key": self.file_key,
            "model_id": self.model_id,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkflowRun:
        return cls(
            workflow_id=data["workflow_id"],
            file_name=data.get("file_name", ""),
            file_key=data.get("file_key", ""),
            model_id=data.get("model_id", ""),
            status=data.get("status", WorkflowStatus.FILE_LANDED.value),
            created_at=data.get("created_at", _now_iso()),
            updated_at=data.get("updated_at", _now_iso()),
            error_message=data.get("error_message"),
        )


@dataclass
class ExtractedObject:
    """Structured data extracted by a Bedrock model."""

    workflow_id: str
    model_id: str
    extracted_at: str = field(default_factory=_now_iso)
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "model_id": self.model_id,
            "extracted_at": self.extracted_at,
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExtractedObject:
        return cls(
            workflow_id=data["workflow_id"],
            model_id=data["model_id"],
            extracted_at=data.get("extracted_at", _now_iso()),
            data=data.get("data", {}),
        )
