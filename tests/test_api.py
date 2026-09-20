"""Tests for the Flask REST API."""

import json

import pytest

from agenticautomation.api.server import create_app
from agenticautomation.storage.store import LocalStore, _store_instance
import agenticautomation.storage.store as store_module


@pytest.fixture(autouse=True)
def reset_store(tmp_path):
    """Reset the store singleton to use a temporary directory for each test."""
    test_store = LocalStore(root=str(tmp_path / "workflows"))
    store_module._store_instance = test_store
    yield
    store_module._store_instance = None


@pytest.fixture
def client():
    """Create a Flask test client."""
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


class TestListWorkflows:
    def test_empty_list(self, client):
        res = client.get("/api/workflows")
        assert res.status_code == 200
        assert res.get_json() == []

    def test_list_after_trigger(self, client, tmp_path):
        # Create a test file
        f = tmp_path / "invoice_test.txt"
        f.write_text("INVOICE\nNumber: 001\n")

        # Trigger processing
        res = client.post(
            "/api/trigger",
            json={"file_path": str(f)},
        )
        assert res.status_code == 201

        # List should have one entry
        res = client.get("/api/workflows")
        data = res.get_json()
        assert len(data) == 1
        assert data[0]["file_name"] == "invoice_test.txt"


class TestWorkflowDetail:
    def test_not_found(self, client):
        res = client.get("/api/workflows/wf-nonexistent")
        assert res.status_code == 404

    def test_detail_after_trigger(self, client, tmp_path):
        f = tmp_path / "invoice_test.txt"
        f.write_text("INVOICE\nNumber: 001\n")

        trigger_res = client.post("/api/trigger", json={"file_path": str(f)})
        wf_id = trigger_res.get_json()["workflow_id"]

        res = client.get(f"/api/workflows/{wf_id}")
        assert res.status_code == 200
        data = res.get_json()
        assert data["workflow"]["workflow_id"] == wf_id
        assert len(data["steps"]) == 6  # All 6 steps for successful workflow


class TestExtractedObject:
    def test_not_found(self, client):
        res = client.get("/api/workflows/wf-nonexistent/object")
        assert res.status_code == 404

    def test_extracted_after_trigger(self, client, tmp_path):
        f = tmp_path / "invoice_test.txt"
        f.write_text("INVOICE\nNumber: 001\n")

        trigger_res = client.post("/api/trigger", json={"file_path": str(f)})
        wf_id = trigger_res.get_json()["workflow_id"]

        res = client.get(f"/api/workflows/{wf_id}/object")
        assert res.status_code == 200
        data = res.get_json()
        assert "data" in data
        assert data["model_id"] is not None


class TestTriggerEndpoint:
    def test_trigger_with_filename(self, client):
        """Trigger with a filename (will fail if file doesn't exist, but tests the route)."""
        res = client.post("/api/trigger", json={"filename": "nonexistent.txt"})
        # Should return 201 but with FAILED status (file not found)
        assert res.status_code == 201
        data = res.get_json()
        assert data["status"] == "FAILED"

    def test_trigger_missing_params(self, client):
        res = client.post("/api/trigger", json={})
        assert res.status_code == 400

    def test_trigger_with_file_path(self, client, tmp_path):
        f = tmp_path / "report_test.txt"
        f.write_text("REPORT\nPeriod: Q3 2026\n")

        res = client.post("/api/trigger", json={"file_path": str(f)})
        assert res.status_code == 201
        data = res.get_json()
        assert data["status"] == "POSTED"
        assert data["file_name"] == "report_test.txt"
