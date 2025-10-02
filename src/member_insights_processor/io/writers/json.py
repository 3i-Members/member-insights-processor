"""
JSON Writer Module

This module handles writing AI-generated structured insights to JSON files.
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class JSONWriter:
    """Handles writing structured content to JSON files."""

    def __init__(self, output_directory: str = "var/output/structured_insights/"):
        """
        Initialize the JSON writer.

        Args:
            output_directory: Directory to write JSON files to
        """
        self.output_directory = Path(output_directory)
        self.output_directory.mkdir(parents=True, exist_ok=True)
        logger.info(f"JSON writer initialized with output directory: {self.output_directory}")

    def write_structured_insight(
        self,
        contact_id: str,
        eni_id: str,
        content: str,
        member_name: Optional[str] = None,
        eni_source_type: Optional[str] = None,
        eni_source_subtype: Optional[str] = None,
        additional_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Write structured insight content to a JSON file.

        Args:
            contact_id: Contact ID
            eni_id: ENI ID
            content: AI-generated content (should be JSON string)
            member_name: Member name
            eni_source_type: ENI source type
            eni_source_subtype: ENI source subtype
            additional_metadata: Additional metadata to include

        Returns:
            Optional[str]: Path to created file, None if failed
        """
        try:
            # Parse the content as JSON
            try:
                json_content = json.loads(content) if isinstance(content, str) else content
            except json.JSONDecodeError:
                logger.warning(
                    f"Content is not valid JSON for {contact_id}_{eni_id}, treating as raw content"
                )
                json_content = {"raw_content": content}

            # Create the full data structure with metadata
            file_data = {
                "metadata": {
                    "contact_id": contact_id,
                    "eni_id": eni_id,
                    "member_name": member_name,
                    "eni_source_type": eni_source_type,
                    "eni_source_subtype": eni_source_subtype,
                    "generated_at": datetime.now().isoformat(),
                    "generator": "structured_insight",
                },
                "insights": json_content,
            }

            # Add any additional metadata
            if additional_metadata:
                file_data["metadata"].update(additional_metadata)

            # Create filename
            filename = f"{contact_id}_{eni_id}.json"
            file_path = self.output_directory / filename

            # Write to file
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(file_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Successfully wrote structured insight JSON to: {file_path}")
            return str(file_path)

        except Exception as e:
            logger.error(f"Error writing JSON file for {contact_id}_{eni_id}: {str(e)}")
            return None

    def read_structured_insight(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Read a structured insight JSON file.

        Args:
            file_path: Path to the JSON file

        Returns:
            Optional[Dict[str, Any]]: Parsed JSON data, None if failed
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            logger.info(f"Successfully read structured insight JSON from: {file_path}")
            return data

        except Exception as e:
            logger.error(f"Error reading JSON file {file_path}: {str(e)}")
            return None

    def get_insight_data_for_airtable(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Extract insight data formatted for Airtable syncing.

        Args:
            file_path: Path to the JSON file

        Returns:
            Optional[Dict[str, Any]]: Data formatted for Airtable, None if failed
        """
        try:
            data = self.read_structured_insight(file_path)
            if not data:
                return None

            metadata = data.get("metadata", {})
            insights = data.get("insights", {})

            return {
                "contact_id": metadata.get("contact_id"),
                "member_name": metadata.get("member_name"),
                "json_data": insights,
                "eni_source_type": metadata.get("eni_source_type"),
                "eni_source_subtype": metadata.get("eni_source_subtype"),
                "generated_at": metadata.get("generated_at"),
            }

        except Exception as e:
            logger.error(f"Error extracting Airtable data from {file_path}: {str(e)}")
            return None

    def list_insight_files(self) -> list:
        """
        List all JSON insight files in the output directory.

        Returns:
            list: List of file paths
        """
        try:
            json_files = list(self.output_directory.glob("*.json"))
            logger.info(f"Found {len(json_files)} JSON insight files")
            return [str(f) for f in json_files]
        except Exception as e:
            logger.error(f"Error listing JSON files: {str(e)}")
            return []

    def batch_extract_for_airtable(self) -> list:
        """
        Extract all insight files for batch Airtable sync.

        Returns:
            list: List of data formatted for Airtable
        """
        insights_data = []
        json_files = self.list_insight_files()

        for file_path in json_files:
            data = self.get_insight_data_for_airtable(file_path)
            if data:
                insights_data.append(data)

        logger.info(f"Extracted {len(insights_data)} insights for Airtable sync")
        return insights_data


def create_json_writer(output_directory: str = "var/output/structured_insights/") -> JSONWriter:
    """
    Factory function to create a JSON writer.

    Args:
        output_directory: Directory to write JSON files to

    Returns:
        JSONWriter: Configured JSON writer
    """
    return JSONWriter(output_directory)
