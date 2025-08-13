import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
import logging

logger = logging.getLogger(__name__)


class ContextManager:
    """Consolidated context management utilities.

    Responsibilities:
    - Load YAML configuration
    - Resolve context file paths for ENI type/subtype from config
    - Read markdown files
    - Estimate tokens for budgeting
    - Build context variables for the LLM prompt per (contact_id, eni_source_type, eni_source_subtype)
    - Load and render system prompt templates
    - Provide config accessors (AI provider, Airtable, Supabase, etc.)
    - Validate configuration and context directory structure
    """

    def __init__(self, config_file_path: str = "config/config.yaml", supabase_client: Optional[Any] = None):
        self.config_file_path = config_file_path
        self.supabase_client = supabase_client
        self.config_data = self._load_config(config_file_path)

        # Defaults for token/window management
        processing_cfg = self.config_data.get("processing", {})
        self.context_window_tokens: int = int(processing_cfg.get("context_window_tokens", 200000))
        self.reserve_output_tokens: int = int(processing_cfg.get("reserve_output_tokens", 8000))
        self.max_new_data_tokens_per_group: int = int(processing_cfg.get("max_new_data_tokens_per_group", 12000))

    # -----------------------------
    # Config and file IO helpers
    # -----------------------------
    def _load_config(self, path: str) -> Dict[str, Any]:
        cfg_path = Path(path)
        if not cfg_path.exists():
            # Try to resolve relative to this file's parent
            fallback = Path(__file__).parents[2] / "config" / "config.yaml"
            cfg_path = fallback if fallback.exists() else cfg_path
        with open(cfg_path, "r") as f:
            return yaml.safe_load(f) or {}

    def read_markdown_file(self, path: Optional[str]) -> str:
        if not path:
            return ""
        file_path = Path(path)
        # If relative, make it relative to repo root (two levels up from src/)
        if not file_path.is_absolute():
            root_guess = Path(__file__).parents[2]
            file_path = root_guess / path
        if file_path.exists():
            try:
                return file_path.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning(f"Failed reading markdown {file_path}: {e}")
                return ""
        return ""

    # -----------------------------
    # Config accessors
    # -----------------------------
    def get_processing_config(self) -> Dict[str, Any]:
        return self.config_data.get("processing", {})

    def get_ai_provider(self) -> str:
        return self.get_processing_config().get("ai_provider", "gemini")

    def get_openai_config(self) -> Dict[str, Any]:
        return self.config_data.get("openai", {})

    def get_gemini_config(self) -> Dict[str, Any]:
        return self.config_data.get("gemini", {})

    def get_anthropic_config(self) -> Dict[str, Any]:
        return self.config_data.get("anthropic", {})

    def get_airtable_config(self) -> Dict[str, Any]:
        return self.config_data.get("airtable", {})

    def get_supabase_config(self) -> Dict[str, Any]:
        return self.config_data.get("supabase", {})

    def get_filter_config(self) -> Dict[str, Any]:
        return self.get_processing_config().get("filter_config", {})

    def get_default_filter_file(self) -> Optional[str]:
        return self.get_filter_config().get("default_filter_file")

    def get_all_system_prompts(self) -> Dict[str, str]:
        return self.config_data.get("system_prompts", {})

    def get_available_eni_types(self) -> List[str]:
        return list(self.config_data.get("eni_mappings", {}).keys())

    # -----------------------------
    # System prompt handling
    # -----------------------------
    def get_system_prompt_template(self, system_prompt_key: str) -> str:
        mapping = self.config_data.get("system_prompts", {})
        prompt_path = mapping.get(system_prompt_key)
        return self.read_markdown_file(prompt_path) if prompt_path else ""

    def render_system_prompt(self, template: str, variables: Dict[str, str]) -> str:
        rendered = template or ""
        for key, value in variables.items():
            rendered = rendered.replace(f"{{{{{key}}}}}", value or "")
        return rendered

    # -----------------------------
    # Context path resolution
    # -----------------------------
    def get_context_file_paths(self, eni_source_type: str, eni_source_subtype: Optional[str]) -> Dict[str, Optional[str]]:
        """Return dict with 'default' and 'subtype' context file paths if configured.

        - If subtype is 'null' or None, only default is provided.
        - If subtype provided but not found, returns default and None for subtype.
        """
        mappings = self.config_data.get("eni_mappings", {})
        type_mapping = mappings.get(str(eni_source_type), {})

        default_path = type_mapping.get("default")
        subtype_path = None
        if eni_source_subtype and str(eni_source_subtype).lower() != "null":
            subtype_path = type_mapping.get(str(eni_source_subtype))
        return {"default": default_path, "subtype": subtype_path}

    # -----------------------------
    # Token estimation
    # -----------------------------
    def estimate_tokens(self, text: str) -> int:
        """Rough token estimator (≈4 chars/token)."""
        if not text:
            return 0
        return max(1, int(len(text) / 4))

    # -----------------------------
    # Structured insight retrieval
    # -----------------------------
    def get_current_structured_insight(self, contact_id: str, system_prompt_key: str) -> str:
        if not self.supabase_client:
            return ""
        try:
            existing = self.supabase_client.get_insight_by_contact_id(contact_id)
            if not existing:
                return ""
            personal = getattr(existing, "personal", "") or ""
            business = getattr(existing, "business", "") or ""
            investing = getattr(existing, "investing", "") or ""
            three_i = getattr(existing, "three_i", "") or getattr(existing, "threeI", "") or ""
            deals = getattr(existing, "deals", "") or ""
            introductions = getattr(existing, "introductions", "") or ""
            return (
                f"## Personal\n{personal}\n\n"
                f"## Business\n{business}\n\n"
                f"## Investing\n{investing}\n\n"
                f"## 3i\n{three_i}\n\n"
                f"## Deals\n{deals}\n\n"
                f"## Introductions\n{introductions}\n"
            )
        except Exception:
            return ""

    # -----------------------------
    # Build 'new_data_to_process' within token budget
    # -----------------------------
    def _build_new_data_block(self, eni_rows: List[Dict[str, Any]], available_tokens: int, source_type_main: str) -> Tuple[str, int]:
        lines: List[str] = []
        used_tokens = 0
        rows_used = 0
        for row in eni_rows:
            desc = row.get("description")
            if not desc:
                continue
            eni_id_val = row.get("eni_id")
            logged_date_val = row.get("logged_date")

            # Normalize values
            desc_str = str(desc).strip()
            eni_id_str = "" if eni_id_val is None else str(eni_id_val).strip()
            date_str_raw = "" if logged_date_val is None else str(logged_date_val).strip()
            date_str = date_str_raw if date_str_raw and date_str_raw.lower() not in ("nan", "nat", "none", "null") else "N/A"

            # Build two-line entry per row: description + citation sub-bullet including source_type
            line_main = f"- {desc_str}\n"
            line_cite = f"  * [{date_str},{eni_id_str},{source_type_main}]\n"
            combined = line_main + line_cite
            combined_tokens = self.estimate_tokens(combined)

            if used_tokens + combined_tokens > max(0, available_tokens):
                break
            lines.append(combined)
            used_tokens += combined_tokens
            rows_used += 1
        return ("".join(lines), rows_used)

    # -----------------------------
    # Public API: Build context variables per group
    # -----------------------------
    def build_context_variables(
        self,
        contact_id: str,
        eni_source_type: str,
        eni_source_subtype: Optional[str],
        eni_group_df,
        system_prompt_key: str,
    ) -> Dict[str, Any]:
        """Produce the four context variables and rendered system prompt with token-aware new data."""
        # 1) Existing structured insight
        current_structured_insight = self.get_current_structured_insight(contact_id, system_prompt_key)

        # 2) Resolve and load type/subtype contexts
        paths = self.get_context_file_paths(eni_source_type, eni_source_subtype)
        type_ctx = self.read_markdown_file(paths.get("default")) or ""
        subtype_ctx = ""
        if eni_source_subtype and str(eni_source_subtype).lower() != "null":
            subtype_ctx = self.read_markdown_file(paths.get("subtype")) or ""

        # 3) Load system prompt template
        system_prompt_template = self.get_system_prompt_template(system_prompt_key)

        # 4) Token budgeting (before adding new data)
        prefill_vars = {
            "current_structured_insight": current_structured_insight,
            "eni_source_type_context": type_ctx,
            "eni_source_subtype_context": subtype_ctx,
            "new_data_to_process": "",
        }
        rendered_without_new = self.render_system_prompt(system_prompt_template, prefill_vars)
        base_tokens = self.estimate_tokens(rendered_without_new)

        overhead_tokens = 500
        total_reserved = self.reserve_output_tokens + base_tokens + overhead_tokens
        available_for_new_data = max(0, self.context_window_tokens - total_reserved)
        available_for_new_data = min(available_for_new_data, self.max_new_data_tokens_per_group)

        # 5) Build new_data_to_process from DF rows
        eni_rows: List[Dict[str, Any]] = []
        rows_total = 0
        try:
            for _, row in eni_group_df.iterrows():
                rows_total += 1
                eni_rows.append({
                    "description": row.get("description"),
                    "eni_id": row.get("eni_id"),
                    "logged_date": row.get("logged_date"),
                })
        except Exception:
            pass

        new_data_block, rows_used = self._build_new_data_block(eni_rows, available_for_new_data, eni_source_type)

        # 6) Render full system prompt with new data
        final_vars = {
            "current_structured_insight": current_structured_insight,
            "eni_source_type_context": type_ctx,
            "eni_source_subtype_context": subtype_ctx,
            "new_data_to_process": new_data_block,
        }
        rendered_full = self.render_system_prompt(system_prompt_template, final_vars)

        return {
            "current_structured_insight": current_structured_insight,
            "eni_source_type_context": type_ctx,
            "eni_source_subtype_context": subtype_ctx,
            "new_data_to_process": new_data_block,
            "system_prompt_template": system_prompt_template,
            "rendered_system_prompt_without_new_data": rendered_without_new,
            "rendered_system_prompt": rendered_full,
            "token_stats": {
                "context_window_tokens": self.context_window_tokens,
                "reserve_output_tokens": self.reserve_output_tokens,
                "base_tokens": base_tokens,
                "overhead_tokens": overhead_tokens,
                "available_for_new_data": available_for_new_data,
                "new_data_tokens_used": self.estimate_tokens(new_data_block),
                "total_rendered_tokens": base_tokens + self.estimate_tokens(new_data_block),
            },
            "rows_used": rows_used,
            "rows_total": rows_total,
        }

    # -----------------------------
    # Validation methods
    # -----------------------------
    def validate_configuration(self) -> Dict[str, Any]:
        report = {
            'valid': True,
            'issues': [],
            'warnings': [],
            'statistics': {}
        }
        try:
            cfg = self.config_data
            if not cfg:
                report['valid'] = False
                report['issues'].append("Configuration data is empty or failed to load")
                return report

            # ENI mappings
            eni_mappings = cfg.get('eni_mappings', {})
            if not eni_mappings:
                report['warnings'].append("No ENI mappings found in configuration")
            else:
                total_mappings = 0
                for eni_type, subtypes in eni_mappings.items():
                    if not isinstance(subtypes, dict):
                        report['issues'].append(f"ENI type '{eni_type}' mappings should be a dictionary")
                        continue
                    total_mappings += len(subtypes)
                    for subtype, file_path in subtypes.items():
                        if not Path(file_path).exists():
                            report['warnings'].append(
                                f"Context file not found: {file_path} (for {eni_type}/{subtype})"
                            )
                report['statistics']['total_eni_mappings'] = total_mappings

            # System prompts
            system_prompts = cfg.get('system_prompts', {})
            if not system_prompts:
                report['warnings'].append("No system prompts found in configuration")
            else:
                report['statistics']['total_system_prompts'] = len(system_prompts)
                for prompt_key, file_path in system_prompts.items():
                    if not Path(file_path).exists():
                        report['warnings'].append(
                            f"System prompt file not found: {file_path} (for key '{prompt_key}')"
                        )

            # BigQuery config
            bigquery_config = cfg.get('bigquery', {})
            required_bq_fields = ['project_id', 'dataset_id', 'table_name']
            missing_bq_fields = [f for f in required_bq_fields if not bigquery_config.get(f)]
            if missing_bq_fields:
                report['issues'].append(
                    f"Missing required BigQuery configuration fields: {missing_bq_fields}"
                )

            # Airtable config
            airtable_config = cfg.get('airtable', {})
            if airtable_config and not airtable_config.get('field_mapping'):
                report['warnings'].append("Airtable field mapping is empty")

            if report['issues']:
                report['valid'] = False
            return report
        except Exception as e:
            report['valid'] = False
            report['issues'].append(f"Unexpected error during validation: {str(e)}")
            return report

    def validate_context_structure(self, base_context_dir: str = "context") -> Dict[str, Any]:
        report = {
            'valid': True,
            'issues': [],
            'statistics': {
                'total_eni_types': 0,
                'total_context_files': 0,
                'empty_files': [],
                'large_files': []
            }
        }
        try:
            base_path = Path(base_context_dir)
            if not base_path.exists():
                report['valid'] = False
                report['issues'].append(f"Context directory does not exist: {base_path}")
                return report

            total_files = 0
            for eni_type_dir in base_path.iterdir():
                if eni_type_dir.is_dir():
                    report['statistics']['total_eni_types'] += 1
                    md_files = list(eni_type_dir.glob("*.md"))
                    total_files += len(md_files)
                    if not md_files:
                        report['issues'].append(f"No markdown files found in {eni_type_dir}")
                    for md_file in md_files:
                        try:
                            file_size = md_file.stat().st_size
                            if file_size == 0:
                                report['statistics']['empty_files'].append(str(md_file))
                            elif file_size > 100 * 1024:
                                report['statistics']['large_files'].append({
                                    'file': str(md_file),
                                    'size_kb': round(file_size / 1024, 2)
                                })
                            with open(md_file, 'r', encoding='utf-8') as f:
                                f.read()
                        except UnicodeDecodeError:
                            report['issues'].append(f"Unicode decode error in {md_file}")
                        except Exception as e:
                            report['issues'].append(f"Error reading {md_file}: {str(e)}")
            report['statistics']['total_context_files'] = total_files
            if report['issues']:
                report['valid'] = False
            return report
        except Exception as e:
            report['valid'] = False
            report['issues'].append(f"Unexpected error during validation: {str(e)}")
            return report 