"""
GCS Write Test

Simple script to verify we can write to a GCS folder, then read back to confirm.

Usage examples:

  python member-insights-processor/tests/test_gcs_trace_write.py \
    --gcs-uri gs://eni_storage_bucket/llm_traces/

  # Or rely on config (debug.llm_trace.remote_output_uri)
  python member-insights-processor/tests/test_gcs_trace_write.py \
    --config member-insights-processor/config/config.yaml
"""

from __future__ import annotations

import argparse
import time
from typing import Tuple, Optional
from pathlib import Path


def parse_gcs_uri(uri: str) -> Tuple[str, str]:
    if not uri.startswith("gs://"):
        raise ValueError("GCS URI must start with gs://")
    without_scheme = uri[len("gs://"):]
    parts = without_scheme.split("/", 1)
    bucket = parts[0]
    prefix = parts[1] if len(parts) > 1 else ""
    return bucket, prefix


def _resolve_config_path(config_path: str) -> Path:
    """Resolve a config path robustly from various working directories.

    Tries, in order:
      1) As-given path
      2) Strip leading 'member-insights-processor/' if present
      3) Path relative to this script's directory (../config/config.yaml)
      4) Repo-root style: 'member-insights-processor/config/config.yaml'
    """
    # 1) As given
    p = Path(config_path)
    if p.exists():
        return p

    # 2) If user is already inside member-insights-processor but passed a path
    #    starting with 'member-insights-processor/', strip it
    prefix = "member-insights-processor/"
    if config_path.startswith(prefix):
        stripped = Path(config_path[len(prefix):])
        if stripped.exists():
            return stripped

    # 3) Relative to this script location
    script_dir = Path(__file__).resolve().parent
    candidate = (script_dir.parent / "config" / "config.yaml").resolve()
    if candidate.exists():
        return candidate

    # 4) Repo-root style fallback
    repo_style = Path("member-insights-processor/config/config.yaml")
    if repo_style.exists():
        return repo_style

    # Return original for error context
    return p


def get_gcs_uri_from_config(config_path: str) -> Optional[str]:
    try:
        import yaml  # PyYAML
    except Exception as exc:
        raise RuntimeError(
            "PyYAML is required to read the config. Please install PyYAML."
        ) from exc

    resolved = _resolve_config_path(config_path)
    if not resolved.exists():
        raise FileNotFoundError(f"Config file not found: {config_path} (resolved to {resolved})")

    with open(resolved, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    debug_cfg = cfg.get("debug", {}) or {}
    llm_cfg = debug_cfg.get("llm_trace", {}) or {}
    uri = llm_cfg.get("remote_output_uri")
    return uri


def write_and_verify_gcs_text(gcs_uri: str) -> str:
    try:
        from google.cloud import storage
    except Exception as exc:
        raise RuntimeError(
            "google-cloud-storage is required. Please install it in your environment."
        ) from exc

    bucket_name, prefix = parse_gcs_uri(gcs_uri)
    if prefix and not prefix.endswith("/"):
        prefix = prefix + "/"

    ts = time.strftime("%Y%m%d_%H%M%S")
    blob_name = f"{prefix}gcs_trace_write_test_{ts}.txt"
    test_text = f"GCS write test OK @ {ts}\n"

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    # Upload test content
    blob.upload_from_string(test_text, content_type="text/plain; charset=utf-8")

    # Read back to verify
    roundtrip = blob.download_as_text(encoding="utf-8")
    if roundtrip != test_text:
        raise AssertionError("Roundtrip content mismatch. Write/read verification failed.")

    return f"gs://{bucket_name}/{blob_name}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify GCS write access for LLM traces")
    parser.add_argument(
        "--gcs-uri",
        help="Target GCS URI (e.g., gs://eni_storage_bucket/llm_traces/). Overrides config if provided.",
    )
    parser.add_argument(
        "--config",
        default="config/config.yaml",
        help="Path to config.yaml to read debug.llm_trace.remote_output_uri",
    )
    args = parser.parse_args()

    gcs_uri = args.gcs_uri
    if not gcs_uri:
        gcs_uri = get_gcs_uri_from_config(args.config)
        if not gcs_uri:
            print("❌ No --gcs-uri provided and no debug.llm_trace.remote_output_uri found in config.")
            return 1

    try:
        written_uri = write_and_verify_gcs_text(gcs_uri)
        print(f"✅ Wrote and verified test file at: {written_uri}")
        print("Note: Ensure your environment has valid GCP credentials (ADC) available.")
        return 0
    except Exception as e:
        print(f"❌ GCS write verification failed: {e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())


