"""
Processing Filter Module

This module handles loading and applying processing filters for ENI types and subtypes.
It determines which records should be processed based on configuration rules.
"""

import yaml
import logging
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set

logger = logging.getLogger(__name__)


class ProcessingFilter:
    """Handles filtering of ENI records based on type and subtype rules."""

    def __init__(self, filter_config_path: str):
        """
        Initialize the processing filter.

        Args:
            filter_config_path: Path to the processing filter YAML file
        """
        self.filter_config_path = Path(filter_config_path)
        self.filter_data = {}
        self.processing_rules = {}
        self.processing_settings = {}
        self._load_filter_config()

    def _load_filter_config(self) -> None:
        """Load the processing filter configuration from file."""
        try:
            if not self.filter_config_path.exists():
                raise FileNotFoundError(
                    f"Processing filter file not found: {self.filter_config_path}"
                )

            with open(self.filter_config_path, "r", encoding="utf-8") as f:
                self.filter_data = yaml.safe_load(f)

            if not self.filter_data:
                raise ValueError("Processing filter file is empty or invalid")

            # Extract processing rules and settings
            self.processing_rules = self.filter_data.get("eni_processing_rules", {})
            self.processing_settings = self.filter_data.get("processing_settings", {})

            filter_info = self.filter_data.get("filter_info", {})
            filter_name = filter_info.get("name", "Unknown")

            logger.info(f"Successfully loaded processing filter: {filter_name}")
            logger.info(f"Loaded rules for {len(self.processing_rules)} ENI types")

        except Exception as e:
            logger.error(
                f"Failed to load processing filter from {self.filter_config_path}: {str(e)}"
            )
            raise

    def should_process_record(self, eni_type: str, eni_subtype: str) -> bool:
        """
        Determine if a record should be processed based on its ENI type and subtype.

        Args:
            eni_type: The ENI source type
            eni_subtype: The ENI source subtype

        Returns:
            bool: True if the record should be processed, False otherwise
        """
        try:
            # Check if ENI type is in processing rules
            if eni_type not in self.processing_rules:
                if self.processing_settings.get("log_skipped_records", False):
                    logger.debug(
                        f"Skipping {eni_type}/{eni_subtype}: ENI type not in processing rules"
                    )
                return False

            rule = self.processing_rules[eni_type]

            # Normalize null subtypes to 'null' for matching
            normalized_subtype = eni_subtype
            if (
                not eni_subtype
                or str(eni_subtype).strip() == ""
                or str(eni_subtype).lower() in ["none", "nan"]
            ):
                normalized_subtype = "null"

            # NULL subtypes are ALWAYS processed regardless of rule configuration
            if normalized_subtype == "null":
                return True

            # Handle "none" rule or empty rule - only NULL subtypes are processed
            if rule == "none" or rule is None:
                if self.processing_settings.get("log_skipped_records", False):
                    logger.debug(
                        f"Skipping {eni_type}/{eni_subtype}: only NULL subtypes processed (no explicit subtypes defined)"
                    )
                return False

            # Handle list of specific subtypes
            if isinstance(rule, list):
                should_process = normalized_subtype in rule

                if not should_process and self.processing_settings.get(
                    "log_skipped_records", False
                ):
                    logger.debug(
                        f"Skipping {eni_type}/{eni_subtype}: subtype not in allowed list {rule}"
                    )

                return should_process

            # If rule is not recognized, only process NULL subtypes
            logger.warning(
                f"Invalid processing rule for {eni_type}: {rule}. Expected list of subtypes. Only processing NULL subtypes."
            )
            return False

        except Exception as e:
            logger.error(f"Error checking processing rule for {eni_type}/{eni_subtype}: {str(e)}")
            return False

    def filter_dataframe(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Filter a DataFrame to include only records that should be processed.

        Args:
            df: DataFrame with eni_source_type and eni_source_subtype columns

        Returns:
            Tuple of (filtered_dataframe, filtering_stats)
        """
        if df.empty:
            return df, {"original_count": 0, "filtered_count": 0, "skipped_count": 0}

        try:
            original_count = len(df)

            # Apply filtering
            mask = df.apply(
                lambda row: self.should_process_record(
                    row["eni_source_type"], row["eni_source_subtype"]
                ),
                axis=1,
            )

            filtered_df = df[mask].copy()
            filtered_count = len(filtered_df)
            skipped_count = original_count - filtered_count

            # Generate statistics
            stats = {
                "original_count": original_count,
                "filtered_count": filtered_count,
                "skipped_count": skipped_count,
                "filter_efficiency": (
                    (filtered_count / original_count * 100) if original_count > 0 else 0
                ),
            }

            # Log statistics if enabled
            if self.processing_settings.get("show_processing_stats", False):
                logger.info(
                    f"Processing filter results: {filtered_count}/{original_count} records included ({stats['filter_efficiency']:.1f}%)"
                )

                if skipped_count > 0:
                    # Show breakdown of skipped records by type
                    skipped_df = df[~mask]
                    skipped_breakdown = (
                        skipped_df.groupby(["eni_source_type", "eni_source_subtype"])
                        .size()
                        .to_dict()
                    )
                    logger.info(
                        f"Skipped records breakdown: {dict(list(skipped_breakdown.items())[:10])}"
                    )  # Show first 10

            return filtered_df, stats

        except Exception as e:
            logger.error(f"Error filtering DataFrame: {str(e)}")
            return df, {
                "original_count": len(df),
                "filtered_count": len(df),
                "skipped_count": 0,
                "error": str(e),
            }

    def get_allowed_eni_types(self) -> Set[str]:
        """
        Get the set of ENI types that are allowed for processing.

        Returns:
            Set[str]: Set of allowed ENI type names
        """
        return set(self.processing_rules.keys())

    def get_allowed_subtypes_for_type(self, eni_type: str) -> Optional[List[str]]:
        """
        Get the allowed subtypes for a specific ENI type.

        Args:
            eni_type: The ENI type to check

        Returns:
            Optional[List[str]]: List of allowed subtypes, or None if not configured
        """
        return self.processing_rules.get(eni_type)

    def validate_filter_against_data(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Validate the filter configuration against actual data.

        Args:
            df: DataFrame containing ENI data to validate against

        Returns:
            Dict[str, Any]: Validation results
        """
        validation_results = {"valid": True, "issues": [], "warnings": [], "statistics": {}}

        try:
            if df.empty:
                validation_results["warnings"].append("No data provided for validation")
                return validation_results

            # Get unique ENI types and subtypes from data
            data_types = set(df["eni_source_type"].unique())
            configured_types = self.get_allowed_eni_types()

            # Check for configured types not in data
            missing_in_data = configured_types - data_types
            if missing_in_data:
                validation_results["warnings"].append(
                    f"Configured types not found in data: {missing_in_data}"
                )

            # Check for data types not configured
            unconfigured_types = data_types - configured_types
            if unconfigured_types:
                validation_results["warnings"].append(
                    f"Data types not configured for processing: {unconfigured_types}"
                )

            # Validate specific subtypes
            for eni_type in configured_types & data_types:
                allowed_subtypes = self.get_allowed_subtypes_for_type(eni_type)

                if isinstance(allowed_subtypes, list):
                    # Get actual subtypes for this ENI type from data
                    actual_subtypes = set(
                        df[df["eni_source_type"] == eni_type]["eni_source_subtype"]
                        .fillna("null")
                        .astype(str)
                    )

                    # Normalize null representations
                    normalized_actual = set()
                    for subtype in actual_subtypes:
                        if (
                            not subtype
                            or subtype.strip() == ""
                            or subtype.lower() in ["none", "nan"]
                        ):
                            normalized_actual.add("null")
                        else:
                            normalized_actual.add(subtype)

                    # Check for configured subtypes not in data
                    missing_subtypes = set(allowed_subtypes) - normalized_actual
                    if missing_subtypes:
                        validation_results["warnings"].append(
                            f"Configured subtypes for {eni_type} not found in data: {missing_subtypes}"
                        )

            # Generate statistics
            if configured_types:
                filter_coverage = len(configured_types & data_types) / len(data_types) * 100
                validation_results["statistics"]["filter_coverage_percent"] = filter_coverage
                validation_results["statistics"]["configured_types_count"] = len(configured_types)
                validation_results["statistics"]["data_types_count"] = len(data_types)

        except Exception as e:
            validation_results["valid"] = False
            validation_results["issues"].append(f"Validation error: {str(e)}")

        return validation_results

    def get_filter_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the current filter configuration.

        Returns:
            Dict[str, Any]: Filter configuration summary
        """
        summary = {
            "filter_info": self.filter_data.get("filter_info", {}),
            "total_eni_types": len(self.processing_rules),
            "processing_rules_summary": {},
            "settings": self.processing_settings,
        }

        # Summarize processing rules
        for eni_type, rule in self.processing_rules.items():
            if isinstance(rule, list):
                summary["processing_rules_summary"][
                    eni_type
                ] = f"{len(rule)} specific subtypes: {rule}"
            else:
                summary["processing_rules_summary"][eni_type] = str(rule)

        return summary


def create_processing_filter(filter_config_path: str) -> ProcessingFilter:
    """
    Factory function to create a ProcessingFilter instance.

    Args:
        filter_config_path: Path to the processing filter configuration file

    Returns:
        ProcessingFilter: Configured filter instance
    """
    return ProcessingFilter(filter_config_path)
