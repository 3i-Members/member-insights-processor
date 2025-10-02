"""
Run-level structured summary writer.

Writes machine-readable artifacts for each run:
- var/logs/runs/{run_id}/summary.json        (final roll-up)
- var/logs/runs/{run_id}/summary.ndjson      (append-only events stream)
- var/logs/runs/{run_id}/contacts/{id}.json  (per-contact results)
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class RunSummaryWriter:
    """Utility to persist structured run summaries and events to disk."""

    def __init__(self, run_id: str, base_dir: str = "var/logs/runs") -> None:
        self.run_id = run_id
        self.base_dir = Path(base_dir)
        self.run_dir = self.base_dir / run_id
        self.contacts_dir = self.run_dir / "contacts"
        # Ensure directories exist
        self.contacts_dir.mkdir(parents=True, exist_ok=True)

        # Event stream file path
        self.ndjson_path = self.run_dir / "summary.ndjson"
        # Final summary JSON path
        self.summary_json_path = self.run_dir / "summary.json"

        # Minimal run metadata header
        self.append_event({
            "event": "run_initialized",
            "run_id": self.run_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

    def append_event(self, event: Dict[str, Any]) -> None:
        """Append an event to the NDJSON stream with an auto timestamp and run_id."""
        safe_event = dict(event or {})
        safe_event.setdefault("run_id", self.run_id)
        safe_event.setdefault("timestamp", datetime.utcnow().isoformat() + "Z")
        # Ensure parent exists
        self.run_dir.mkdir(parents=True, exist_ok=True)
        with self.ndjson_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(safe_event, ensure_ascii=False) + "\n")

    def write_contact_summary(self, contact_id: str, payload: Dict[str, Any]) -> Path:
        """Write per-contact summary JSON and return the file path."""
        file_path = self.contacts_dir / f"{contact_id}.json"
        data = dict(payload or {})
        data.setdefault("run_id", self.run_id)
        data.setdefault("contact_id", contact_id)
        data.setdefault("written_at", datetime.utcnow().isoformat() + "Z")
        with file_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        # Also append an event for discoverability
        self.append_event({
            "event": "contact_summary_written",
            "contact_id": contact_id,
            "path": str(file_path),
        })
        return file_path

    def write_final_summary(self, summary: Dict[str, Any]) -> Path:
        """Write the final roll-up JSON and return the file path."""
        data = dict(summary or {})
        data.setdefault("run_id", self.run_id)
        data.setdefault("written_at", datetime.utcnow().isoformat() + "Z")
        self.run_dir.mkdir(parents=True, exist_ok=True)
        with self.summary_json_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        self.append_event({
            "event": "final_summary_written",
            "path": str(self.summary_json_path),
            "totals": {
                "total_contacts": data.get("total_contacts"),
                "successful_contacts": data.get("successful_contacts"),
                "failed_contacts": data.get("failed_contacts"),
            },
        })
        return self.summary_json_path

    def get_run_directory(self) -> Path:
        return self.run_dir
