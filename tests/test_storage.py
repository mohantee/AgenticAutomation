"""Tests for the storage layer (LocalStore)."""

import json

import pytest

from agenticautomation.processor.models import ExtractedObject, WorkflowRun, WorkflowStep
from agenticautomation.storage.store import LocalStore


@pytest.fixture
def store(tmp_path):
    """Create a LocalStore backed by a temporary directory."""
    return LocalStore(root=str(tmp_path))


@pytest.fixture
def sample_workflow():
    """Create a sample workflow run."""
    return WorkflowRun(
        workflow_id="wf-test-001",
        file_name="invoice_test.txt",
        file_key="sample_files/invoice_test.txt",
        model_id="anthropic.claude-3-sonnet-20240229-v1:0",
        status="POSTED",
    )


@pytest.fixture
def sample_steps():
    """Create sample workflow steps."""
    return [
        WorkflowStep("FILE_LANDED", "SUCCESS", "File detected"),
        WorkflowStep("REGISTRY_MATCHED", "SUCCESS", "Matched invoice_*"),
        WorkflowStep("CONTENT_READ", "SUCCESS", "Read 500 bytes"),
        WorkflowStep("AGENT_PARSING", "SUCCESS", "Model invoked"),
        WorkflowStep("PARSED", "SUCCESS", "JSON valid"),
        WorkflowStep("POSTED", "SUCCESS", "Saved"),
    ]


class TestLocalStore:
    """Test LocalStore CRUD operations."""

    def test_save_and_get_workflow(self, store, sample_workflow):
        store.save_workflow(sample_workflow)
        result = store.get_workflow("wf-test-001")
        assert result is not None
        assert result["workflow_id"] == "wf-test-001"
        assert result["file_name"] == "invoice_test.txt"
        assert result["status"] == "POSTED"

    def test_get_nonexistent_workflow(self, store):
        result = store.get_workflow("wf-does-not-exist")
        assert result is None

    def test_save_and_get_steps(self, store, sample_workflow, sample_steps):
        store.save_workflow(sample_workflow)
        store.save_steps("wf-test-001", sample_steps)
        result = store.get_steps("wf-test-001")
        assert len(result) == 6
        assert result[0]["step_name"] == "FILE_LANDED"
        assert result[-1]["step_name"] == "POSTED"

    def test_get_steps_nonexistent(self, store):
        result = store.get_steps("wf-does-not-exist")
        assert result == []

    def test_save_and_get_extracted(self, store, sample_workflow):
        store.save_workflow(sample_workflow)
        extracted = ExtractedObject(
            workflow_id="wf-test-001",
            model_id="anthropic.claude-3-sonnet-20240229-v1:0",
            data={"invoice_number": "INV-001", "total": 100.0},
        )
        store.save_extracted(extracted)
        result = store.get_extracted("wf-test-001")
        assert result is not None
        assert result["data"]["invoice_number"] == "INV-001"
        assert result["data"]["total"] == 100.0

    def test_get_extracted_nonexistent(self, store):
        result = store.get_extracted("wf-does-not-exist")
        assert result is None

    def test_list_workflows(self, store, sample_workflow):
        store.save_workflow(sample_workflow)
        result = store.list_workflows()
        assert len(result) == 1
        assert result[0]["workflow_id"] == "wf-test-001"

    def test_list_workflows_empty(self, store):
        result = store.list_workflows()
        assert result == []

    def test_index_updates_on_save(self, store):
        """Saving a workflow twice should update the index, not duplicate."""
        wf = WorkflowRun(workflow_id="wf-dup", file_name="test.txt", status="FILE_LANDED")
        store.save_workflow(wf)
        assert len(store.list_workflows()) == 1

        wf.status = "POSTED"
        store.save_workflow(wf)
        index = store.list_workflows()
        assert len(index) == 1
        assert index[0]["status"] == "POSTED"

    def test_multiple_workflows(self, store):
        for i in range(5):
            wf = WorkflowRun(workflow_id=f"wf-multi-{i}", file_name=f"file_{i}.txt")
            store.save_workflow(wf)
        assert len(store.list_workflows()) == 5
