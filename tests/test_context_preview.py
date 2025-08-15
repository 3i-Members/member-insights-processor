import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime
from types import SimpleNamespace

import pandas as pd
import pytest

# Ensure 'src' is importable when running tests directly
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from context_management.context_manager import ContextManager
from tests import DEFAULT_CONTACT_ID, DEFAULT_STRUCTURED_INSIGHT


class StubSupabaseClient:
    def __init__(self, default_structured_insight: dict):
        self.default_structured_insight = default_structured_insight

    def get_insight_by_contact_id(self, contact_id: str):
        # Return a simple object with insights as JSON structure (not individual fields)
        d = self.default_structured_insight
        return SimpleNamespace(
            insights={
                "personal": d.get("personal", ""),
                "business": d.get("business", ""),
                "investing": d.get("investing", ""),
                "3i": d.get("3i", ""),
                "deals": d.get("deals", ""),
                "introductions": d.get("introductions", ""),
            }
        )


def _ensure_logs_dir() -> Path:
    logs_dir = PROJECT_ROOT / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def _build_fallback_dataframe(contact_id: str) -> pd.DataFrame:
    # Minimal synthetic dataset spanning two groups
    rows = [
        {
            "contact_id": contact_id,
            "eni_source_type": "airtable_notes",
            "eni_source_subtype": "investing_preferences",
            "description": "Interested in AI/ML infra and B2B SaaS",
            "eni_id": "ENI-FAKE-0001",
            "logged_date": "2024-06-01",
        },
        {
            "contact_id": contact_id,
            "eni_source_type": "airtable_notes",
            "eni_source_subtype": "investing_preferences",
            "description": "Prefers Series A companies with >$2M ARR",
            "eni_id": "ENI-FAKE-0002",
            "logged_date": "2024-06-02",
        },
        {
            "contact_id": contact_id,
            "eni_source_type": "member_requests",
            "eni_source_subtype": "requested",
            "description": "Looking to meet energy transition fund GPs",
            "eni_id": "ENI-FAKE-0003",
            "logged_date": "2024-06-03",
        },
    ]
    return pd.DataFrame(rows)


@pytest.mark.integration
def test_context_preview_log_generation():
    contact_id = DEFAULT_CONTACT_ID

    # Initialize ContextManager with a stub Supabase client providing default insight
    ctx_manager = ContextManager(
        config_file_path=str(PROJECT_ROOT / "config" / "config.yaml"),
        supabase_client=StubSupabaseClient(DEFAULT_STRUCTURED_INSIGHT),
    )

    # Try to load real data from BigQuery, fallback to synthetic data if connection fails
    connected = False
    bq = None
    try:
        from data_processing.bigquery_connector import create_bigquery_connector
        bq = create_bigquery_connector(ctx_manager.config_data)
        connected = bq.connect()
    except Exception:
        connected = False
        bq = None

    if connected:
        # Pull all data for this contact (we mimic current pipeline by pulling per type/subtype combos)
        # For preview, fetch combinations from config's processing filter like the main pipeline
        try:
            from context_management.processing_filter import create_processing_filter
            filter_file = ctx_manager.config_data.get("processing", {}).get("filter_config", {}).get("default_filter_file")
            processing_filter = create_processing_filter(filter_file) if filter_file else None
            rules = processing_filter.processing_rules if processing_filter else {}
        except Exception:
            rules = {}
        combos = bq.get_eni_combinations_for_processing(rules)

        all_dfs = []
        for (eni_type, eni_subtype) in combos:
            try:
                df = bq.load_contact_data_filtered(contact_id, eni_type, eni_subtype)
                if not df.empty:
                    all_dfs.append(df)
            except Exception:
                continue
        if all_dfs:
            contact_df = pd.concat(all_dfs, ignore_index=True)
        else:
            contact_df = _build_fallback_dataframe(contact_id)
    else:
        contact_df = _build_fallback_dataframe(contact_id)

    # Normalize subtype like the main pipeline
    if "eni_source_subtype" in contact_df.columns:
        contact_df["eni_source_subtype"] = contact_df["eni_source_subtype"].fillna("null")
        mask = (
            contact_df["eni_source_subtype"].astype(str).str.strip() == ""
        ) | contact_df["eni_source_subtype"].astype(str).str.lower().isin(["none", "nan", "nat"])
        contact_df.loc[mask, "eni_source_subtype"] = "null"

    # Group and build per-group context variables
    grouped = contact_df.groupby(["eni_source_type", "eni_source_subtype"])

    per_group_results = []
    for (eni_type, eni_subtype), group_df in grouped:
        ctx_vars = ctx_manager.build_context_variables(
            contact_id=contact_id,
            eni_source_type=eni_type,
            eni_source_subtype=eni_subtype,
            eni_group_df=group_df,
            system_prompt_key="structured_insight",
        )
        per_group_results.append({
            "eni_source_type": eni_type,
            "eni_source_subtype": eni_subtype,
            "rows_in_group": len(group_df),
            "context_variables": ctx_vars,
        })

    # Compose preview log content
    current_structured_insight = ctx_manager.get_current_structured_insight(contact_id, "structured_insight")
    llm_calls = len(per_group_results)  # One call per group in a batched-per-group strategy

    lines = []
    lines.append(f"Context Preview Report - {datetime.utcnow().isoformat()}Z\n")
    lines.append(f"Contact ID: {contact_id}\n")
    lines.append(f"LLM calls (would-be): {llm_calls}\n\n")

    # Summary table header
    lines.append("run_number | eni_source_type | eni_source_sub_type | tokens_system_plus_source_ctx | remaining_tokens | total_rows_in_group | rows_processed | total_tokens_rendered\n")
    lines.append("--- | --- | --- | --- | --- | --- | --- | ---\n")

    # Build summary rows first
    summary_rows = []
    for idx, result in enumerate(per_group_results, 1):
        ctxv = result["context_variables"]
        token_stats = ctxv.get("token_stats", {})
        tokens_system_plus_source = token_stats.get("base_tokens", 0)
        remaining_tokens = token_stats.get("available_for_new_data", 0)
        total_tokens_rendered = token_stats.get("total_rendered_tokens", 0)
        summary_rows.append(
            f"{idx} | {result['eni_source_type']} | {result['eni_source_subtype']} | {tokens_system_plus_source} | {remaining_tokens} | {ctxv.get('rows_total', 0)} | {ctxv.get('rows_used', 0)} | {total_tokens_rendered}\n"
        )

    lines.extend(summary_rows)
    lines.append("\n")

    # Detailed sections per run
    for idx, result in enumerate(per_group_results, 1):
        ctxv = result["context_variables"]
        token_stats = ctxv.get("token_stats", {})
        lines.append(f"=== Call {idx}: {result['eni_source_type']}/{result['eni_source_subtype']} ===\n")
        lines.append(f"Rows in group: {result['rows_in_group']}\n")
        lines.append("-- Rendered System Prompt (Full) --\n")
        rendered = ctxv.get("rendered_system_prompt", "").strip()
        lines.append(rendered + "\n\n")
        lines.append("-- Token Stats --\n")
        lines.append(json.dumps(token_stats, indent=2) + "\n\n")

        # Basic assertion within the loop to ensure eni_id is present in rendered content
        # (Not raising here; we'll assert after writing the log for better failure context.)

    # Write out log file
    logs_dir = _ensure_logs_dir()
    ts = time.strftime("%Y%m%d_%H%M%S")
    log_path = logs_dir / f"context_preview_{contact_id}_{ts}.md"
    log_path.write_text("".join(lines), encoding="utf-8")

    # Assert log created with content
    assert log_path.exists(), "Preview log file was not created"
    assert log_path.stat().st_size > 0, "Preview log file is empty"

    # Read back to assert ENI IDs made it into the rendered content
    content = log_path.read_text(encoding="utf-8")
    assert "ENI-" in content, "Rendered prompt is missing ENI citations"

    # Print location for convenience when running tests locally
    print(f"Context preview log written to: {log_path}") 