"""Bedrock model invocation — real AWS Bedrock or deterministic mock responses."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from agenticautomation.config import config

logger = logging.getLogger(__name__)


def invoke_model(model_id: str, prompt: str, content: str) -> dict[str, Any]:
    """Invoke a Bedrock model (or mock) and return extracted JSON.

    Args:
        model_id: The Bedrock model identifier.
        prompt: The prompt template (with {content} placeholder already filled).
        content: The raw document text (used only for mock responses).

    Returns:
        A parsed JSON dict with the model's structured extraction.
    """
    if config.mock_bedrock:
        return _mock_invoke(model_id, content)
    else:
        return _aws_invoke(model_id, prompt)


# ---------------------------------------------------------------------------
# AWS Bedrock invocation
# ---------------------------------------------------------------------------

_MAX_RETRIES = 3
_BASE_BACKOFF = 1.0  # seconds


def _aws_invoke(model_id: str, prompt: str) -> dict[str, Any]:
    """Call AWS Bedrock InvokeModel with retry on throttling."""
    import boto3

    client = boto3.client("bedrock-runtime", region_name=config.aws_region)

    body = _build_request_body(model_id, prompt)

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            logger.info(
                "Bedrock InvokeModel attempt %d/%d — model=%s",
                attempt,
                _MAX_RETRIES,
                model_id,
            )
            response = client.invoke_model(
                modelId=model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(body),
            )
            response_body = json.loads(response["body"].read())
            return _parse_response(model_id, response_body)

        except client.exceptions.ThrottlingException:
            if attempt == _MAX_RETRIES:
                raise
            wait = _BASE_BACKOFF * (2 ** (attempt - 1))
            logger.warning("Throttled — retrying in %.1fs ...", wait)
            time.sleep(wait)

    # Unreachable but satisfies the type checker.
    raise RuntimeError("Exhausted retries for Bedrock InvokeModel")


def _build_request_body(model_id: str, prompt: str) -> dict[str, Any]:
    """Build the request payload for the target model family."""
    if "anthropic.claude" in model_id:
        return {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
    elif "amazon.nova" in model_id:
        return {
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {
                "max_new_tokens": 4096,
                "temperature": 0.1,
                "top_p": 0.9,
            },
        }
    elif "amazon.titan" in model_id:
        return {
            "inputText": prompt,
            "textGenerationConfig": {
                "maxTokenCount": 4096,
                "temperature": 0.1,
                "topP": 0.9,
            },
        }
    elif "meta.llama" in model_id:
        return {
            "prompt": f"<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\n{prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n",
            "max_gen_len": 4096,
            "temperature": 0.1,
            "top_p": 0.9,
        }
    else:
        # Generic fallback
        return {"inputText": prompt}


def _parse_response(model_id: str, response_body: dict[str, Any]) -> dict[str, Any]:
    """Extract the JSON payload from a model-specific response envelope."""
    raw_text: str = ""

    if "anthropic.claude" in model_id:
        raw_text = response_body.get("content", [{}])[0].get("text", "")
    elif "amazon.nova" in model_id:
        content_blocks = response_body.get("output", {}).get("message", {}).get("content", [])
        raw_text = content_blocks[0].get("text", "") if content_blocks else ""
    elif "amazon.titan" in model_id:
        results = response_body.get("results", [{}])
        raw_text = results[0].get("outputText", "") if results else ""
    elif "meta.llama" in model_id:
        raw_text = response_body.get("generation", "")
    else:
        raw_text = json.dumps(response_body)

    # Try to parse as JSON — if the model wrapped it in markdown fences, strip them.
    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        raw_text = "\n".join(lines)

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        logger.warning("Model response was not valid JSON; wrapping as raw_text.")
        return {"raw_text": raw_text}


# ---------------------------------------------------------------------------
# Mock Bedrock — deterministic canned responses for dev/testing
# ---------------------------------------------------------------------------

def _mock_invoke(model_id: str, content: str) -> dict[str, Any]:
    """Return a realistic mock extraction based on the model type."""
    logger.info("Mock Bedrock invocation — model=%s, content_length=%d", model_id, len(content))

    if "haiku" in model_id or "sonnet" in model_id or "invoice" in content.lower():
        return _mock_invoice()
    elif "nova-lite" in model_id or "llama" in model_id or "contract" in content.lower():
        return _mock_contract()
    elif "nova-micro" in model_id or "titan" in model_id or "report" in content.lower():
        return _mock_report()
    else:
        return _mock_generic(content)


def _mock_invoice() -> dict[str, Any]:
    return {
        "invoice_number": "INV-2026-Q3-0847",
        "date": "2026-07-15",
        "due_date": "2026-08-14",
        "vendor_name": "Stellar Supplies Co.",
        "vendor_address": "742 Innovation Blvd, Suite 300, Austin, TX 78701",
        "bill_to": "AgenticAutomation Inc., 100 Main St, San Francisco, CA 94102",
        "line_items": [
            {
                "description": "Cloud Compute (GPU Instances) — July 2026",
                "quantity": 120,
                "unit_price": 45.00,
                "amount": 5400.00,
            },
            {
                "description": "Enterprise Support License",
                "quantity": 1,
                "unit_price": 2500.00,
                "amount": 2500.00,
            },
            {
                "description": "Data Transfer (10TB egress)",
                "quantity": 10,
                "unit_price": 85.00,
                "amount": 850.00,
            },
        ],
        "subtotal": 8750.00,
        "tax": 721.88,
        "total": 9471.88,
        "currency": "USD",
    }


def _mock_contract() -> dict[str, Any]:
    return {
        "contract_title": "Master Services Agreement",
        "parties": ["AgenticAutomation Inc.", "Quantum AI Solutions Ltd."],
        "effective_date": "2026-01-15",
        "expiration_date": "2028-01-14",
        "contract_type": "Service Agreement",
        "key_terms": [
            {
                "term_name": "Service Level Agreement",
                "description": "99.95% uptime guarantee with financial credits for breaches",
            },
            {
                "term_name": "Data Processing",
                "description": "All data processed within US-East regions; GDPR and SOC2 compliant",
            },
            {
                "term_name": "Termination Clause",
                "description": "Either party may terminate with 90 days written notice",
            },
            {
                "term_name": "Intellectual Property",
                "description": "Client retains full ownership of all processed documents and extracted data",
            },
        ],
        "total_value": 450000.00,
        "currency": "USD",
        "governing_law": "State of Delaware, United States",
        "summary": (
            "Two-year master services agreement between AgenticAutomation Inc. and Quantum AI Solutions Ltd. "
            "for cloud-based document processing services. Total contract value of $450,000 USD with "
            "99.95% uptime SLA and full data sovereignty guarantees."
        ),
    }


def _mock_report() -> dict[str, Any]:
    return {
        "report_title": "Monthly Operations Report — August 2026",
        "reporting_period": "August 1–31, 2026",
        "prepared_by": "Operations Analytics Team",
        "kpis": [
            {"metric_name": "Documents Processed", "value": 14832, "unit": "documents", "trend": "up"},
            {"metric_name": "Average Latency", "value": 1.34, "unit": "seconds", "trend": "down"},
            {"metric_name": "Extraction Accuracy", "value": 97.2, "unit": "%", "trend": "up"},
            {"metric_name": "Error Rate", "value": 0.8, "unit": "%", "trend": "down"},
            {"metric_name": "Monthly Cost", "value": 12450, "unit": "USD", "trend": "flat"},
        ],
        "highlights": [
            "Document throughput increased 23% month-over-month",
            "New invoice template support reduced extraction errors by 40%",
            "Titan model migration completed for all report-type documents",
        ],
        "risks": [
            "Bedrock throttling observed during peak hours (2–4 PM EST)",
            "Three new document formats awaiting template coverage",
        ],
        "recommendations": [
            "Increase provisioned throughput for Claude 3 Sonnet during peak windows",
            "Prioritize template creation for newly identified document formats",
            "Evaluate Bedrock batch inference API for overnight bulk processing",
        ],
        "summary": (
            "August 2026 saw strong performance with 14,832 documents processed at 97.2% accuracy. "
            "Latency improved to 1.34s average. Throughput grew 23% MoM while costs held flat at $12,450. "
            "Key risk is peak-hour throttling requiring provisioned throughput adjustment."
        ),
    }


def _mock_generic(content: str) -> dict[str, Any]:
    word_count = len(content.split())
    return {
        "document_type": "general",
        "word_count": word_count,
        "content_preview": content[:200] + ("..." if len(content) > 200 else ""),
        "extracted_entities": [
            {"type": "text_block", "value": content[:500]},
        ],
        "summary": f"General document with {word_count} words processed by fallback model.",
    }
