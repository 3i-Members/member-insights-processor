"""
Configuration Loader Module

This module handles loading and managing configuration files that map
ENI types and subtypes to file locations, and system prompt keys to prompts.
"""

import yaml
from pathlib import Path
from typing import Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


class ConfigLoader:
    """Handles loading and managing YAML configuration files."""

    def __init__(self, config_file_path: str = "config/config.yaml"):
        """
        Initialize the configuration loader.

        Args:
            config_file_path: Path to the YAML configuration file
        """
        self.config_file_path = Path(config_file_path)
        self.config_data = None
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        try:
            if not self.config_file_path.exists():
                logger.error(f"Configuration file not found: {self.config_file_path}")
                self.config_data = {}
                return

            with open(self.config_file_path, "r", encoding="utf-8") as f:
                self.config_data = yaml.safe_load(f) or {}

            logger.info(f"Successfully loaded configuration from {self.config_file_path}")

        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error in {self.config_file_path}: {str(e)}")
            self.config_data = {}
        except Exception as e:
            logger.error(f"Error loading configuration file: {str(e)}")
            self.config_data = {}

    def reload_config(self) -> bool:
        """
        Reload configuration from file.

        Returns:
            bool: True if reload successful, False otherwise
        """
        try:
            self._load_config()
            return self.config_data is not None
        except Exception as e:
            logger.error(f"Error reloading configuration: {str(e)}")
            return False

    def get_context_file_path(self, eni_type: str, eni_subtype: str) -> Optional[str]:
        """
        Get the file path for a specific ENI type and subtype.

        Args:
            eni_type: The ENI type
            eni_subtype: The ENI subtype (can be None, empty string, or 'null')

        Returns:
            Optional[str]: File path if found, None otherwise
        """
        try:
            eni_mappings = self.config_data.get("eni_mappings", {})

            # Check if ENI type exists
            if eni_type not in eni_mappings:
                logger.warning(f"ENI type '{eni_type}' not found in configuration")
                return None

            type_mappings = eni_mappings[eni_type]

            # Normalize null/empty subtypes to 'null'
            normalized_subtype = eni_subtype
            if (
                not eni_subtype
                or eni_subtype.strip() == ""
                or eni_subtype.lower() in ["none", "nan"]
            ):
                normalized_subtype = "null"

            # Check for exact subtype match (including 'null')
            if normalized_subtype in type_mappings:
                file_path = type_mappings[normalized_subtype]
                logger.debug(
                    f"Found exact mapping for {eni_type}/{normalized_subtype}: {file_path}"
                )
                return file_path

            # If 'null' subtype and no explicit 'null' mapping, try 'default'
            if normalized_subtype == "null" and "default" in type_mappings:
                file_path = type_mappings["default"]
                logger.info(
                    f"Using default mapping for null subtype {eni_type}/{eni_subtype}: {file_path}"
                )
                return file_path

            # Check for default mapping for any other unmapped subtypes
            if "default" in type_mappings:
                file_path = type_mappings["default"]
                logger.info(f"Using default mapping for {eni_type}/{eni_subtype}: {file_path}")
                return file_path

            logger.warning(
                f"No mapping found for {eni_type}/{eni_subtype} and no default available"
            )
            return None

        except Exception as e:
            logger.error(f"Error getting context file path for {eni_type}/{eni_subtype}: {str(e)}")
            return None

    def get_context_file_paths(self, eni_type: str, eni_subtype: str) -> Dict[str, Optional[str]]:
        """
        Get both default and subtype-specific context file paths.

        Args:
            eni_type: The ENI type
            eni_subtype: The ENI subtype (can be None, empty string, or 'null')

        Returns:
            Dict[str, Optional[str]]: Dictionary with 'default' and 'subtype' file paths
        """
        try:
            eni_mappings = self.config_data.get("eni_mappings", {})
            result = {"default": None, "subtype": None}

            # Check if ENI type exists
            if eni_type not in eni_mappings:
                logger.warning(f"ENI type '{eni_type}' not found in configuration")
                return result

            type_mappings = eni_mappings[eni_type]

            # Get default context path
            if "default" in type_mappings:
                result["default"] = type_mappings["default"]
                logger.debug(f"Found default context for {eni_type}: {result['default']}")

            # Normalize null/empty subtypes to 'null'
            normalized_subtype = eni_subtype
            if (
                not eni_subtype
                or eni_subtype.strip() == ""
                or eni_subtype.lower() in ["none", "nan"]
            ):
                normalized_subtype = "null"

            # Get subtype-specific context path (if different from default)
            if normalized_subtype in type_mappings:
                subtype_path = type_mappings[normalized_subtype]
                # Only use subtype path if it's different from default
                if subtype_path != result["default"]:
                    result["subtype"] = subtype_path
                    logger.debug(
                        f"Found subtype context for {eni_type}/{normalized_subtype}: {result['subtype']}"
                    )

            return result

        except Exception as e:
            logger.error(f"Error getting context file paths for {eni_type}/{eni_subtype}: {str(e)}")
            return {"default": None, "subtype": None}

    def get_system_prompt_path(self, prompt_key: str) -> Optional[str]:
        """
        Get the file path for a system prompt.

        Args:
            prompt_key: The system prompt key

        Returns:
            Optional[str]: File path if found, None otherwise
        """
        try:
            system_prompts = self.config_data.get("system_prompts", {})

            if prompt_key in system_prompts:
                file_path = system_prompts[prompt_key]
                logger.debug(f"Found system prompt path for '{prompt_key}': {file_path}")
                return file_path

            logger.warning(f"System prompt key '{prompt_key}' not found in configuration")
            return None

        except Exception as e:
            logger.error(f"Error getting system prompt path for '{prompt_key}': {str(e)}")
            return None

    def get_all_eni_mappings(self) -> Dict[str, Dict[str, str]]:
        """
        Get all ENI mappings from configuration.

        Returns:
            Dict[str, Dict[str, str]]: All ENI type/subtype mappings
        """
        try:
            return self.config_data.get("eni_mappings", {})
        except Exception as e:
            logger.error(f"Error getting ENI mappings: {str(e)}")
            return {}

    def get_all_system_prompts(self) -> Dict[str, str]:
        """
        Get all system prompt mappings from configuration.

        Returns:
            Dict[str, str]: All system prompt key/path mappings
        """
        try:
            return self.config_data.get("system_prompts", {})
        except Exception as e:
            logger.error(f"Error getting system prompts: {str(e)}")
            return {}

    def get_bigquery_config(self) -> Dict[str, Any]:
        """
        Get BigQuery configuration.

        Returns:
            Dict[str, Any]: BigQuery configuration
        """
        try:
            return self.config_data.get("bigquery", {})
        except Exception as e:
            logger.error(f"Error getting BigQuery configuration: {str(e)}")
            return {}

    def get_airtable_config(self) -> Dict[str, Any]:
        """
        Get Airtable configuration.

        Returns:
            Dict[str, Any]: Airtable configuration
        """
        try:
            return self.config_data.get("airtable", {})
        except Exception as e:
            logger.error(f"Error getting Airtable configuration: {str(e)}")
            return {}

    def get_processing_config(self) -> Dict[str, Any]:
        """
        Get processing configuration settings.

        Returns:
            Dict[str, Any]: Processing configuration
        """
        try:
            return self.config_data.get("processing", {})
        except Exception as e:
            logger.error(f"Error getting processing configuration: {str(e)}")
            return {}

    def get_gemini_config(self) -> Dict[str, Any]:
        """
        Get Gemini AI configuration.

        Returns:
            Dict[str, Any]: Gemini configuration
        """
        try:
            return self.config_data.get("gemini", {})
        except Exception as e:
            logger.error(f"Error getting Gemini configuration: {str(e)}")
            return {}

    def get_openai_config(self) -> Dict[str, Any]:
        """
        Get OpenAI configuration.

        Returns:
            Dict[str, Any]: OpenAI configuration
        """
        try:
            return self.config_data.get("openai", {})
        except Exception as e:
            logger.error(f"Error getting OpenAI configuration: {str(e)}")
            return {}

    def get_anthropic_config(self) -> Dict[str, Any]:
        """
        Get Anthropic configuration.

        Returns:
            Dict[str, Any]: Anthropic configuration
        """
        try:
            return self.config_data.get("anthropic", {})
        except Exception as e:
            logger.error(f"Error getting Anthropic configuration: {str(e)}")
            return {}

    def get_ai_provider(self) -> str:
        """
        Get the configured AI provider.

        Returns:
            str: AI provider ('openai' or 'gemini')
        """
        try:
            processing_config = self.config_data.get("processing", {})
            return processing_config.get("ai_provider", "gemini")
        except Exception as e:
            logger.error(f"Error getting AI provider: {str(e)}")
            return "gemini"

    def get_filter_config(self) -> Dict[str, Any]:
        """
        Get processing filter configuration.

        Returns:
            Dict[str, Any]: Filter configuration
        """
        try:
            processing_config = self.config_data.get("processing", {})
            return processing_config.get("filter_config", {})
        except Exception as e:
            logger.error(f"Error getting filter configuration: {str(e)}")
            return {}

    def get_default_filter_file(self) -> Optional[str]:
        """
        Get the default processing filter file path.

        Returns:
            Optional[str]: Default filter file path
        """
        try:
            filter_config = self.get_filter_config()
            return filter_config.get("default_filter_file")
        except Exception as e:
            logger.error(f"Error getting default filter file: {str(e)}")
            return None

    def validate_configuration(self) -> Dict[str, Any]:
        """
        Validate the configuration and return a report.

        Returns:
            Dict[str, Any]: Validation report
        """
        report = {"valid": True, "issues": [], "warnings": [], "statistics": {}}

        try:
            if not self.config_data:
                report["valid"] = False
                report["issues"].append("Configuration data is empty or failed to load")
                return report

            # Validate ENI mappings
            eni_mappings = self.config_data.get("eni_mappings", {})
            if not eni_mappings:
                report["warnings"].append("No ENI mappings found in configuration")
            else:
                total_mappings = 0
                for eni_type, subtypes in eni_mappings.items():
                    if not isinstance(subtypes, dict):
                        report["issues"].append(
                            f"ENI type '{eni_type}' mappings should be a dictionary"
                        )
                        continue

                    total_mappings += len(subtypes)

                    # Check if files exist
                    for subtype, file_path in subtypes.items():
                        if not Path(file_path).exists():
                            report["warnings"].append(
                                f"Context file not found: {file_path} (for {eni_type}/{subtype})"
                            )

                report["statistics"]["total_eni_mappings"] = total_mappings

            # Validate system prompts
            system_prompts = self.config_data.get("system_prompts", {})
            if not system_prompts:
                report["warnings"].append("No system prompts found in configuration")
            else:
                report["statistics"]["total_system_prompts"] = len(system_prompts)

                # Check if prompt files exist
                for prompt_key, file_path in system_prompts.items():
                    if not Path(file_path).exists():
                        report["warnings"].append(
                            f"System prompt file not found: {file_path} (for key '{prompt_key}')"
                        )

            # Validate BigQuery configuration
            bigquery_config = self.config_data.get("bigquery", {})
            required_bq_fields = ["project_id", "dataset_id", "table_name"]
            missing_bq_fields = [
                field for field in required_bq_fields if not bigquery_config.get(field)
            ]

            if missing_bq_fields:
                report["issues"].append(
                    f"Missing required BigQuery configuration fields: {missing_bq_fields}"
                )

            # Validate Airtable configuration
            airtable_config = self.config_data.get("airtable", {})
            if airtable_config:
                field_mapping = airtable_config.get("field_mapping", {})
                if not field_mapping:
                    report["warnings"].append("Airtable field mapping is empty")

            if report["issues"]:
                report["valid"] = False

            logger.info(
                f"Configuration validation complete: {len(report['issues'])} issues, {len(report['warnings'])} warnings"
            )
            return report

        except Exception as e:
            report["valid"] = False
            report["issues"].append(f"Unexpected error during validation: {str(e)}")
            return report

    def get_available_eni_types(self) -> list:
        """
        Get list of available ENI types.

        Returns:
            list: List of available ENI types
        """
        try:
            eni_mappings = self.config_data.get("eni_mappings", {})
            return list(eni_mappings.keys())
        except Exception as e:
            logger.error(f"Error getting available ENI types: {str(e)}")
            return []

    def get_available_subtypes(self, eni_type: str) -> list:
        """
        Get list of available subtypes for an ENI type.

        Args:
            eni_type: The ENI type

        Returns:
            list: List of available subtypes (excluding 'default')
        """
        try:
            eni_mappings = self.config_data.get("eni_mappings", {})
            if eni_type in eni_mappings:
                subtypes = list(eni_mappings[eni_type].keys())
                # Remove 'default' from the list as it's not a real subtype
                return [subtype for subtype in subtypes if subtype != "default"]
            return []
        except Exception as e:
            logger.error(f"Error getting available subtypes for {eni_type}: {str(e)}")
            return []

    def get_config_value(self, key_path: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.

        Args:
            key_path: Dot-separated path to the configuration value (e.g., 'bigquery.project_id')
            default: Default value if key not found

        Returns:
            Any: Configuration value or default
        """
        try:
            keys = key_path.split(".")
            value = self.config_data

            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return default

            return value

        except Exception as e:
            logger.error(f"Error getting config value for '{key_path}': {str(e)}")
            return default

    def get_parallel_config(self) -> Dict[str, Any]:
        """Get parallel processing configuration with defaults and guardrails."""
        try:
            processing_config = self.config_data.get("processing", {}) or {}
            parallel_cfg = processing_config.get("parallel", {}) or {}
            defaults = {
                "enable": False,
                "max_concurrent_contacts": 1,
                "selection": {
                    "sql_file": None,
                    "batch_size": 100,
                },
                "claims": {
                    "enabled": True,
                    "ttl_seconds": 900,
                    "backoff_seconds": {
                        "min": 1,
                        "max": 5,
                    },
                },
            }
            merged = {**defaults, **parallel_cfg}
            # Deep merge nested dicts
            sel = parallel_cfg.get("selection") or {}
            merged["selection"] = {**defaults["selection"], **sel}
            claims = parallel_cfg.get("claims") or {}
            bo = claims.get("backoff_seconds") or {}
            merged["claims"] = {
                **defaults["claims"],
                **claims,
                "backoff_seconds": {**defaults["claims"]["backoff_seconds"], **bo},
            }
            # Guardrails
            if int(merged["max_concurrent_contacts"]) < 1:
                merged["max_concurrent_contacts"] = 1
            if int(merged["selection"]["batch_size"]) < 1:
                merged["selection"]["batch_size"] = 1
            return merged
        except Exception as e:
            logger.error(f"Error getting parallel processing configuration: {str(e)}")
            return {
                "enable": False,
                "max_concurrent_contacts": 1,
                "selection": {
                    "sql_file": None,
                    "batch_size": 100,
                },
                "claims": {
                    "enabled": True,
                    "ttl_seconds": 900,
                    "backoff_seconds": {
                        "min": 1,
                        "max": 5,
                    },
                },
            }


def create_config_loader(config_file_path: Optional[str] = None) -> ConfigLoader:
    """
    Factory function to create a ConfigLoader instance.

    Args:
        config_file_path: Optional custom path to configuration file

    Returns:
        ConfigLoader: Configured loader instance
    """
    if config_file_path is None:
        config_file_path = "config/config.yaml"

    return ConfigLoader(config_file_path)
