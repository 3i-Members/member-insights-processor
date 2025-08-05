"""
Airtable Writer Module

This module handles syncing markdown files and AI-generated content
to Airtable using the pyairtable library.
"""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import logging

try:
    from pyairtable import Table
    PYAIRTABLE_AVAILABLE = True
except ImportError:
    PYAIRTABLE_AVAILABLE = False
    Table = None

logger = logging.getLogger(__name__)


class AirtableWriter:
    """Handles writing markdown content and metadata to Airtable."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_id: Optional[str] = None,
        table_name: Optional[str] = None
    ):
        """
        Initialize the Airtable writer.
        
        Args:
            api_key: Airtable API key (if None, will try to get from environment)
            base_id: Airtable base ID (if None, will try to get from environment)
            table_name: Airtable table name (if None, will try to get from environment)
        """
        if not PYAIRTABLE_AVAILABLE:
            logger.error("pyairtable library not available. Install with: pip install pyairtable")
            self.table = None
            return
        
        self.api_key = api_key or os.getenv('AIRTABLE_API_KEY')
        self.base_id = base_id or os.getenv('AIRTABLE_BASE_ID')
        self.table_name = table_name or os.getenv('AIRTABLE_TABLE_NAME')
        
        self.table = None
        self._initialize_table()
    
    def _initialize_table(self) -> None:
        """Initialize the Airtable table connection."""
        try:
            if not all([self.api_key, self.base_id, self.table_name]):
                missing = []
                if not self.api_key:
                    missing.append("API key")
                if not self.base_id:
                    missing.append("base ID")
                if not self.table_name:
                    missing.append("table name")
                
                logger.error(f"Missing Airtable configuration: {', '.join(missing)}")
                return
            
            self.table = Table(self.api_key, self.base_id, self.table_name)
            logger.info(f"Successfully initialized Airtable connection: {self.table_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Airtable connection: {str(e)}")
            self.table = None
    
    def test_connection(self) -> bool:
        """
        Test the connection to Airtable.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            if not self.table:
                return False
            
            # Try to fetch the first record to test connection
            records = self.table.all(max_records=1)
            logger.info("Airtable connection test successful")
            return True
            
        except Exception as e:
            logger.error(f"Airtable connection test failed: {str(e)}")
            return False
    
    def parse_markdown_metadata(self, markdown_content: str) -> Dict[str, Any]:
        """
        Parse YAML front matter from markdown content.
        
        Args:
            markdown_content: Full markdown content with metadata
            
        Returns:
            Dict[str, Any]: Parsed metadata
        """
        try:
            if not markdown_content.startswith('---\n'):
                return {}
            
            # Split the content to extract front matter
            parts = markdown_content.split('---\n', 2)
            if len(parts) < 3:
                return {}
            
            front_matter = parts[1]
            metadata = {}
            
            # Simple YAML parsing for basic key-value pairs
            for line in front_matter.split('\n'):
                line = line.strip()
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Remove quotes if present
                    if (value.startswith('"') and value.endswith('"')) or \
                       (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]
                    
                    # Convert basic types
                    if value.lower() == 'null':
                        value = None
                    elif value.lower() == 'true':
                        value = True
                    elif value.lower() == 'false':
                        value = False
                    elif value.isdigit():
                        value = int(value)
                    
                    metadata[key] = value
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error parsing markdown metadata: {str(e)}")
            return {}
    
    def extract_content_from_markdown(self, markdown_content: str) -> str:
        """
        Extract the main content from markdown, excluding front matter.
        
        Args:
            markdown_content: Full markdown content
            
        Returns:
            str: Content without front matter
        """
        try:
            if markdown_content.startswith('---\n'):
                parts = markdown_content.split('---\n', 2)
                if len(parts) >= 3:
                    return parts[2].strip()
            
            return markdown_content.strip()
            
        except Exception as e:
            logger.error(f"Error extracting content from markdown: {str(e)}")
            return markdown_content
    
    def prepare_airtable_record(
        self,
        markdown_content: str,
        field_mapping: Dict[str, str],
        additional_fields: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Prepare a record for Airtable from markdown content.
        
        Args:
            markdown_content: Full markdown content with metadata
            field_mapping: Mapping of data fields to Airtable field names
            additional_fields: Additional field values to include
            
        Returns:
            Dict[str, Any]: Prepared Airtable record
        """
        try:
            # Parse metadata and content
            metadata = self.parse_markdown_metadata(markdown_content)
            content = self.extract_content_from_markdown(markdown_content)
            
            # Start building the record
            record = {}
            
            # Apply field mapping
            for source_field, airtable_field in field_mapping.items():
                if source_field == 'content':
                    record[airtable_field] = content
                elif source_field in metadata:
                    record[airtable_field] = metadata[source_field]
            
            # Add additional fields
            if additional_fields:
                record.update(additional_fields)
            
            # Add default fields if not present
            if 'Last Updated' in field_mapping.values() and 'Last Updated' not in record:
                record['Last Updated'] = datetime.now().isoformat()
            
            return record
            
        except Exception as e:
            logger.error(f"Error preparing Airtable record: {str(e)}")
            return {}
    
    def find_existing_record(self, contact_id: str, contact_id_field: str = "Contact ID") -> Optional[Dict[str, Any]]:
        """
        Find an existing record by contact ID.
        
        Args:
            contact_id: The contact ID to search for
            contact_id_field: The Airtable field name for contact ID
            
        Returns:
            Optional[Dict[str, Any]]: Existing record if found, None otherwise
        """
        try:
            if not self.table:
                return None
            
            # Search for records with matching contact ID
            formula = f"{{{contact_id_field}}} = '{contact_id}'"
            records = self.table.all(formula=formula)
            
            if records:
                logger.debug(f"Found existing record for contact ID: {contact_id}")
                return records[0]  # Return the first match
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding existing record: {str(e)}")
            return None
    
    def create_record(self, record_data: Dict[str, Any]) -> Optional[str]:
        """
        Create a new record in Airtable.
        
        Args:
            record_data: Data for the new record
            
        Returns:
            Optional[str]: Record ID if successful, None otherwise
        """
        try:
            if not self.table:
                logger.error("Airtable table not initialized")
                return None
            
            created_record = self.table.create(record_data)
            record_id = created_record['id']
            
            logger.info(f"Successfully created Airtable record: {record_id}")
            return record_id
            
        except Exception as e:
            logger.error(f"Error creating Airtable record: {str(e)}")
            return None
    
    def update_record(self, record_id: str, record_data: Dict[str, Any]) -> bool:
        """
        Update an existing record in Airtable.
        
        Args:
            record_id: ID of the record to update
            record_data: Data to update
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not self.table:
                logger.error("Airtable table not initialized")
                return False
            
            self.table.update(record_id, record_data)
            logger.info(f"Successfully updated Airtable record: {record_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating Airtable record: {str(e)}")
            return False
    
    def sync_markdown_file(
        self,
        markdown_file_path: str,
        field_mapping: Dict[str, str],
        additional_fields: Optional[Dict[str, Any]] = None,
        contact_id_field: str = "Contact ID"
    ) -> Optional[str]:
        """
        Sync a markdown file to Airtable.
        
        Args:
            markdown_file_path: Path to the markdown file
            field_mapping: Mapping of data fields to Airtable field names
            additional_fields: Additional field values
            contact_id_field: Airtable field name for contact ID
            
        Returns:
            Optional[str]: Record ID if successful, None otherwise
        """
        try:
            # Read markdown file
            file_path = Path(markdown_file_path)
            if not file_path.exists():
                logger.error(f"Markdown file not found: {markdown_file_path}")
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                markdown_content = f.read()
            
            # Prepare record data
            record_data = self.prepare_airtable_record(
                markdown_content=markdown_content,
                field_mapping=field_mapping,
                additional_fields=additional_fields
            )
            
            if not record_data:
                logger.error("Failed to prepare record data from markdown")
                return None
            
            # Check if record exists
            contact_id = record_data.get(contact_id_field)
            if contact_id:
                existing_record = self.find_existing_record(contact_id, contact_id_field)
                
                if existing_record:
                    # Update existing record
                    success = self.update_record(existing_record['id'], record_data)
                    return existing_record['id'] if success else None
                else:
                    # Create new record
                    return self.create_record(record_data)
            else:
                # No contact ID, always create new record
                return self.create_record(record_data)
                
        except Exception as e:
            logger.error(f"Error syncing markdown file to Airtable: {str(e)}")
            return None
    
    def sync_content_directly(
        self,
        content: str,
        contact_id: str,
        eni_id: str,
        field_mapping: Dict[str, str],
        additional_fields: Optional[Dict[str, Any]] = None,
        contact_id_field: str = "Contact ID"
    ) -> Optional[str]:
        """
        Sync content directly to Airtable without a file.
        
        Args:
            content: The content to sync
            contact_id: Contact ID
            eni_id: ENI ID
            field_mapping: Mapping of data fields to Airtable field names
            additional_fields: Additional field values
            contact_id_field: Airtable field name for contact ID
            
        Returns:
            Optional[str]: Record ID if successful, None otherwise
        """
        try:
            # Build record data
            record_data = {}
            
            # Apply field mapping
            for source_field, airtable_field in field_mapping.items():
                if source_field == 'content':
                    record_data[airtable_field] = content
                elif source_field == 'contact_id':
                    record_data[airtable_field] = contact_id
                elif source_field == 'eni_id':
                    record_data[airtable_field] = eni_id
            
            # Add additional fields
            if additional_fields:
                record_data.update(additional_fields)
            
            # Add timestamps
            record_data['Last Updated'] = datetime.now().isoformat()
            
            # Check if record exists
            existing_record = self.find_existing_record(contact_id, contact_id_field)
            
            if existing_record:
                # Update existing record
                success = self.update_record(existing_record['id'], record_data)
                return existing_record['id'] if success else None
            else:
                # Create new record
                return self.create_record(record_data)
                
        except Exception as e:
            logger.error(f"Error syncing content directly to Airtable: {str(e)}")
            return None
    
    def batch_sync_files(
        self,
        file_paths: List[str],
        field_mapping: Dict[str, str],
        additional_fields: Optional[Dict[str, Any]] = None,
        contact_id_field: str = "Contact ID"
    ) -> Dict[str, Optional[str]]:
        """
        Sync multiple markdown files to Airtable in batch.
        
        Args:
            file_paths: List of markdown file paths
            field_mapping: Mapping of data fields to Airtable field names
            additional_fields: Additional field values
            contact_id_field: Airtable field name for contact ID
            
        Returns:
            Dict[str, Optional[str]]: Mapping of file paths to record IDs
        """
        results = {}
        
        for file_path in file_paths:
            try:
                record_id = self.sync_markdown_file(
                    markdown_file_path=file_path,
                    field_mapping=field_mapping,
                    additional_fields=additional_fields,
                    contact_id_field=contact_id_field
                )
                results[file_path] = record_id
                
                # Add small delay to avoid rate limiting
                import time
                time.sleep(0.2)
                
            except Exception as e:
                logger.error(f"Error syncing file {file_path}: {str(e)}")
                results[file_path] = None
        
        return results
    
    def get_table_info(self) -> Dict[str, Any]:
        """
        Get information about the Airtable table.
        
        Returns:
            Dict[str, Any]: Table information
        """
        try:
            info = {
                'api_configured': bool(self.api_key),
                'base_id': self.base_id,
                'table_name': self.table_name,
                'table_initialized': bool(self.table),
                'connection_test': False,
                'record_count': None
            }
            
            if self.table:
                info['connection_test'] = self.test_connection()
                
                # Try to get record count
                try:
                    records = self.table.all(max_records=1)
                    # Note: This doesn't give actual count, just tests if we can fetch
                    info['can_read_records'] = True
                except Exception:
                    info['can_read_records'] = False
            
            return info
            
        except Exception as e:
            return {
                'api_configured': False,
                'table_initialized': False,
                'connection_test': False,
                'error': str(e)
            }


def create_airtable_writer(
    api_key: Optional[str] = None,
    base_id: Optional[str] = None,
    table_name: Optional[str] = None
) -> AirtableWriter:
    """
    Factory function to create an AirtableWriter instance.
    
    Args:
        api_key: Optional API key (will use environment variable if not provided)
        base_id: Optional base ID (will use environment variable if not provided)
        table_name: Optional table name (will use environment variable if not provided)
        
    Returns:
        AirtableWriter: Configured writer instance
    """
    return AirtableWriter(api_key=api_key, base_id=base_id, table_name=table_name) 