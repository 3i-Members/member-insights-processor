import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List


class ContextManager:
    """Consolidated context management utilities.

    Responsibilities:
    - Load YAML configuration
    - Resolve context file paths for ENI type/subtype from config
    - Read markdown files
    - Estimate tokens for budgeting
    - Build context variables for the LLM prompt per (contact_id, eni_source_type, eni_source_subtype)
    - Load and render system prompt templates
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
            return yaml.safe_load(f)

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
            except Exception:
                return ""
        return ""

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
        """Rough token estimator.

        Heuristic: ~4 characters per token on average.
        This is a simple, fast approximation suitable for budgeting.
        """
        if not text:
            return 0
        return max(1, int(len(text) / 4))

    # -----------------------------
    # Structured insight retrieval
    # -----------------------------
    def get_current_structured_insight(self, contact_id: str, system_prompt_key: str) -> str:
        """Fetch latest existing structured insight for contact from Supabase if available.

        Returns a formatted string with sections expected by the prompt template.
        """
        if not self.supabase_client:
            return ""
        try:
            existing = self.supabase_client.get_insight_by_contact_id(contact_id)
            if not existing:
                return ""

            # Prefer explicit fields; fallback to empty strings
            personal = getattr(existing, "personal", "") or ""
            business = getattr(existing, "business", "") or ""
            investing = getattr(existing, "investing", "") or ""
            three_i = getattr(existing, "three_i", "") or getattr(existing, "threeI", "") or ""
            deals = getattr(existing, "deals", "") or ""
            introductions = getattr(existing, "introductions", "") or ""

            formatted = (
                f"## Personal\n{personal}\n\n"
                f"## Business\n{business}\n\n"
                f"## Investing\n{investing}\n\n"
                f"## 3i\n{three_i}\n\n"
                f"## Deals\n{deals}\n\n"
                f"## Introductions\n{introductions}\n"
            )
            return formatted
        except Exception:
            return ""

    # -----------------------------
    # Build 'new_data_to_process' within token budget
    # -----------------------------
    def _build_new_data_block(self, eni_rows: List[Dict[str, Any]], available_tokens: int) -> Tuple[str, int]:
        """Create a bullet list from 'description' fields, truncated to fit available tokens.

        Returns (text_block, rows_used).
        """
        lines: List[str] = []
        used_tokens = 0
        rows_used = 0
        for row in eni_rows:
            desc = row.get("description")
            if not desc:
                continue
            line = f"- {str(desc).strip()}\n"
            line_tokens = self.estimate_tokens(line)
            if used_tokens + line_tokens > max(0, available_tokens):
                break
            lines.append(line)
            used_tokens += line_tokens
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
        """Produce the four context variables for the LLM prompt, with token-aware new data.

        Returns dict with keys:
        - current_structured_insight
        - eni_source_type_context
        - eni_source_subtype_context
        - new_data_to_process
        - system_prompt_template
        - rendered_system_prompt_without_new_data
        - rendered_system_prompt
        - token_stats: budgeting info
        - rows_used: number of rows included in new_data_to_process
        - rows_total: total rows in group
        """
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
        # Render system prompt with empty new data to count base tokens
        prefill_vars = {
            "current_structured_insight": current_structured_insight,
            "eni_source_type_context": type_ctx,
            "eni_source_subtype_context": subtype_ctx,
            "new_data_to_process": "",
        }
        rendered_without_new = self.render_system_prompt(system_prompt_template, prefill_vars)
        base_tokens = self.estimate_tokens(rendered_without_new)

        # Safety buffer for headings/formatting
        overhead_tokens = 500
        total_reserved = self.reserve_output_tokens + base_tokens + overhead_tokens
        available_for_new_data = max(0, self.context_window_tokens - total_reserved)
        # Also cap per-group to avoid a single group consuming everything
        available_for_new_data = min(available_for_new_data, self.max_new_data_tokens_per_group)

        # 5) Build new_data_to_process from DF rows
        eni_rows: List[Dict[str, Any]] = []
        rows_total = 0
        try:
            for _, row in eni_group_df.iterrows():
                rows_total += 1
                eni_rows.append({
                    "description": row.get("description"),
                })
        except Exception:
            pass

        new_data_block, rows_used = self._build_new_data_block(eni_rows, available_for_new_data)

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