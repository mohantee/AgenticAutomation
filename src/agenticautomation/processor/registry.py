"""Model & Prompt Registry — maps filename patterns to Bedrock models and prompts."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass


@dataclass(frozen=True)
class RegistryEntry:
    """A single entry mapping a filename pattern to a model and prompt."""

    pattern: str
    model_id: str
    model_label: str
    prompt_template: str


# --- Registry Entries ---

MODEL_REGISTRY: list[RegistryEntry] = [
    RegistryEntry(
        pattern="invoice_*",
        model_id="anthropic.claude-3-haiku-20240307-v1:0",
        model_label="Claude 3 Haiku",
        prompt_template=(
            "You are an expert invoice parser. Extract all structured fields from this invoice document.\n"
            "Return a JSON object with these fields:\n"
            "- invoice_number (string)\n"
            "- date (string, ISO format)\n"
            "- due_date (string, ISO format)\n"
            "- vendor_name (string)\n"
            "- vendor_address (string)\n"
            "- bill_to (string)\n"
            "- line_items (array of objects with: description, quantity, unit_price, amount)\n"
            "- subtotal (number)\n"
            "- tax (number)\n"
            "- total (number)\n"
            "- currency (string, e.g. USD)\n\n"
            "Document content:\n{content}"
        ),
    ),
    RegistryEntry(
        pattern="contract_*",
        model_id="amazon.nova-lite-v1:0",
        model_label="Nova Lite",
        prompt_template=(
            "You are a legal document analyst. Summarize this contract and extract key terms.\n"
            "Return a JSON object with these fields:\n"
            "- contract_title (string)\n"
            "- parties (array of strings — full party names)\n"
            "- effective_date (string, ISO format)\n"
            "- expiration_date (string, ISO format or null)\n"
            "- contract_type (string, e.g. 'Service Agreement', 'NDA')\n"
            "- key_terms (array of objects with: term_name, description)\n"
            "- total_value (number or null)\n"
            "- currency (string or null)\n"
            "- governing_law (string — jurisdiction)\n"
            "- summary (string — 2-3 sentence executive summary)\n\n"
            "Document content:\n{content}"
        ),
    ),
    RegistryEntry(
        pattern="report_*",
        model_id="amazon.nova-micro-v1:0",
        model_label="Nova Micro",
        prompt_template=(
            "You are a business intelligence analyst. Extract key metrics and findings from this report.\n"
            "Return a JSON object with these fields:\n"
            "- report_title (string)\n"
            "- reporting_period (string)\n"
            "- prepared_by (string)\n"
            "- kpis (array of objects with: metric_name, value, unit, trend — 'up'/'down'/'flat')\n"
            "- highlights (array of strings — key findings)\n"
            "- risks (array of strings — identified risks or concerns)\n"
            "- recommendations (array of strings)\n"
            "- summary (string — executive summary paragraph)\n\n"
            "Document content:\n{content}"
        ),
    ),
    # Fallback — catches any unmatched filename
    RegistryEntry(
        pattern="*",
        model_id="amazon.nova-micro-v1:0",
        model_label="Nova Micro",
        prompt_template=(
            "Extract all structured content from this document. "
            "Return a JSON object with the most relevant fields based on the document type.\n\n"
            "Document content:\n{content}"
        ),
    ),
]


def resolve_model(filename: str) -> RegistryEntry:
    """Resolve a filename to its matching registry entry.

    Matches are tested in order; the first match wins.
    The last entry ('*') serves as a guaranteed fallback.

    Args:
        filename: The basename of the document file (e.g. 'invoice_Q3.txt').

    Returns:
        The matching RegistryEntry.
    """
    for entry in MODEL_REGISTRY:
        if fnmatch.fnmatch(filename, entry.pattern):
            return entry
    # Should never reach here because '*' catches everything,
    # but return the fallback defensively.
    return MODEL_REGISTRY[-1]
