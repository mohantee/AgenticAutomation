"""Tests for the Model & Prompt Registry."""

from agenticautomation.processor.registry import MODEL_REGISTRY, RegistryEntry, resolve_model


class TestResolveModel:
    """Test filename → model resolution."""

    def test_invoice_pattern(self):
        entry = resolve_model("invoice_Q3.txt")
        assert entry.pattern == "invoice_*"
        assert "claude-3-haiku" in entry.model_id
        assert entry.model_label == "Claude 3 Haiku"

    def test_contract_pattern(self):
        entry = resolve_model("contract_vendor_A.txt")
        assert entry.pattern == "contract_*"
        assert "nova-lite" in entry.model_id
        assert entry.model_label == "Nova Lite"

    def test_report_pattern(self):
        entry = resolve_model("report_monthly.txt")
        assert entry.pattern == "report_*"
        assert "nova-micro" in entry.model_id
        assert entry.model_label == "Nova Micro"

    def test_fallback_pattern(self):
        entry = resolve_model("unknown_document.pdf")
        assert entry.pattern == "*"
        assert "nova-micro" in entry.model_id
        assert entry.model_label == "Nova Micro"

    def test_invoice_with_numbers(self):
        entry = resolve_model("invoice_2026_Q1_final.txt")
        assert entry.pattern == "invoice_*"

    def test_contract_various_names(self):
        entry = resolve_model("contract_NDA_acme.txt")
        assert entry.pattern == "contract_*"

    def test_report_various_names(self):
        entry = resolve_model("report_weekly_summary.csv")
        assert entry.pattern == "report_*"


class TestRegistry:
    """Test registry structure."""

    def test_registry_has_entries(self):
        assert len(MODEL_REGISTRY) >= 4  # 3 specific + 1 fallback

    def test_last_entry_is_fallback(self):
        assert MODEL_REGISTRY[-1].pattern == "*"

    def test_all_entries_are_registry_entry(self):
        for entry in MODEL_REGISTRY:
            assert isinstance(entry, RegistryEntry)
            assert entry.pattern
            assert entry.model_id
            assert entry.prompt_template
            assert "{content}" in entry.prompt_template

    def test_first_match_wins(self):
        """Ensure ordered matching — invoice_* should match before *."""
        entry = resolve_model("invoice_test.txt")
        assert entry.pattern == "invoice_*"
        assert entry.pattern != "*"
