"""
Main Processing Pipeline

This module orchestrates the complete member insights processing workflow,
integrating all components for end-to-end data processing and AI insights generation.
"""

import os
import logging
import pandas as pd
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from uuid import uuid4
import threading

# Load environment variables from .env file
# Try multiple locations: project root, src/, src/member_insights_processor/
env_paths = [
    Path(__file__).parent.parent.parent.parent / ".env",  # Project root
    Path(__file__).parent.parent.parent / ".env",  # src/
    Path(__file__).parent.parent / ".env",  # src/member_insights_processor/
]

env_loaded = False
for env_path in env_paths:
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Loaded environment variables from: {env_path}")
        env_loaded = True
        break

if not env_loaded:
    print("⚠️  No .env file found, using system environment variables")

# Import all components
from member_insights_processor.io.readers.bigquery import create_bigquery_connector
from member_insights_processor.io.log_manager import create_log_manager
from member_insights_processor.io.readers.supabase import SupabaseInsightsClient
from member_insights_processor.io.writers.supabase import SupabaseInsightsProcessor
from member_insights_processor.pipeline.config import create_config_loader
from member_insights_processor.io.readers.markdown import create_markdown_reader
from member_insights_processor.pipeline.filters import create_processing_filter
from member_insights_processor.pipeline.context import ContextManager
from member_insights_processor.core.llm.gemini import create_gemini_processor
from member_insights_processor.core.llm.openai import create_openai_processor
from member_insights_processor.core.llm.anthropic import AnthropicProcessor
from member_insights_processor.io.writers.markdown import create_markdown_writer
from member_insights_processor.io.writers.json import create_json_writer
from member_insights_processor.io.writers.airtable import create_structured_airtable_writer
from member_insights_processor.core.utils.logging import create_enhanced_logger
from member_insights_processor.core.utils.tokens import estimate_tokens
from member_insights_processor.io.writers.markdown import LLMTraceWriter
from member_insights_processor.io.writers.supabase_sync import SupabaseAirtableSync
from member_insights_processor.core.utils.claims import create_local_claimer
from member_insights_processor.core.utils.run_summary import RunSummaryWriter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("var/logs/processing.log"), logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


class MemberInsightsProcessor:
    """Main processor that orchestrates the complete member insights workflow."""

    def __init__(
        self, config_file_path: str = "config/config.yaml", filter_file_path: Optional[str] = None
    ):
        """
        Initialize the member insights processor.

        Args:
            config_file_path: Path to the configuration file
            filter_file_path: Optional path to processing filter file (overrides default)
        """
        self.config_file_path = config_file_path
        self.filter_file_path = filter_file_path
        self.config_loader = None
        self.bigquery_connector = None
        self.log_manager = None
        self.markdown_reader = None
        self.processing_filter = None
        self.ai_processor = None  # Will be either Gemini or OpenAI
        self.markdown_writer = None
        self.airtable_writer = None
        self.json_writer = None
        self.structured_airtable_writer = None
        self.enhanced_logger = None
        self.context_manager = None

        # Supabase components
        self.supabase_client = None
        self.supabase_processor = None
        self.supabase_airtable_sync = None
        self.run_summary_writer = None

        self._initialize_components()

    def _initialize_components(self) -> None:
        """Initialize all processing components."""
        try:
            # Load configuration (legacy loader retained but primary access will be via ContextManager)
            self.config_loader = create_config_loader(self.config_file_path)
            logger.info("Configuration loaded successfully")

            # Initialize Context Manager with config
            self.context_manager = ContextManager(
                config_file_path=self.config_file_path,
                supabase_client=None,
            )
            logger.info("Context manager initialized")

            # Initialize enhanced logging system
            logging_config = self.context_manager.config_data.get("logging", {})
            self.enhanced_logger = create_enhanced_logger(logging_config)
            self.enhanced_logger.logger.info("Enhanced logging system initialized")

            # Initialize BigQuery connector
            self.bigquery_connector = create_bigquery_connector(self.config_loader.config_data)

            # Initialize log manager
            self.log_manager = create_log_manager()

            # Initialize markdown reader
            self.markdown_reader = create_markdown_reader()

            # Initialize processing filter
            filter_file = self.filter_file_path or self.context_manager.get_default_filter_file()
            if filter_file:
                self.processing_filter = create_processing_filter(filter_file)
                logger.info(f"Processing filter loaded from: {filter_file}")
            else:
                logger.warning("No processing filter configured - all records will be processed")

            # Initialize AI processor (OpenAI, Gemini, or Anthropic based on configuration)
            ai_provider = self.context_manager.get_ai_provider()

            if ai_provider.lower() == "openai":
                openai_config = self.context_manager.get_openai_config()
                self.ai_processor = create_openai_processor(config=openai_config)
                logger.info("Initialized OpenAI processor")
            elif ai_provider.lower() == "anthropic":
                anthropic_config = self.context_manager.get_anthropic_config()
                self.ai_processor = AnthropicProcessor(
                    model_name=anthropic_config.get("model_name", "claude-3-5-sonnet-20241022"),
                    generation_config=anthropic_config.get("generation_config", {}),
                )
                logger.info("Initialized Anthropic processor")
            else:
                gemini_config = self.context_manager.get_gemini_config()
                self.ai_processor = create_gemini_processor(config=gemini_config)
                logger.info("Initialized Gemini processor")

            # Initialize markdown writer
            self.markdown_writer = create_markdown_writer()

            # Initialize JSON writer for structured insights
            self.json_writer = create_json_writer()

            # Initialize Airtable writer for structured insights (optional)
            airtable_config = self.context_manager.get_airtable_config()
            if airtable_config:
                self.structured_airtable_writer = create_structured_airtable_writer(
                    config=airtable_config
                )

            # Initialize Supabase components
            supabase_config = self.context_manager.get_supabase_config()
            if supabase_config and supabase_config.get("enable_supabase_storage", True):
                try:
                    self.supabase_client = SupabaseInsightsClient()
                    self.supabase_processor = SupabaseInsightsProcessor(
                        self.supabase_client, batch_size=supabase_config.get("batch_size", 10)
                    )
                    logger.info("Supabase components initialized successfully")
                except Exception as e:
                    logger.warning(f"Failed to initialize Supabase components: {e}")
                    logger.info("Continuing without Supabase integration")
            else:
                logger.info("Supabase integration disabled in configuration")

            # Attach Supabase client to context manager if available
            try:
                if self.context_manager:
                    self.context_manager.supabase_client = self.supabase_client
            except Exception:
                pass

            # Initialize Supabase→Airtable sync helper if both sides are available
            try:
                if self.supabase_client and self.structured_airtable_writer:
                    self.supabase_airtable_sync = SupabaseAirtableSync(
                        supabase_client=self.supabase_client,
                        airtable_writer=self.structured_airtable_writer,
                    )
                    logger.info("Initialized Supabase→Airtable sync helper")
            except Exception as e:
                logger.warning(f"Failed to initialize Supabase→Airtable sync helper: {e}")

            logger.info("All components initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize components: {str(e)}")
            raise

    def validate_setup(self) -> Dict[str, Any]:
        """
        Validate the complete setup and return a report.

        Returns:
            Dict[str, Any]: Validation report
        """
        report = {"valid": True, "component_status": {}, "issues": [], "warnings": []}

        try:
            # Validate configuration (moved to ContextManager)
            config_validation = self.context_manager.validate_configuration()
            report["component_status"]["config"] = config_validation
            if not config_validation["valid"]:
                report["valid"] = False
                report["issues"].extend(config_validation["issues"])

            # Validate BigQuery connection
            if self.bigquery_connector:
                bq_connected = self.bigquery_connector.connect()
                report["component_status"]["bigquery"] = {"connected": bq_connected}
                if not bq_connected:
                    report["issues"].append("BigQuery connection failed")
                    report["valid"] = False
            else:
                report["issues"].append("BigQuery connector not initialized")
                report["valid"] = False

            # Validate Gemini processor (if Gemini API key is available)
            gemini_api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            if gemini_api_key:
                try:
                    from member_insights_processor.core.llm.gemini import create_gemini_processor

                    gemini_test_processor = create_gemini_processor()
                    gemini_info = gemini_test_processor.get_model_info()
                    report["component_status"]["gemini"] = gemini_info
                    if not gemini_info.get("connection_test", False):
                        report["warnings"].append("Gemini API connection test failed")
                except Exception as e:
                    report["warnings"].append(f"Gemini API connection test failed: {str(e)}")
                    report["component_status"]["gemini"] = {
                        "error": str(e),
                        "connection_test": False,
                    }
            else:
                report["component_status"]["gemini"] = {
                    "connection_test": False,
                    "api_configured": False,
                }
                report["warnings"].append("Gemini API key not configured")

            # Validate context structure (moved to ContextManager)
            context_validation = self.context_manager.validate_context_structure()
            report["component_status"]["context"] = context_validation
            if not context_validation["valid"]:
                report["warnings"].extend(context_validation["issues"])

            # Validate output directory
            if self.markdown_writer:
                output_validation = self.markdown_writer.validate_output_directory()
                report["component_status"]["output"] = output_validation
                if not output_validation["valid"]:
                    report["issues"].extend(output_validation["issues"])

            # Validate Airtable (if configured)
            airtable_api_key = os.environ.get("AIRTABLE_API_KEY")
            airtable_base_id = os.environ.get("AIRTABLE_BASE_ID")
            airtable_table_id = os.environ.get("AIRTABLE_TABLE_ID")

            if airtable_api_key and airtable_base_id and airtable_table_id:
                if self.airtable_writer:
                    airtable_info = self.airtable_writer.get_table_info()
                    report["component_status"]["airtable"] = airtable_info
                    if not airtable_info.get("connection_test", False):
                        report["warnings"].append("Airtable connection test failed")
                else:
                    report["warnings"].append(
                        "Airtable writer not initialized despite having credentials"
                    )
            elif airtable_api_key:
                report["component_status"]["airtable"] = {
                    "api_configured": True,
                    "connection_test": False,
                    "missing_config": [],
                }
                missing = []
                if not airtable_base_id:
                    missing.append("AIRTABLE_BASE_ID")
                if not airtable_table_id:
                    missing.append("AIRTABLE_TABLE_ID")
                report["component_status"]["airtable"]["missing_config"] = missing
                report["warnings"].append(
                    f"Airtable partially configured - missing: {', '.join(missing)}"
                )
            else:
                report["component_status"]["airtable"] = {
                    "api_configured": False,
                    "connection_test": False,
                }
                report["warnings"].append("Airtable API key not configured")

            logger.info(
                f"Setup validation complete: {len(report['issues'])} issues, {len(report['warnings'])} warnings"
            )
            return report

        except Exception as e:
            report["valid"] = False
            report["issues"].append(f"Validation error: {str(e)}")
            return report

    def process_contact(
        self, contact_id: str, system_prompt_key: str = "structured_insight", dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Process a single contact's data.

        Args:
            contact_id: The contact ID to process
            system_prompt_key: System prompt key to use (only structured_insight supported)
            dry_run: If True, don't save results or update logs

        Returns:
            Dict[str, Any]: Processing results
        """
        result = {
            "contact_id": contact_id,
            "success": False,
            "processed_eni_ids": [],
            "skipped_eni_ids": [],
            "errors": [],
            "files_created": [],
            "airtable_records": [],
            "airtable_final_sync": None,
            # Token-loss diagnostics
            "token_loss_events": 0,
            "token_loss_groups_skipped": 0,
            "token_loss_records_skipped": 0,
        }

        # Per-contact token metrics summary (accumulate accepted iterations)
        contact_est_input_tokens = 0
        contact_est_insights_tokens_latest = 0
        contact_generation_time_seconds = 0.0

        try:
            # Optional LLM trace setup
            debug_cfg = self.context_manager.config_data.get("debug", {}) or {}
            llm_trace_cfg = (debug_cfg.get("llm_trace") or {}) if debug_cfg else {}
            llm_trace_enabled = bool(llm_trace_cfg.get("enabled"))
            trace_file_path = None
            trace_writer = None
            if llm_trace_enabled:
                trace_writer = LLMTraceWriter(
                    llm_trace_cfg.get("output_dir", "var/logs/llm_traces")
                )
                trace_file_path = trace_writer.start_trace(
                    contact_id,
                    llm_trace_cfg.get(
                        "file_naming_pattern", "llm_trace_{contact_id}_{timestamp}.md"
                    ),
                )

            # Ensure BigQuery connection is established
            if not self.bigquery_connector.connect():
                result["errors"].append("Failed to connect to BigQuery")
                return result

            # Get processing rules from filter configuration
            processing_rules = None
            if self.processing_filter:
                processing_rules = self.processing_filter.processing_rules
                logger.info(f"Using processing filter rules for contact {contact_id}")
            else:
                logger.info(f"No processing filter configured - skipping contact {contact_id}")
                result["success"] = True
                return result

            # Get ENI type/subtype combinations to process
            # NOTE: This will ALWAYS include NULL subtypes first, then any explicitly defined subtypes
            eni_combinations = self.bigquery_connector.get_eni_combinations_for_processing(
                processing_rules
            )

            if not eni_combinations:
                logger.info(f"No ENI combinations to process for contact {contact_id}")
                result["success"] = True
                return result

            # Use a consolidated ENI id so all groups merge into a single Supabase record per contact
            consolidated_eni_id = f"COMBINED-{contact_id}-ALL"

            # Process per group: load, build context, call LLM, upsert, and mark processed per group
            total_loaded = 0
            for eni_source_type, eni_source_subtype in eni_combinations:
                try:
                    eni_data = self.bigquery_connector.load_contact_data_filtered(
                        contact_id=contact_id,
                        eni_source_type=eni_source_type,
                        eni_source_subtype=eni_source_subtype,
                    )

                    if eni_data.empty:
                        continue
                    total_loaded += len(eni_data)
                    subtype_desc = f"/{eni_source_subtype}" if eni_source_subtype else ""
                    logger.info(
                        f"Loaded {len(eni_data)} records for {contact_id}, {eni_source_type}{subtype_desc}"
                    )

                    # Normalize subtype for consistency
                    eni_data["eni_source_subtype"] = eni_data["eni_source_subtype"].fillna("null")
                    mask = (
                        eni_data["eni_source_subtype"].astype(str).str.strip() == ""
                    ) | eni_data["eni_source_subtype"].astype(str).str.lower().isin(
                        ["none", "nan", "nat"]
                    )
                    eni_data.loc[mask, "eni_source_subtype"] = "null"

                    # Build context variables for this group
                    ctx_vars = self.context_manager.build_context_variables(
                        contact_id=contact_id,
                        eni_source_type=eni_source_type,
                        eni_source_subtype=eni_source_subtype,
                        eni_group_df=eni_data,
                        system_prompt_key=system_prompt_key,
                    )

                    # Readable token diagnostics for this group
                    token_stats = ctx_vars.get("token_stats", {})
                    logger.info(
                        (
                            f"[CTX] {contact_id} {eni_source_type}/{eni_source_subtype} "
                            f"rows_total={ctx_vars.get('rows_total', 0)} rows_used={ctx_vars.get('rows_used', 0)} | "
                            f"existing_summary_tokens={token_stats.get('existing_summary_tokens', 0)} "
                            f"base_tokens={token_stats.get('base_tokens', 0)} new_data_tokens_used={token_stats.get('new_data_tokens_used', 0)} "
                            f"available_for_new_data={token_stats.get('available_for_new_data', 0)} rendered_full_tokens={token_stats.get('rendered_full_tokens', 0)}"
                        )
                    )

                    # Use fully-rendered system prompt from ContextManager (matches preview logic)
                    full_rendered_prompt = ctx_vars.get("rendered_system_prompt") or ""

                    # LLM call for this group
                    if self.enhanced_logger:
                        self.enhanced_logger.log_ai_call_start(
                            (
                                self.ai_processor.model_name
                                if hasattr(self.ai_processor, "model_name")
                                else "AI"
                            ),
                            "structured_insight",
                            f"{eni_source_type}/{eni_source_subtype}",
                            len(eni_data),
                        )
                    start_time = time.time()
                    insights = self.ai_processor.generate_from_full_prompt(full_rendered_prompt)
                    ai_duration = time.time() - start_time
                    if self.enhanced_logger:
                        self.enhanced_logger.log_ai_call_end(
                            (
                                self.ai_processor.model_name
                                if hasattr(self.ai_processor, "model_name")
                                else "AI"
                            ),
                            "structured_insight",
                            f"{eni_source_type}/{eni_source_subtype}",
                            bool(insights),
                            ai_duration,
                            len(insights) if insights else 0,
                        )

                    # Append trace for request
                    if llm_trace_enabled and trace_writer and trace_file_path:
                        if llm_trace_cfg.get("include_rendered_prompts", True):
                            trace_writer.append_section(
                                trace_file_path,
                                f"Request: {eni_source_type}/{eni_source_subtype}",
                                full_rendered_prompt,
                            )
                        if llm_trace_cfg.get("include_token_stats", True):
                            import json as _json

                            trace_writer.append_section(
                                trace_file_path, "Token Stats", _json.dumps(token_stats, indent=2)
                            )

                    if not insights:
                        result["errors"].append(
                            f"Failed to generate insights for {contact_id} {eni_source_type}/{eni_source_subtype}"
                        )
                        continue

                    # Token-loss guard: compare output vs existing summary tokens
                    # NOTE: Token-loss retry logic is disabled for versioned insights since we can audit previous versions
                    # Keeping this code commented for potential future reuse
                    # existing_summary_tokens = token_stats.get('existing_summary_tokens', 0)
                    # output_token_estimate = estimate_tokens(insights)
                    # logger.info(
                    #     (
                    #         f"[LLM] {contact_id} {eni_source_type}/{eni_source_subtype} "
                    #         f"output_token_estimate={output_token_estimate} vs existing_summary_tokens={existing_summary_tokens}"
                    #     )
                    # )

                    # accepted_duration = ai_duration
                    # accepted_output_tokens = output_token_estimate

                    # if existing_summary_tokens and output_token_estimate < existing_summary_tokens:
                    #     # Count token-loss event
                    #     result['token_loss_events'] += 1
                    #     logger.error(
                    #         (
                    #             f"[TOKEN-LOSS] Output tokens ({output_token_estimate}) < existing summary tokens ({existing_summary_tokens}). "
                    #             f"Retrying once for {contact_id} {eni_source_type}/{eni_source_subtype}"
                    #         )
                    #     )
                    #     # Retry once
                    #     start_time_retry = time.time()
                    #     insights_retry = self.ai_processor.generate_from_full_prompt(full_rendered_prompt)
                    #     ai_retry_duration = time.time() - start_time_retry
                    #     if self.enhanced_logger:
                    #         self.enhanced_logger.log_ai_call_end(
                    #             self.ai_processor.model_name if hasattr(self.ai_processor, 'model_name') else 'AI',
                    #             "structured_insight (retry)",
                    #             f"{eni_source_type}/{eni_source_subtype}",
                    #             bool(insights_retry),
                    #             ai_retry_duration,
                    #             len(insights_retry) if insights_retry else 0
                    #         )

                    #     if not insights_retry:
                    #         result['errors'].append(
                    #             f"Retry also failed for {contact_id} {eni_source_type}/{eni_source_subtype}; skipping upsert and processed-marking"
                    #         )
                    #         # Count skipped group and records
                    #         group_eni_ids = eni_data['eni_id'].tolist()
                    #         result['token_loss_groups_skipped'] += 1
                    #         result['token_loss_records_skipped'] += len(group_eni_ids)
                    #         continue

                    #     output_retry_tokens = estimate_tokens(insights_retry)
                    #     logger.info(
                    #         (
                    #             f"[LLM-RETRY] {contact_id} {eni_source_type}/{eni_source_subtype} output_token_estimate={output_retry_tokens} "
                    #             f"vs existing_summary_tokens={existing_summary_tokens}"
                    #         )
                    #     )
                    #     if output_retry_tokens < existing_summary_tokens:
                    #         logger.error(
                    #             (
                    #                 f"[TOKEN-LOSS] Retry output still smaller ({output_retry_tokens} < {existing_summary_tokens}). "
                    #                 f"Skipping this group without upsert or processed-marking"
                    #             )
                    #         )
                    #         # Count skipped group and records
                    #         group_eni_ids = eni_data['eni_id'].tolist()
                    #         result['token_loss_groups_skipped'] += 1
                    #         result['token_loss_records_skipped'] += len(group_eni_ids)
                    #         continue

                    #     insights = insights_retry
                    #     accepted_duration = ai_retry_duration
                    #     accepted_output_tokens = output_retry_tokens

                    # With versioned insights, we accept all LLM outputs without retry
                    accepted_duration = ai_duration
                    accepted_output_tokens = estimate_tokens(insights)

                    # Append trace for response
                    if llm_trace_enabled and trace_writer and trace_file_path:
                        if llm_trace_cfg.get("include_response", True):
                            trace_writer.append_section(
                                trace_file_path,
                                f"Response: {eni_source_type}/{eni_source_subtype}",
                                insights,
                            )

                    # Use a per-group ENI composite id
                    group_eni_ids = eni_data["eni_id"].tolist()
                    group_eni_id = f"COMBINED-{eni_source_type}-{eni_source_subtype}-{contact_id}-{len(group_eni_ids)}ENI"

                    if not dry_run:
                        # Write JSON for this group
                        json_file = self.json_writer.write_structured_insight(
                            contact_id=contact_id,
                            eni_id=group_eni_id,
                            content=insights,
                            additional_metadata={
                                "eni_source_type": eni_source_type,
                                "eni_source_subtype": eni_source_subtype,
                                "system_prompt_key": system_prompt_key,
                                "context_files": f"{eni_source_type}/{eni_source_subtype}",
                                "record_count": len(eni_data),
                                "total_eni_ids": len(group_eni_ids),
                            },
                        )
                        if json_file:
                            result["files_created"].append(json_file)
                            if self.enhanced_logger:
                                self.enhanced_logger.log_file_creation(
                                    json_file, "structured_insight"
                                )

                        # Save to Supabase per group
                        if self.supabase_processor:
                            try:
                                import json as _json
                                import re as _re
                                from data_processing.schema import StructuredInsightContent

                                structured_content = None

                                def _all_fields_empty(si: StructuredInsightContent) -> bool:
                                    return not any(
                                        [
                                            (si.personal or "").strip(),
                                            (si.business or "").strip(),
                                            (si.investing or "").strip(),
                                            (getattr(si, "three_i", "") or "").strip(),
                                            (si.deals or "").strip(),
                                            (si.introductions or "").strip(),
                                        ]
                                    )

                                def _parse_markdown_sections(
                                    md_text: str,
                                ) -> StructuredInsightContent:
                                    if not md_text:
                                        return StructuredInsightContent(
                                            personal="",
                                            business="",
                                            investing="",
                                            three_i="",
                                            deals="",
                                            introductions="",
                                        )

                                    def _extract(section: str) -> str:
                                        pattern = rf"^## {section}\n([\s\S]*?)(?=\n## |\Z)"
                                        m = _re.search(pattern, md_text, _re.MULTILINE)
                                        return m.group(1).strip() if m else ""

                                    return StructuredInsightContent(
                                        personal=_extract("Personal"),
                                        business=_extract("Business"),
                                        investing=_extract("Investing"),
                                        three_i=_extract("3i"),
                                        deals=_extract("Deals"),
                                        introductions=_extract("Introductions"),
                                    )

                                if insights:
                                    json_match = _re.search(
                                        r"```json\s*(.*?)\s*```", insights, _re.DOTALL
                                    )
                                    if json_match:
                                        try:
                                            parsed_json = _json.loads(json_match.group(1))
                                            if (
                                                isinstance(parsed_json, dict)
                                                and "existing_member_summary" in parsed_json
                                            ):
                                                structured_content = _parse_markdown_sections(
                                                    parsed_json.get("existing_member_summary") or ""
                                                )
                                            else:
                                                structured_content = StructuredInsightContent(
                                                    **parsed_json
                                                )
                                        except (_json.JSONDecodeError, Exception):
                                            structured_content = None
                                    else:
                                        try:
                                            parsed_json = _json.loads(insights)
                                            if (
                                                isinstance(parsed_json, dict)
                                                and "existing_member_summary" in parsed_json
                                            ):
                                                structured_content = _parse_markdown_sections(
                                                    parsed_json.get("existing_member_summary") or ""
                                                )
                                            else:
                                                structured_content = StructuredInsightContent(
                                                    **parsed_json
                                                )
                                        except (_json.JSONDecodeError, Exception):
                                            # Try generic fenced block without language
                                            generic_match = _re.search(
                                                r"```\s*(.*?)\s*```", insights, _re.DOTALL
                                            )
                                            if generic_match:
                                                try:
                                                    parsed_json = _json.loads(
                                                        generic_match.group(1)
                                                    )
                                                    if (
                                                        isinstance(parsed_json, dict)
                                                        and "existing_member_summary" in parsed_json
                                                    ):
                                                        structured_content = (
                                                            _parse_markdown_sections(
                                                                parsed_json.get(
                                                                    "existing_member_summary"
                                                                )
                                                                or ""
                                                            )
                                                        )
                                                    else:
                                                        structured_content = (
                                                            StructuredInsightContent(**parsed_json)
                                                        )
                                                except (_json.JSONDecodeError, Exception):
                                                    structured_content = None
                                            if not structured_content:
                                                # Final fallback: parse markdown sections from free text
                                                structured_content = _parse_markdown_sections(
                                                    insights
                                                )

                                if structured_content:
                                    # If JSON parsed but all fields empty, attempt markdown fallback once
                                    if _all_fields_empty(structured_content) and insights:
                                        md_fallback = _parse_markdown_sections(insights)
                                        if not _all_fields_empty(md_fallback):
                                            structured_content = md_fallback
                                    # Compute token metrics for this accepted iteration
                                    rendered_full_tokens = 0
                                    try:
                                        rendered_full_tokens = int(
                                            token_stats.get("rendered_full_tokens") or 0
                                        )
                                    except Exception:
                                        rendered_full_tokens = 0
                                    if rendered_full_tokens <= 0:
                                        rendered_full_tokens = estimate_tokens(full_rendered_prompt)
                                    est_input_tokens_delta = rendered_full_tokens or 0
                                    est_insights_tokens_current = (
                                        accepted_output_tokens or estimate_tokens(insights)
                                    )
                                    generation_time_seconds_delta = float(accepted_duration or 0.0)

                                    logger.info(
                                        f"[TOKENS] input+={est_input_tokens_delta} current_output={est_insights_tokens_current} gen_time+={generation_time_seconds_delta:.2f}"
                                    )

                                    # Accumulate per-contact summary
                                    contact_est_input_tokens += est_input_tokens_delta
                                    contact_est_insights_tokens_latest = est_insights_tokens_current
                                    contact_generation_time_seconds += generation_time_seconds_delta

                                    supabase_result, was_created = (
                                        self.supabase_processor.process_insight(
                                            contact_id=contact_id,
                                            # Use consolidated ENI id so all groups merge into a single record per contact
                                            eni_id=consolidated_eni_id,
                                            insight_content=structured_content,
                                            metadata={
                                                # Only append to arrays; do not set single-value type/subtype columns
                                                "eni_source_types": [eni_source_type],
                                                "eni_source_subtypes": [eni_source_subtype],
                                                "system_prompt_key": system_prompt_key,
                                                "context_files": f"{eni_source_type}/{eni_source_subtype}",
                                                "record_count": len(eni_data),
                                                "total_eni_ids": len(group_eni_ids),
                                            },
                                            est_input_tokens_delta=est_input_tokens_delta,
                                            est_insights_tokens_current=est_insights_tokens_current,
                                            generation_time_seconds_delta=generation_time_seconds_delta,
                                        )
                                    )
                                    if supabase_result:
                                        action = "created" if was_created else "updated"
                                        logger.info(
                                            f"Successfully {action} structured insight in Supabase for contact {contact_id} ({eni_source_type}/{eni_source_subtype})"
                                        )
                                        result["supabase_record_id"] = str(supabase_result.id)
                                        result["supabase_action"] = action
                                else:
                                    logger.warning(
                                        f"Failed to parse insight content for Supabase storage: {contact_id} ({eni_source_type}/{eni_source_subtype})"
                                    )
                            except Exception as e:
                                logger.error(
                                    f"Error saving to Supabase for contact {contact_id} ({eni_source_type}/{eni_source_subtype}): {e}"
                                )
                                result["errors"].append(f"Supabase save error: {str(e)}")

                        # Sync to Airtable per group (removed - now Supabase-driven after all groups)
                        # (No-op here to prevent multiple writes per contact)

                        # Mark group ENIs as processed
                        records_to_mark = [
                            {
                                "eni_id": eni_id,
                                "contact_id": contact_id,
                                "processing_status": "completed",
                                "processor_version": "1.0.0",
                                "metadata": {"batch_id": group_eni_id},
                            }
                            for eni_id in group_eni_ids
                        ]
                        successful_count, failed_count = (
                            self.bigquery_connector.batch_mark_processed(records_to_mark)
                        )
                        if successful_count > 0:
                            logger.info(
                                f"Marked {successful_count} ENI IDs as processed in BigQuery for contact {contact_id} ({eni_source_type}/{eni_source_subtype})"
                            )
                        if failed_count > 0:
                            logger.warning(
                                f"Failed to mark {failed_count} ENI IDs as processed in BigQuery for contact {contact_id} ({eni_source_type}/{eni_source_subtype})"
                            )
                        result["processed_eni_ids"].extend(group_eni_ids)

                except Exception as e:
                    error_msg = f"Error processing group for {contact_id}, {eni_source_type}/{eni_source_subtype}: {str(e)}"
                    result["errors"].append(error_msg)
                    logger.error(error_msg)
                    continue

            logger.info(
                f"Per-group processing complete for contact {contact_id}. Total groups with data: {1 if total_loaded>0 else 0}, total records: {total_loaded}"
            )

            # Token-loss summary for this contact
            if result["token_loss_events"] or result["token_loss_groups_skipped"]:
                logger.info(
                    (
                        f"[TOKEN-LOSS] Summary for {contact_id}: "
                        f"events={result['token_loss_events']} | "
                        f"groups_skipped={result['token_loss_groups_skipped']} | "
                        f"records_skipped={result['token_loss_records_skipped']}"
                    )
                )

            # Token metrics summary for this contact
            logger.info(
                f"[TOKENS] Summary for {contact_id}: est_input_tokens={contact_est_input_tokens} "
                f"est_insights_tokens={contact_est_insights_tokens_latest} generation_time_seconds={contact_generation_time_seconds:.2f}"
            )

            # Perform single Supabase-driven Airtable sync per contact (post-processing)
            if not dry_run and self.supabase_airtable_sync and self.structured_airtable_writer:
                try:
                    sync_res = self.supabase_airtable_sync.sync_contact_to_airtable(
                        contact_id, force_update=True
                    )
                    result["airtable_final_sync"] = {
                        "success": sync_res.success,
                        "action": sync_res.action,
                        "airtable_record_id": sync_res.airtable_record_id,
                        "error_message": sync_res.error_message,
                    }
                    # Keep count compatibility with existing summaries
                    result["airtable_records"].append(result["airtable_final_sync"])
                    if self.enhanced_logger:
                        self.enhanced_logger.log_airtable_sync(
                            contact_id,
                            sync_res.success,
                            f"supabase_post_process({sync_res.action})",
                        )
                except Exception as e:
                    err = f"Post-processing Airtable sync failed for {contact_id}: {e}"
                    result["errors"].append(err)
                    logger.error(err)

            result["success"] = len(result["errors"]) == 0

            # Return per-contact token metrics for optional CLI printing
            result["est_input_tokens"] = contact_est_input_tokens
            result["est_insights_tokens"] = contact_est_insights_tokens_latest
            result["generation_time_seconds"] = contact_generation_time_seconds

            return result

        except Exception as e:
            result["errors"].append(f"Unexpected error processing contact {contact_id}: {str(e)}")
            logger.error(f"Error processing contact {contact_id}: {str(e)}")
            return result

    def _process_combined_structured_insight(
        self, contact_id: str, contact_data: pd.DataFrame, system_prompt_key: str, dry_run: bool
    ) -> Dict[str, Any]:
        """
        Process all ENI groups for a contact into a single comprehensive structured insight.

        Args:
            contact_id: The contact ID to process
            contact_data: All filtered contact data for this contact
            system_prompt_key: System prompt key (should be "structured_insight")
            dry_run: If True, don't save results or update logs

        Returns:
            Dict[str, Any]: Processing results
        """
        result = {
            "processed_eni_ids": [],
            "errors": [],
            "files_created": [],
            "airtable_records": [],
        }

        try:
            # Enhanced logging for combined processing start
            if self.enhanced_logger:
                self.enhanced_logger.log_contact_processing_start(
                    contact_id, len(contact_data), len(contact_data)
                )

            # Load existing structured insight from Supabase if available
            existing_insight = None
            if self.supabase_client:
                try:
                    existing_insight = self.supabase_client.get_latest_insight_by_contact_id(
                        contact_id, generator="structured_insight"
                    )
                    if existing_insight:
                        logger.info(f"Found existing structured insight for contact {contact_id}")
                    else:
                        logger.info(
                            f"No existing structured insight found for contact {contact_id}"
                        )
                except Exception as e:
                    logger.warning(f"Failed to load existing insight from Supabase: {e}")

            # Initialize member summary structure (use existing or create new)
            if existing_insight and hasattr(existing_insight, "insights"):
                # Start with existing insights content - access from JSON structure
                insights_content = existing_insight.insights
                if isinstance(insights_content, dict):
                    member_summary = {
                        "personal": insights_content.get("personal", ""),
                        "business": insights_content.get("business", ""),
                        "investing": insights_content.get("investing", ""),
                        "3i": insights_content.get("3i") or insights_content.get("three_i", ""),
                        "deals": insights_content.get(
                            "deals",
                            "This Member **Has Experience** and Is Comfortable Diligencing These Asset Classes & Sectors\n\nThis Member **Is Interested In Exploring** These Asset Classes, Sectors, and Strategies\n\nThis Member **Wants to Avoid** These Asset Classes, Sectors, and Strategies\n",
                        ),
                        "introductions": insights_content.get(
                            "introductions", "**Looking to meet:**\n\n**Avoid introductions to:**\n"
                        ),
                    }
                else:
                    # If insights is a StructuredInsightContent object
                    member_summary = {
                        "personal": getattr(insights_content, "personal", "") or "",
                        "business": getattr(insights_content, "business", "") or "",
                        "investing": getattr(insights_content, "investing", "") or "",
                        "3i": getattr(insights_content, "three_i", "") or "",
                        "deals": getattr(insights_content, "deals", "")
                        or "This Member **Has Experience** and Is Comfortable Diligencing These Asset Classes & Sectors\n\nThis Member **Is Interested In Exploring** These Asset Classes, Sectors, and Strategies\n\nThis Member **Wants to Avoid** These Asset Classes, Sectors, and Strategies\n",
                        "introductions": getattr(insights_content, "introductions", "")
                        or "**Looking to meet:**\n\n**Avoid introductions to:**\n",
                    }
                logger.info(f"Loaded existing insights as baseline for {contact_id}")
            else:
                # Initialize empty member summary structure
                member_summary = {
                    "personal": "",
                    "business": "",
                    "investing": "",
                    "3i": "",
                    "deals": "This Member **Has Experience** and Is Comfortable Diligencing These Asset Classes & Sectors\n\nThis Member **Is Interested In Exploring** These Asset Classes, Sectors, and Strategies\n\nThis Member **Wants to Avoid** These Asset Classes, Sectors, and Strategies\n",
                    "introductions": "**Looking to meet:**\n\n**Avoid introductions to:**\n",
                }

            # Group data by ENI source type and subtype
            grouped_data = contact_data.groupby(["eni_source_type", "eni_source_subtype"])

            # Build per-group context variables with token budgeting
            per_group_blocks = []
            total_eni_ids = []

            for (eni_source_type, eni_source_subtype), group_data in grouped_data:
                try:
                    # Build context variables for this group
                    if not self.context_manager:
                        raise RuntimeError("ContextManager not initialized")

                    ctx_vars = self.context_manager.build_context_variables(
                        contact_id=contact_id,
                        eni_source_type=eni_source_type,
                        eni_source_subtype=eni_source_subtype,
                        eni_group_df=group_data,
                        system_prompt_key=system_prompt_key,
                    )

                    # Render a compact per-group block using the four variables
                    group_header = f"=== ENI GROUP: {eni_source_type}/{eni_source_subtype} ({len(group_data)} records) ===\n"
                    type_block = (
                        (
                            f"## ENI Source Type Context ({eni_source_type})\n"
                            f"{ctx_vars['eni_source_type_context']}\n\n"
                        )
                        if ctx_vars.get("eni_source_type_context")
                        else ""
                    )
                    subtype_block = (
                        (
                            f"## ENI Source Subtype Context ({eni_source_subtype})\n"
                            f"{ctx_vars['eni_source_subtype_context']}\n\n"
                        )
                        if ctx_vars.get("eni_source_subtype_context")
                        else ""
                    )
                    new_data_block = (
                        f"## New Data To Process ({ctx_vars.get('rows_used', 0)} rows)\n"
                        f"{ctx_vars['new_data_to_process']}\n"
                    )

                    per_group_blocks.append(
                        group_header + type_block + subtype_block + new_data_block
                    )

                    # Collect ENI IDs
                    eni_ids_in_group = group_data["eni_id"].tolist()
                    total_eni_ids.extend(eni_ids_in_group)

                except Exception as e:
                    error_msg = f"Error collecting context for {eni_source_type}/{eni_source_subtype}: {str(e)}"
                    result["errors"].append(error_msg)
                    logger.error(error_msg)
                    continue

            # Combine all group blocks; include current structured insight once at the top
            current_structured_insight = ""
            if self.context_manager:
                current_structured_insight = self.context_manager.get_current_structured_insight(
                    contact_id, system_prompt_key
                )
            combined_groups_context = "\n\n".join(per_group_blocks)

            # Build final prompt for AI processing
            final_prompt_context = f"""
EXISTING MEMBER SUMMARY (to be updated):
{current_structured_insight}

CONTEXT PACKAGES BY ENI GROUP:
{combined_groups_context}
"""

            # Enhanced logging for AI call
            if self.enhanced_logger:
                self.enhanced_logger.log_ai_call_start(
                    (
                        self.ai_processor.model_name
                        if hasattr(self.ai_processor, "model_name")
                        else "AI"
                    ),
                    "combined_structured_insight",
                    "all_eni_groups",
                    len(total_eni_ids),
                )

            # Process with AI
            start_time = time.time()
            insights = self.ai_processor.process_single_contact(
                contact_data=contact_data,
                system_prompt_key=system_prompt_key,
                context_content=final_prompt_context,
                config_loader=self.config_loader,
            )
            ai_duration = time.time() - start_time

            # Enhanced logging for AI call end
            if self.enhanced_logger:
                self.enhanced_logger.log_ai_call_end(
                    (
                        self.ai_processor.model_name
                        if hasattr(self.ai_processor, "model_name")
                        else "AI"
                    ),
                    "combined_structured_insight",
                    "all_eni_groups",
                    bool(insights),
                    ai_duration,
                    len(insights) if insights else 0,
                )

            if not insights:
                result["errors"].append(f"Failed to generate insights for contact {contact_id}")
                return result

            # Generate single combined ENI ID for the comprehensive insight
            combined_eni_id = f"COMBINED-{contact_id}-{len(total_eni_ids)}ENI"

            if not dry_run:
                # Write to JSON file (structured insights always use JSON)
                json_file = self.json_writer.write_structured_insight(
                    contact_id=contact_id,
                    eni_id=combined_eni_id,
                    content=insights,
                    additional_metadata={
                        "eni_source_types": list(set(contact_data["eni_source_type"].tolist())),
                        "eni_source_subtypes": list(
                            set(contact_data["eni_source_subtype"].tolist())
                        ),
                        "system_prompt_key": system_prompt_key,
                        "context_files": "combined_all_eni_groups",
                        "record_count": len(contact_data),
                        "total_eni_ids": len(total_eni_ids),
                    },
                )

                if json_file:
                    result["files_created"].append(json_file)
                    if self.enhanced_logger:
                        self.enhanced_logger.log_file_creation(json_file, "structured_insight")

                # Save to Supabase if available
                if self.supabase_processor:
                    try:
                        # Import required classes
                        import json
                        import re
                        from data_processing.schema import StructuredInsightContent

                        # Parse the insights to extract structured content
                        structured_content = None
                        if insights:
                            # Try to extract JSON from markdown code blocks
                            json_match = re.search(r"```json\s*(.*?)\s*```", insights, re.DOTALL)
                            if json_match:
                                try:
                                    parsed_json = json.loads(json_match.group(1))
                                    structured_content = StructuredInsightContent(**parsed_json)
                                except (json.JSONDecodeError, Exception):
                                    # If parsing fails, create content with raw_content
                                    structured_content = StructuredInsightContent(
                                        personal="",
                                        business="",
                                        investing="",
                                        three_i="",
                                        deals="",
                                        introductions="",
                                    )
                            else:
                                # Try to parse the whole thing as JSON
                                try:
                                    parsed_json = json.loads(insights)
                                    structured_content = StructuredInsightContent(**parsed_json)
                                except (json.JSONDecodeError, Exception):
                                    # Create content with raw insights
                                    structured_content = StructuredInsightContent(
                                        personal="",
                                        business="",
                                        investing="",
                                        three_i="",
                                        deals="",
                                        introductions="",
                                    )

                        if structured_content:
                            # Process the insights with Supabase (handles upsert logic)
                            supabase_result, was_created = self.supabase_processor.process_insight(
                                contact_id=contact_id,
                                eni_id=combined_eni_id,
                                insight_content=structured_content,
                                metadata={
                                    "eni_source_types": list(
                                        set(contact_data["eni_source_type"].tolist())
                                    ),
                                    "eni_source_subtypes": list(
                                        set(contact_data["eni_source_subtype"].tolist())
                                    ),
                                    "system_prompt_key": system_prompt_key,
                                    "context_files": "combined_all_eni_groups",
                                    "record_count": len(contact_data),
                                    "total_eni_ids": len(total_eni_ids),
                                },
                            )

                            if supabase_result:
                                action = "created" if was_created else "updated"
                                logger.info(
                                    f"Successfully {action} structured insight in Supabase for contact {contact_id}"
                                )
                                result["supabase_record_id"] = str(supabase_result.id)
                                result["supabase_action"] = action
                            else:
                                logger.warning(
                                    f"Failed to save to Supabase for contact {contact_id}"
                                )
                        else:
                            logger.warning(
                                f"Failed to parse insight content for Supabase storage: {contact_id}"
                            )

                    except Exception as e:
                        logger.error(f"Error saving to Supabase for contact {contact_id}: {e}")
                        result["errors"].append(f"Supabase save error: {str(e)}")

                # Sync to structured Airtable if configured
                if self.structured_airtable_writer:
                    try:
                        # Parse the insights to extract JSON (handle markdown code blocks)
                        structured_json = None
                        if insights:
                            import json
                            import re

                            # Try to extract JSON from markdown code blocks
                            json_match = re.search(r"```json\s*(.*?)\s*```", insights, re.DOTALL)
                            if json_match:
                                try:
                                    structured_json = json.loads(json_match.group(1))
                                except json.JSONDecodeError:
                                    # If that fails, try to parse the whole thing as JSON
                                    try:
                                        structured_json = json.loads(insights)
                                    except json.JSONDecodeError:
                                        structured_json = {"raw_content": insights}
                            else:
                                # Try to parse the whole thing as JSON
                                try:
                                    structured_json = json.loads(insights)
                                except json.JSONDecodeError:
                                    structured_json = {"raw_content": insights}

                        if structured_json:
                            airtable_result = (
                                self.structured_airtable_writer.create_note_submission_record(
                                    contact_id=contact_id, structured_json=structured_json
                                )
                            )
                            if airtable_result:
                                result["airtable_records"].append(airtable_result)
                                if self.enhanced_logger:
                                    self.enhanced_logger.log_airtable_sync(
                                        contact_id, True, "structured_insight"
                                    )
                        else:
                            result["errors"].append(
                                "Failed to parse JSON from AI insights for Airtable sync"
                            )
                    except Exception as e:
                        result["errors"].append(f"Error in structured Airtable sync: {str(e)}")
                        if self.enhanced_logger:
                            self.enhanced_logger.log_airtable_sync(
                                contact_id, False, "structured_insight"
                            )

                # Mark all ENI IDs as processed in BigQuery
                records_to_mark = [
                    {
                        "eni_id": eni_id,
                        "contact_id": contact_id,
                        "processing_status": "completed",
                        "processor_version": "1.0.0",
                        "metadata": {"batch_id": combined_eni_id},
                    }
                    for eni_id in total_eni_ids
                ]

                successful_count, failed_count = self.bigquery_connector.batch_mark_processed(
                    records_to_mark
                )
                if successful_count > 0:
                    logger.info(
                        f"Marked {successful_count} ENI IDs as processed in BigQuery for contact {contact_id}"
                    )
                if failed_count > 0:
                    logger.warning(
                        f"Failed to mark {failed_count} ENI IDs as processed in BigQuery for contact {contact_id}"
                    )

                result["processed_eni_ids"].extend(total_eni_ids)

            logger.info(
                f"Successfully processed combined structured insight for contact {contact_id} with {len(total_eni_ids)} ENI IDs"
            )

            # Enhanced logging for contact processing end
            if self.enhanced_logger:
                final_result = {
                    "success": len(result["errors"]) == 0,
                    "processed_eni_ids": result["processed_eni_ids"],
                    "files_created": result["files_created"],
                    "airtable_records": result["airtable_records"],
                    "errors": result["errors"],
                }
                self.enhanced_logger.log_contact_processing_end(contact_id, final_result)

            return result

        except Exception as e:
            error_msg = f"Error in combined structured insight processing: {str(e)}"
            result["errors"].append(error_msg)
            logger.error(error_msg)
            if self.enhanced_logger:
                self.enhanced_logger.log_contact_processing_end(
                    contact_id, {"success": False, "errors": [error_msg]}
                )
            return result

    def process_multiple_contacts(
        self,
        contact_ids: Optional[List[str]],
        system_prompt_key: str = "structured_insight",
        dry_run: bool = False,
        max_contacts: Optional[int] = None,
        contact_ids_sql: Optional[str] = None,
        selection_batch_size: Optional[int] = None,
        job_start_time: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process multiple contacts.

        Args:
            contact_ids: List of specific contact IDs to process (if None, processes all)
            system_prompt_key: System prompt key to use
            dry_run: If True, don't save results or update logs
            max_contacts: Maximum number of contacts to process
            contact_ids_sql: SQL query text for selecting prioritized contact_ids
            selection_batch_size: SQL selection batch size per wave
            job_start_time: Job start time in ISO format

        Returns:
            Dict[str, Any]: Processing summary
        """
        summary = {
            "total_contacts": 0,
            "successful_contacts": 0,
            "failed_contacts": 0,
            "total_processed_eni_ids": 0,
            "total_files_created": 0,
            "total_airtable_records": 0,
            # Aggregated token-loss stats
            "token_loss_events": 0,
            "token_loss_groups_skipped": 0,
            "token_loss_records_skipped": 0,
            "contact_results": {},
            "errors": [],
            "start_time": datetime.now().isoformat(),
            "end_time": None,
        }

        try:
            # Ensure BigQuery connection is established
            if not self.bigquery_connector.connect():
                summary["errors"].append("Failed to connect to BigQuery")
                summary["end_time"] = datetime.now().isoformat()
                return summary

            # Determine parallel config
            parallel_cfg = self.config_loader.get_parallel_config()
            enable_parallel = bool(parallel_cfg.get("enable"))
            max_workers = int(parallel_cfg.get("max_concurrent_contacts", 1))
            sel_cfg = parallel_cfg.get("selection") or {}
            default_batch_size = int(sel_cfg.get("batch_size", 100))
            batch_size = int(selection_batch_size or default_batch_size)
            claims_cfg = parallel_cfg.get("claims") or {}
            claimer = create_local_claimer(enabled=bool(claims_cfg.get("enabled", True)))
            ttl_seconds = int(claims_cfg.get("ttl_seconds", 900))

            # Capture job start time (UTC ISO) once
            run_start = job_start_time or datetime.utcnow().isoformat() + "Z"
            run_id = str(uuid4())
            # Selection cutoff: one week ago to avoid reprocessing recent runs
            selection_cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat() + "Z"
            logger.info(
                f"Parallel run config: enable={enable_parallel} workers={max_workers} batch_size={batch_size} job_start_time={run_start}"
            )

            # Initialize run summary writer and run directory (only for parallel mode)
            rsw: Optional[RunSummaryWriter] = None
            if enable_parallel and max_workers > 1:
                rsw = RunSummaryWriter(run_id=run_id, base_dir="var/logs/runs")
                self.run_summary_writer = rsw

            # If contact_ids provided explicitly, process those; else use SQL selection or fallback to unique IDs
            explicit_ids = contact_ids is not None
            if contact_ids is None:
                if contact_ids_sql:
                    variables = {
                        "system_prompt": system_prompt_key,
                        "generator": "structured_insight",
                        # Use one-week-ago cutoff to reduce duplicate reprocessing
                        "job_start_time": selection_cutoff,
                    }
                    contact_ids = self.bigquery_connector.get_contact_ids_from_sql(
                        sql_text=contact_ids_sql,
                        variables=variables,
                        offset=0,
                        limit=max_contacts,
                    )
                else:
                    # Use prioritized selection: never-processed first, then oldest processed before cutoff
                    contact_ids = self.bigquery_connector.get_prioritized_contact_ids(
                        system_prompt_key=system_prompt_key,
                        generator="structured_insight",
                        cutoff_time_iso=selection_cutoff,
                        limit=max_contacts,
                        offset=0,
                    )

            if max_contacts:
                contact_ids = contact_ids[:max_contacts]

            summary["total_contacts"] = len(contact_ids)
            logger.info(
                f"Starting processing of {len(contact_ids)} contacts (parallel={enable_parallel})"
            )

            # Selection mode reporting
            selection_mode = (
                "sql"
                if contact_ids_sql
                else ("explicit_list" if explicit_ids else "fallback_unique")
            )

            # Emit run-start event and console banner
            if rsw:
                rsw.append_event(
                    {
                        "event": "run_started",
                        "run_id": run_id,
                        "job_start_time": run_start,
                        "selection_cutoff_time": selection_cutoff,
                        "parallel": {
                            "enabled": enable_parallel,
                            "max_workers": max_workers,
                            "batch_size": batch_size,
                            "claims_ttl_seconds": ttl_seconds,
                        },
                        "selection_mode": selection_mode,
                        "total_contacts_selected": len(contact_ids),
                    }
                )
                logger.info(
                    f"RUN {run_id} | workers={max_workers} batch_size={batch_size} selection={selection_mode} start={run_start}"
                )

            # Dispatcher helpers
            in_flight = set()
            seen = set()
            # Additional counters
            total_scheduled = 0
            total_started = 0
            total_completed_success = 0
            total_skipped_claim = 0
            total_failed = 0

            def worker(cid: str) -> Tuple[str, Dict[str, Any]]:
                key = f"contact/{cid}"
                acquired = True
                if claimer:
                    # Log claim attempt
                    if rsw:
                        rsw.append_event({"event": "claim_attempt", "contact_id": cid, "key": key})
                    acquired = claimer.acquire(key, ttl_seconds, run_id)
                    if rsw:
                        rsw.append_event(
                            {
                                "event": "claim_acquired" if acquired else "claim_skipped",
                                "contact_id": cid,
                                "key": key,
                            }
                        )
                    if not acquired:
                        # Skipped due to claim
                        return cid, {
                            "success": True,
                            "status": "skipped_claim",
                            "processed_eni_ids": [],
                            "files_created": [],
                            "airtable_records": [],
                            "errors": [f"skipped_due_to_claim:{cid}"],
                        }
                try:
                    # Emit start event
                    if rsw:
                        rsw.append_event({"event": "contact_started", "contact_id": cid})
                    # Track started count locally by emitting via event only; final totals will be derived
                    res = self.process_contact(
                        contact_id=cid, system_prompt_key=system_prompt_key, dry_run=dry_run
                    )
                    return cid, res
                finally:
                    if claimer and acquired:
                        try:
                            claimer.release(key)
                            if rsw:
                                rsw.append_event(
                                    {"event": "claim_released", "contact_id": cid, "key": key}
                                )
                        except Exception:
                            pass

            def schedule_batch(executor: ThreadPoolExecutor, batch_ids: List[str]):
                futures = []
                for cid in batch_ids:
                    if cid in seen:
                        continue
                    seen.add(cid)
                    in_flight.add(cid)
                    if rsw:
                        rsw.append_event({"event": "contact_scheduled", "contact_id": cid})
                    futures.append(executor.submit(worker, cid))
                return futures

            if enable_parallel and max_workers > 1 and (contact_ids_sql or explicit_ids):
                # Re-query loop for SQL-driven selection or explicit list batched
                all_futures = set()
                idx = 0
                with ThreadPoolExecutor(max_workers=max_workers) as ex:
                    sql_cursor = 0
                    while True:
                        # Drain completed
                        done = [f for f in list(all_futures) if f.done()]
                        for f in done:
                            all_futures.discard(f)
                            cid, result = f.result()
                            in_flight.discard(cid)
                            summary["contact_results"][cid] = result
                            # Persist per-contact summary artifact
                            if rsw:
                                try:
                                    contact_payload = dict(result)
                                    contact_payload["status"] = (
                                        "success"
                                        if result.get("success")
                                        else (
                                            "skipped_claim"
                                            if any(
                                                "skipped_due_to_claim" in e
                                                for e in result.get("errors", [])
                                            )
                                            else "failed"
                                        )
                                    )
                                    contact_payload["start_ts"] = summary["start_time"]
                                    contact_payload["end_ts"] = datetime.now().isoformat()
                                    rsw.write_contact_summary(cid, contact_payload)
                                    rsw.append_event(
                                        {
                                            "event": "contact_completed",
                                            "contact_id": cid,
                                            "status": contact_payload["status"],
                                        }
                                    )
                                except Exception:
                                    pass
                            if result.get("errors") and any(
                                "skipped" in e for e in result["errors"]
                            ):
                                total_skipped_claim += 1
                                continue
                            if result.get("success"):
                                summary["successful_contacts"] += 1
                                total_completed_success += 1
                                summary["total_processed_eni_ids"] += len(
                                    result.get("processed_eni_ids", [])
                                )
                                summary["total_files_created"] += len(
                                    result.get("files_created", [])
                                )
                                summary["total_airtable_records"] += len(
                                    result.get("airtable_records", [])
                                )
                                summary["token_loss_events"] += result.get("token_loss_events", 0)
                                summary["token_loss_groups_skipped"] += result.get(
                                    "token_loss_groups_skipped", 0
                                )
                                summary["token_loss_records_skipped"] += result.get(
                                    "token_loss_records_skipped", 0
                                )
                            else:
                                summary["failed_contacts"] += 1
                                total_failed += 1
                                summary["errors"].extend(result.get("errors", []))

                        capacity = max_workers - len(in_flight)
                        if capacity > 0:
                            # Respect overall max_contacts cap if provided
                            remaining_allowed = None
                            if max_contacts is not None:
                                remaining_allowed = max(0, int(max_contacts) - len(seen))
                                if remaining_allowed == 0 and not all_futures and not in_flight:
                                    break
                            # Decide source for next batch
                            if contact_ids_sql:
                                variables = {
                                    "system_prompt": system_prompt_key,
                                    "generator": "structured_insight",
                                    # Continue using the same cutoff within the run
                                    "job_start_time": selection_cutoff,
                                }
                                # Skip anything we've already scheduled (seen)
                                offset = len(seen)
                                fetch_limit = min(batch_size, capacity)
                                if remaining_allowed is not None:
                                    fetch_limit = min(fetch_limit, remaining_allowed)
                                next_ids = self.bigquery_connector.get_contact_ids_from_sql(
                                    sql_text=contact_ids_sql,
                                    variables=variables,
                                    offset=offset,
                                    limit=fetch_limit,
                                )
                            else:
                                # Prioritized list paging: fetch next chunk using offset
                                next_ids = self.bigquery_connector.get_prioritized_contact_ids(
                                    system_prompt_key=system_prompt_key,
                                    generator="structured_insight",
                                    cutoff_time_iso=selection_cutoff,
                                    limit=min(
                                        batch_size,
                                        (
                                            capacity
                                            if remaining_allowed is None
                                            else min(capacity, remaining_allowed)
                                        ),
                                    ),
                                    offset=len(seen),
                                )

                            if next_ids:
                                logger.info(
                                    f"Scheduling {len(next_ids)} contacts (in_flight={len(in_flight)}, capacity={capacity}, offset={len(seen)}, fetch_limit={min(batch_size, capacity)})"
                                )
                                if rsw:
                                    rsw.append_event(
                                        {
                                            "event": "schedule_wave",
                                            "in_flight": len(in_flight),
                                            "capacity": capacity,
                                            "offset": len(seen),
                                            "fetch_limit": min(batch_size, capacity),
                                            "scheduled_count": len(next_ids),
                                        }
                                    )
                                batch_futs = schedule_batch(ex, next_ids[:capacity])
                                for bf in batch_futs:
                                    all_futures.add(bf)
                                total_scheduled += len(next_ids[:capacity])
                            else:
                                if not all_futures and not in_flight:
                                    break
                        # Brief yield to avoid busy loop
                        time.sleep(0.1)
                    # Final drain
                    for f in as_completed(list(all_futures)):
                        cid, result = f.result()
                        in_flight.discard(cid)
                        summary["contact_results"][cid] = result
                        if rsw:
                            try:
                                contact_payload = dict(result)
                                contact_payload["status"] = (
                                    "success"
                                    if result.get("success")
                                    else (
                                        "skipped_claim"
                                        if any(
                                            "skipped_due_to_claim" in e
                                            for e in result.get("errors", [])
                                        )
                                        else "failed"
                                    )
                                )
                                contact_payload["start_ts"] = summary["start_time"]
                                contact_payload["end_ts"] = datetime.now().isoformat()
                                rsw.write_contact_summary(cid, contact_payload)
                                rsw.append_event(
                                    {
                                        "event": "contact_completed",
                                        "contact_id": cid,
                                        "status": contact_payload["status"],
                                    }
                                )
                            except Exception:
                                pass
                        if result.get("errors") and any("skipped" in e for e in result["errors"]):
                            total_skipped_claim += 1
                            continue
                        if result.get("success"):
                            summary["successful_contacts"] += 1
                            total_completed_success += 1
                            summary["total_processed_eni_ids"] += len(
                                result.get("processed_eni_ids", [])
                            )
                            summary["total_files_created"] += len(result.get("files_created", []))
                            summary["total_airtable_records"] += len(
                                result.get("airtable_records", [])
                            )
                            summary["token_loss_events"] += result.get("token_loss_events", 0)
                            summary["token_loss_groups_skipped"] += result.get(
                                "token_loss_groups_skipped", 0
                            )
                            summary["token_loss_records_skipped"] += result.get(
                                "token_loss_records_skipped", 0
                            )
                        else:
                            summary["failed_contacts"] += 1
                            total_failed += 1
                            summary["errors"].extend(result.get("errors", []))
            else:
                # Sequential fallback over provided IDs
                for i, contact_id in enumerate(contact_ids, 1):
                    try:
                        logger.info(f"Processing contact {i}/{len(contact_ids)}: {contact_id}")
                        result = self.process_contact(
                            contact_id=contact_id,
                            system_prompt_key=system_prompt_key,
                            dry_run=dry_run,
                        )
                        summary["contact_results"][contact_id] = result
                        if result["success"]:
                            summary["successful_contacts"] += 1
                            summary["total_processed_eni_ids"] += len(result["processed_eni_ids"])
                            summary["total_files_created"] += len(result["files_created"])
                            summary["total_airtable_records"] += len(result["airtable_records"])
                            summary["token_loss_events"] += result.get("token_loss_events", 0)
                            summary["token_loss_groups_skipped"] += result.get(
                                "token_loss_groups_skipped", 0
                            )
                            summary["token_loss_records_skipped"] += result.get(
                                "token_loss_records_skipped", 0
                            )
                        else:
                            summary["failed_contacts"] += 1
                            summary["errors"].extend(result["errors"])
                        if i % 10 == 0 or i == len(contact_ids):
                            logger.info(f"Progress: {i}/{len(contact_ids)} contacts processed")
                    except Exception as e:
                        error_msg = f"Unexpected error processing contact {contact_id}: {str(e)}"
                        summary["errors"].append(error_msg)
                        summary["failed_contacts"] += 1
                        logger.error(error_msg)

            summary["end_time"] = datetime.now().isoformat()

            # Generate final report
            logger.info(
                f"""
Processing Complete:
- Total Contacts: {summary['total_contacts']}
- Successful: {summary['successful_contacts']}
- Failed: {summary['failed_contacts']}
- Total ENI IDs Processed: {summary['total_processed_eni_ids']}
- Files Created: {summary['total_files_created']}
- Airtable Records: {summary['total_airtable_records']}
- Errors: {len(summary['errors'])}
- Token-Loss Events: {summary['token_loss_events']}
- Token-Loss Groups Skipped: {summary['token_loss_groups_skipped']}
- Token-Loss Records Skipped: {summary['token_loss_records_skipped']}
"""
            )

            # Write final structured summary artifacts (parallel mode only)
            if rsw:
                final_summary = {
                    "run_id": run_id,
                    "job_start_time": run_start,
                    "selection_mode": selection_mode,
                    "parallel": {
                        "enabled": enable_parallel,
                        "max_workers": max_workers,
                        "batch_size": batch_size,
                        "claims_ttl_seconds": ttl_seconds,
                    },
                    "start_time": summary["start_time"],
                    "end_time": summary["end_time"],
                    "totals": {
                        "total_contacts_selected": summary["total_contacts"],
                        "total_scheduled": total_scheduled,
                        "total_started": len(summary["contact_results"]),
                        "total_completed_success": total_completed_success,
                        "total_skipped_claim": total_skipped_claim,
                        "total_failed": total_failed,
                        "total_eni_ids_processed": summary["total_processed_eni_ids"],
                        "total_ai_calls": None,
                    },
                    "per_contact": [
                        {
                            "contact_id": cid,
                            "status": (
                                "success"
                                if res.get("success")
                                else (
                                    "skipped_claim"
                                    if any(
                                        "skipped_due_to_claim" in e for e in res.get("errors", [])
                                    )
                                    else "failed"
                                )
                            ),
                            "groups_processed": None,
                            "eni_ids_processed": len(res.get("processed_eni_ids", [])),
                            "files_created": len(res.get("files_created", [])),
                            "airtable_records": len(res.get("airtable_records", [])),
                            "supabase": {
                                "action": res.get("supabase_action"),
                                "record_id": res.get("supabase_record_id"),
                            },
                            "airtable": res.get("airtable_final_sync"),
                            "tokens": {
                                "input_total": res.get("est_input_tokens"),
                                "output_latest": res.get("est_insights_tokens"),
                                "generation_time_seconds_total": res.get("generation_time_seconds"),
                            },
                            "errors": res.get("errors", []),
                        }
                        for cid, res in summary["contact_results"].items()
                    ],
                    "errors": summary["errors"],
                }
                rsw.write_final_summary(final_summary)

            return summary

        except Exception as e:
            summary["errors"].append(f"Unexpected error in batch processing: {str(e)}")
            summary["end_time"] = datetime.now().isoformat()
            logger.error(f"Error in batch processing: {str(e)}")
            return summary

    def get_processing_statistics(self) -> Dict[str, Any]:
        """
        Get processing statistics and system status.

        Returns:
            Dict[str, Any]: Statistics and status information
        """
        try:
            stats = {
                "log_statistics": self.log_manager.get_processing_stats(),
                "output_files": len(self.markdown_writer.list_summary_files()),
                "available_eni_types": self.context_manager.get_available_eni_types(),
                "available_prompts": list(self.context_manager.get_all_system_prompts().keys()),
                "system_status": self.validate_setup(),
            }

            # Add BigQuery statistics if available
            if self.bigquery_connector and self.bigquery_connector.connect():
                try:
                    eni_types_df = self.bigquery_connector.get_eni_source_types_and_subtypes()
                    stats["bigquery_eni_types"] = len(eni_types_df)
                    stats["total_unique_contacts"] = len(
                        self.bigquery_connector.get_unique_contact_ids()
                    )
                except Exception as e:
                    stats["bigquery_error"] = str(e)

            return stats

        except Exception as e:
            logger.error(f"Error getting processing statistics: {str(e)}")
            return {"error": str(e)}

    def clear_processed_logs(self, contact_id: Optional[str] = None) -> bool:
        """
        Clear processed logs for a specific contact or all contacts.

        Args:
            contact_id: Specific contact ID to clear (if None, clears all)

        Returns:
            bool: True if successful
        """
        try:
            if contact_id:
                return self.log_manager.clear_contact_records(contact_id)
            else:
                return self.log_manager.clear_all_records()
        except Exception as e:
            logger.error(f"Error clearing processed logs: {str(e)}")
            return False


def main():
    """Main entry point for the processing pipeline."""
    import argparse

    parser = argparse.ArgumentParser(description="Member Insights Processor")
    parser.add_argument("--config", default="config/config.yaml", help="Configuration file path")
    parser.add_argument(
        "--filter", help="Processing filter file path (overrides default from config)"
    )
    parser.add_argument("--contact-id", help="Process specific contact ID")
    parser.add_argument("--limit", type=int, help="Limit number of contacts to process")
    parser.add_argument(
        "--system-prompt",
        default="structured_insight",
        help="System prompt key to use (only structured_insight supported)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Run without saving results")
    parser.add_argument("--validate", action="store_true", help="Only validate setup")
    parser.add_argument("--stats", action="store_true", help="Show processing statistics")
    parser.add_argument(
        "--clear-logs",
        nargs="?",
        const="all",
        help="Clear processed logs (optionally specify contact ID, e.g., --clear-logs CNT-123456)",
    )
    parser.add_argument("--airtable-test", action="store_true", help="Test Airtable connection")
    parser.add_argument(
        "--airtable-batch-sync", action="store_true", help="Use enhanced batch sync to Airtable"
    )
    parser.add_argument(
        "--structured-airtable-test",
        action="store_true",
        help="Test structured insights Airtable connection",
    )
    parser.add_argument(
        "--structured-batch-sync",
        action="store_true",
        help="Sync existing JSON insights to structured Airtable",
    )
    parser.add_argument(
        "--show-filter", action="store_true", help="Show current processing filter configuration"
    )
    # Parallel/selection flags
    parser.add_argument(
        "--parallel", action="store_true", help="Enable contact-level parallel processing"
    )
    parser.add_argument(
        "--max-concurrent-contacts", type=int, help="Max contacts processed concurrently"
    )
    parser.add_argument(
        "--selection-batch-size", type=int, help="SQL selection batch size per wave"
    )
    parser.add_argument("--contacts-sql", help="Path to SQL file selecting prioritized contact_ids")
    parser.add_argument(
        "--contacts-sql-inline", help="Inline SQL selecting prioritized contact_ids"
    )

    args = parser.parse_args()

    try:
        # Initialize processor
        processor = MemberInsightsProcessor(args.config, args.filter)

        if args.validate:
            # Validate setup
            validation = processor.validate_setup()
            print("Setup Validation:")
            print(f"Valid: {validation['valid']}")
            if validation["issues"]:
                print("Issues:")
                for issue in validation["issues"]:
                    print(f"  - {issue}")
            if validation["warnings"]:
                print("Warnings:")
                for warning in validation["warnings"]:
                    print(f"  - {warning}")
            return

        if args.stats:
            # Show statistics
            stats = processor.get_processing_statistics()
            print("Processing Statistics:")
            for key, value in stats.items():
                print(f"{key}: {value}")
            return

        if args.clear_logs:
            # Clear logs
            contact_id = None if args.clear_logs == "all" else args.clear_logs
            success = processor.clear_processed_logs(contact_id)
            if contact_id:
                print(f"Clear logs for {contact_id}: {'Success' if success else 'Failed'}")
            else:
                print(f"Clear all logs: {'Success' if success else 'Failed'}")
            return

        if args.show_filter:
            # Show processing filter configuration
            if processor.processing_filter:
                filter_summary = processor.processing_filter.get_filter_summary()
                print("Processing Filter Configuration:")
                print(f"  Filter: {filter_summary['filter_info'].get('name', 'Unknown')}")
                print(
                    f"  Description: {filter_summary['filter_info'].get('description', 'No description')}"
                )
                print(f"  ENI Types Configured: {filter_summary['total_eni_types']}")
                print("\nProcessing Rules:")
                for eni_type, rule_desc in filter_summary["processing_rules_summary"].items():
                    print(f"  {eni_type}: {rule_desc}")
                print(f"\nSettings: {filter_summary['settings']}")
            else:
                print("No processing filter configured")
            return

        if args.airtable_test:
            # Test Airtable connection
            print("Testing Airtable Connection:")
            airtable_info = processor.airtable_writer.get_table_info()
            for key, value in airtable_info.items():
                print(f"  {key}: {value}")
            return

        if args.structured_airtable_test:
            # Test structured insights Airtable connection
            print("Testing Structured Insights Airtable Connection:")
            if processor.structured_airtable_writer:
                connection_info = processor.structured_airtable_writer.test_connection()
                for key, value in connection_info.items():
                    print(f"  {key}: {value}")
            else:
                print("  Structured Airtable writer not initialized")
            return

        if args.structured_batch_sync:
            # Sync existing JSON insights to structured Airtable
            print("Syncing existing JSON insights to Structured Airtable:")
            if processor.structured_airtable_writer and processor.json_writer:
                insights_data = processor.json_writer.batch_extract_for_airtable()
                if insights_data:
                    sync_results = (
                        processor.structured_airtable_writer.sync_structured_insights_batch(
                            insights_data, show_progress=True
                        )
                    )
                    print(f"Sync Results:")
                    print(f"  Total records: {sync_results['total_records']}")
                    print(f"  Successful: {sync_results['successful']}")
                    print(f"  Failed: {sync_results['failed']}")
                    if sync_results["errors"]:
                        print(f"  Errors: {len(sync_results['errors'])}")
                        for error in sync_results["errors"][:3]:  # Show first 3 errors
                            print(f"    - {error}")
                else:
                    print("  No JSON insights found to sync")
            else:
                print("  Structured Airtable writer or JSON writer not initialized")
            return

        # Process contacts
        if args.contact_id:
            # Process single contact
            result = processor.process_contact(
                contact_id=args.contact_id,
                system_prompt_key=args.system_prompt,
                dry_run=args.dry_run,
            )
            print(f"Processing result for {args.contact_id}:")
            print(f"Success: {result['success']}")
            print(f"Processed ENI IDs: {len(result['processed_eni_ids'])}")
            print(f"Errors: {len(result['errors'])}")
            # Token-loss summary for single-contact run
            if result.get("token_loss_events") or result.get("token_loss_groups_skipped"):
                print(
                    f"Token-Loss Summary: events={result.get('token_loss_events', 0)} | "
                    f"groups_skipped={result.get('token_loss_groups_skipped', 0)} | "
                    f"records_skipped={result.get('token_loss_records_skipped', 0)}"
                )
            # Token metrics summary for single-contact run
            print(
                f"[TOKENS] Summary for {args.contact_id}: est_input_tokens={result.get('est_input_tokens', 0)} "
                f"est_insights_tokens={result.get('est_insights_tokens', 0)} "
                f"generation_time_seconds={result.get('generation_time_seconds', 0.0):.2f}"
            )
        else:
            # Process multiple contacts
            # Ensure BigQuery connection first
            if not processor.bigquery_connector.connect():
                print("❌ Failed to connect to BigQuery")
                return

            # Load SQL (file or inline) if provided
            contacts_sql_text = None
            if args.contacts_sql_inline:
                contacts_sql_text = args.contacts_sql_inline
            elif args.contacts_sql:
                try:
                    with open(args.contacts_sql, "r", encoding="utf-8") as f:
                        contacts_sql_text = f.read()
                except Exception as e:
                    logger.warning(f"Failed to read contacts SQL file: {e}")

            # Parallel overrides to config
            if args.parallel or args.max_concurrent_contacts or args.selection_batch_size:
                try:
                    pcfg = processor.config_loader.get_parallel_config()
                    if args.parallel:
                        pcfg["enable"] = True
                    if args.max_concurrent_contacts:
                        pcfg["max_concurrent_contacts"] = int(args.max_concurrent_contacts)
                    if args.selection_batch_size:
                        pcfg.setdefault("selection", {})["batch_size"] = int(
                            args.selection_batch_size
                        )
                    # Write back into context for this run (in-memory only)
                    processor.config_loader.config_data.setdefault("processing", {}).setdefault(
                        "parallel", {}
                    ).update(pcfg)
                except Exception as e:
                    logger.warning(f"Failed to apply parallel CLI overrides: {e}")

            result = processor.process_multiple_contacts(
                contact_ids=(
                    None
                    if contacts_sql_text
                    else processor.bigquery_connector.get_unique_contact_ids(limit=args.limit)
                ),
                system_prompt_key=args.system_prompt,
                dry_run=args.dry_run,
                max_contacts=args.limit,
                contact_ids_sql=contacts_sql_text,
                selection_batch_size=args.selection_batch_size,
            )
            print("Batch processing completed:")
            print(f"Total contacts: {result['total_contacts']}")
            print(f"Successful: {result['successful_contacts']}")
            print(f"Failed: {result['failed_contacts']}")
            print(f"Total ENI IDs processed: {result['total_processed_eni_ids']}")

            # Enhanced Airtable batch sync if requested
            if args.airtable_batch_sync and processor.airtable_writer.connected:
                print("\nPerforming enhanced Airtable batch sync...")
                sync_result = processor.airtable_writer.sync_member_insights_from_processor_results(
                    result, show_progress=True
                )
                print(f"Airtable Sync Results:")
                print(f"  Total records: {sync_result.total_records}")
                print(f"  Successful: {sync_result.successful}")
                print(f"  Failed: {sync_result.failed}")
                print(f"  Processing time: {sync_result.processing_time:.2f} seconds")

                if sync_result.errors:
                    print(f"  Errors: {len(sync_result.errors)}")
                    for error in sync_result.errors[:3]:  # Show first 3 errors
                        print(f"    - {error}")

                # Export report
                report_path = processor.airtable_writer.export_sync_report(sync_result)
                print(f"  Report saved: {report_path}")
            elif args.airtable_batch_sync:
                print("\nAirtable batch sync requested but not connected to Airtable")

    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        print(f"Error: {str(e)}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
