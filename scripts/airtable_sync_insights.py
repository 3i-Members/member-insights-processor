#!/usr/bin/env python3
"""
Sync all latest structured insights from Supabase to Airtable.

This script queries Supabase for rows where is_latest = true in
elvis__structured_insights and iterates through the results,
writing each to Airtable using the structured writer.

Usage:
  source venv/bin/activate
  PYTHONPATH="src" python scripts/airtable_sync_insights.py [--force]

Environment:
  - .env should contain Supabase and Airtable credentials
"""

import os
import sys
import argparse
from pathlib import Path

# Ensure we can import project modules when run from repo root or scripts/
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from data_processing.supabase_client import SupabaseInsightsClient
from output_management.airtable_writer import StructuredInsightsAirtableWriter
from output_management.supabase_airtable_sync import SupabaseAirtableSync
from dotenv import load_dotenv
import yaml


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync latest Supabase structured insights to Airtable")
    parser.add_argument("--force", action="store_true", help="Force update even if recently synced")
    parser.add_argument("--limit", type=int, default=1000, help="Max number of records to fetch")
    args = parser.parse_args()

    # Load .env from project root
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    # Initialize clients
    supabase_client = SupabaseInsightsClient()

    # Load Airtable config from config/config.yaml
    cfg_path = PROJECT_ROOT / "config" / "config.yaml"
    airtable_cfg = {}
    if cfg_path.exists():
        try:
            with open(cfg_path, "r") as f:
                cfg = yaml.safe_load(f) or {}
                airtable_cfg = cfg.get("airtable", {})
        except Exception:
            airtable_cfg = {}

    airtable_writer = StructuredInsightsAirtableWriter(airtable_cfg)
    syncer = SupabaseAirtableSync(supabase_client=supabase_client, airtable_writer=airtable_writer)

    # Query Supabase for latest records
    # Using the low-level client directly to filter is_latest = true
    client = supabase_client._ensure_connection()
    table = supabase_client.TABLE_NAME
    result = (
        client.table(table)
        .select("*")
        .eq("is_latest", True)
        .eq("generator", "structured_insight")
        .limit(args.limit)
        .execute()
    )
    rows = result.data or []

    print(f"Found {len(rows)} latest insights to sync")

    successes = 0
    failures = 0
    for row in rows:
        contact_id = row.get("contact_id")
        if not contact_id:
            failures += 1
            continue
        res = syncer.sync_contact_to_airtable(contact_id, force_update=args.force)
        status = "✅" if res.success else "❌"
        print(f"{status} {contact_id}: {res.action} {res.airtable_record_id or ''} {res.error_message or ''}")
        if res.success:
            successes += 1
        else:
            failures += 1

    print(f"Done. Successes: {successes} | Failures: {failures}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())


