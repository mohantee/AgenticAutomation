"""Tests for the workflow trigger / orchestrator."""

import os
import tempfile

import pytest

from agenticautomation.processor.models import WorkflowStatus
from agenticautomation.processor.trigger import simulate_trigger


@pytest.fixture
def sample_invoice(tmp_path):
    """Create a temporary invoice file."""
    f = tmp_path / "invoice_test.txt"
    f.write_text("INVOICE\nInvoice Number: INV-001\nTotal: $100.00\n")
    return str(f)


@pytest.fixture
def sample_contract(tmp_path):
    """Create a temporary contract file."""
    f = tmp_path / "contract_test.txt"
    f.write_text("CONTRACT\nParties: A and B\nEffective: 2026-01-01\n")
    return str(f)


@pytest.fixture
def sample_report(tmp_path):
    """Create a temporary report file."""
    f = tmp_path / "report_test.txt"
    f.write_text("REPORT\nPeriod: August 2026\nDocuments: 14832\n")
    return str(f)


class TestSimulateTrigger:
    """Test the local trigger simulation."""

    def test_invoice_workflow_completes(self, sample_invoice):
        result = simulate_trigger(sample_invoice)
        assert result.status == WorkflowStatus.POSTED.value
        assert result.file_name == "invoice_test.txt"
        assert "claude-3-haiku" in result.model_id
        assert result.error_message is None

    def test_contract_workflow_completes(self, sample_contract):
        result = simulate_trigger(sample_contract)
        assert result.status == WorkflowStatus.POSTED.value
        assert result.file_name == "contract_test.txt"
        assert "nova-lite" in result.model_id

    def test_report_workflow_completes(self, sample_report):
        result = simulate_trigger(sample_report)
        assert result.status == WorkflowStatus.POSTED.value
        assert result.file_name == "report_test.txt"
        assert "nova-micro" in result.model_id

    def test_missing_file_fails(self, tmp_path):
        result = simulate_trigger(str(tmp_path / "nonexistent.txt"))
        assert result.status == WorkflowStatus.FAILED.value
        assert result.error_message is not None
        assert "not found" in result.error_message.lower() or "FileNotFoundError" in result.error_message

    def test_workflow_id_format(self, sample_invoice):
        result = simulate_trigger(sample_invoice)
        assert result.workflow_id.startswith("wf-")
        parts = result.workflow_id.split("-")
        assert len(parts) >= 4  # wf-YYYYMMDD-HHMMSS-hex

    def test_workflow_timestamps_set(self, sample_invoice):
        result = simulate_trigger(sample_invoice)
        assert result.created_at
        assert result.updated_at
