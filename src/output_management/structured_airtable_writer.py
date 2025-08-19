"""
Structured Insights Airtable Writer

This module handles syncing structured insight JSON data to Airtable with 
specific field mapping and contact ID lookup functionality.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

try:
    from pyairtable import Table
    PYAIRTABLE_AVAILABLE = True
except ImportError:
    PYAIRTABLE_AVAILABLE = False
    Table = None

logger = logging.getLogger(__name__)


@dataclass
class StructuredSyncResult:
    """Result of a structured insight sync operation."""
    success: bool
    record_id: Optional[str] = None
    contact_id: Optional[str] = None
    master_record_id: Optional[str] = None
    error: Optional[str] = None
    created: bool = False
    updated: bool = False


class StructuredInsightsAirtableWriter:
    """
    Specialized Airtable writer for structured insights JSON data.
    
    Features:
    - Contact ID lookup and linking
    - JSON to specific field mapping
    - Content concatenation for note_content field
    - Master record relationship management
    """
    
    def __init__(
        self,
        config: Dict[str, Any],
        api_key: Optional[str] = None
    ):
        """
        Initialize the structured insights Airtable writer.
        
        Args:
            config: Airtable configuration from config.yaml
            api_key: Airtable API key (if None, will get from environment)
        """
        if not PYAIRTABLE_AVAILABLE:
            logger.error("pyairtable library not available. Install with: pip install pyairtable")
            self.connected = False
            return
        
        self.api_key = api_key or os.getenv('AIRTABLE_API_KEY')
        self.config = config
        self.connected = False
        
        # Initialize tables
        self.note_submission_table = None
        self.master_table = None
        
        # Cache for contact ID lookups
        self._contact_cache = {}
        
        self._initialize_connection()
    
    def _initialize_connection(self) -> bool:
        """Initialize connections to Airtable tables."""
        try:
            if not self.api_key:
                logger.error("Missing Airtable API key")
                return False
            
            base_id = self.config['structured_insight']['base_id']
            
            # Initialize note submission table
            note_table_id = self.config['structured_insight']['tables']['note_submission']['table_id']
            self.note_submission_table = Table(self.api_key, base_id, note_table_id)
            
            # Initialize master table
            master_table_id = self.config['structured_insight']['tables']['master']['table_id']
            self.master_table = Table(self.api_key, base_id, master_table_id)
            
            self.connected = True
            logger.info("Successfully connected to structured insights Airtable tables")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Airtable connection: {str(e)}")
            self.connected = False
            return False
    
    def _get_airtable_record_id(self, table: Table, field_id: str, value: str) -> Optional[str]:
        """
        Generic function to find an Airtable record ID by a field value.
        Based on the shared logic from the other codebase.
        
        Args:
            table: Airtable table instance
            field_id: Field ID to search in
            value: Value to search for
            
        Returns:
            Optional[str]: Record ID if found, None otherwise
        """
        try:
            formula = f"{{{field_id}}} = '{value}'"
            record = table.first(formula=formula)
            if record:
                logger.info(f"Found existing record in table {table.name} where {field_id} = {value}. Record ID: {record['id']}")
                return record['id']
            logger.info(f"No record found in table {table.name} for value: {value}")
            return None
        except Exception as e:
            logger.error(f"Error looking up Airtable record ID for value {value} in table {table.name}: {e}")
            return None
    
    def find_master_record_by_contact_id(self, contact_id: str) -> Optional[str]:
        """
        Find the master record ID by contact ID.
        
        Args:
            contact_id: Contact ID to search for
            
        Returns:
            Optional[str]: Master record ID if found
        """
        # Check cache first
        if contact_id in self._contact_cache:
            return self._contact_cache[contact_id]
        
        # Get field ID for contact_id lookup
        contact_field_id = self.config['structured_insight']['tables']['master']['fields']['contact_id']
        
        # Find the record
        master_record_id = self._get_airtable_record_id(
            self.master_table, 
            contact_field_id, 
            contact_id
        )
        
        # Cache the result
        if master_record_id:
            self._contact_cache[contact_id] = master_record_id
        
        return master_record_id
    
    def process_structured_json(self, json_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Process structured JSON data into Airtable-ready format.
        
        Args:
            json_data: Structured insight JSON data
            
        Returns:
            Dict[str, str]: Processed data ready for Airtable
        """
        processed_data = {}
        
        # Concatenate personal, business, investing, and 3i for note_content
        note_content_parts = []
        for section in ['personal', 'business', 'investing', '3i']:
            if section in json_data and json_data[section]:
                formatted_content = self._format_markdown_for_airtable(json_data[section])
                note_content_parts.append(f"**{section.title()}:**\n{formatted_content}")
        
        processed_data['note_content'] = "\n\n".join(note_content_parts)
        
        # Map deals and introductions directly (also format them)
        if 'deals' in json_data and json_data['deals']:
            processed_data['deals'] = self._format_markdown_for_airtable(json_data['deals'])
        
        if 'introductions' in json_data and json_data['introductions']:
            processed_data['introductions'] = self._format_markdown_for_airtable(json_data['introductions'])
        
        return processed_data
    
    def _format_markdown_for_airtable(self, content: str) -> str:
        """
        Format markdown content for better display in Airtable.
        Converts markdown sub-bullets to proper indentation.
        
        Args:
            content: Markdown content with potential sub-bullets
            
        Returns:
            str: Formatted content for Airtable
        """
        if not content:
            return content
        
        lines = content.split('\n')
        formatted_lines = []
        
        for line in lines:
            # Check for citation sub-bullets with exact 2-space indentation
            if line.startswith('  * ['):
                # This is a citation sub-bullet, format with proper indentation
                citation_text = line[4:]  # Remove '  * '
                formatted_lines.append(f"    {citation_text}")
            elif line.startswith('  *') and not line.startswith('  * ['):
                # Regular sub-bullet, add indentation
                sub_bullet_text = line[4:]  # Remove '  * '
                formatted_lines.append(f"    • {sub_bullet_text}")
            else:
                # Keep regular lines as-is
                formatted_lines.append(line)
        
        return '\n'.join(formatted_lines)
    
    def create_note_submission_record(
        self,
        contact_id: str,
        structured_json: Dict[str, Any],
        member_name: Optional[str] = None
    ) -> StructuredSyncResult:
        """
        Create a note submission record with structured insight data.
        
        Args:
            contact_id: Contact ID to link to
            structured_json: Structured insight JSON data
            member_name: Optional member name for logging
            
        Returns:
            StructuredSyncResult: Result of the sync operation
        """
        if not self.connected:
            return StructuredSyncResult(
                success=False,
                contact_id=contact_id,
                error="Not connected to Airtable"
            )
        
        try:
            # Find master record
            master_record_id = self.find_master_record_by_contact_id(contact_id)
            if not master_record_id:
                return StructuredSyncResult(
                    success=False,
                    contact_id=contact_id,
                    error=f"No master record found for contact ID: {contact_id}"
                )
            
            # Process the JSON data
            processed_data = self.process_structured_json(structured_json)
            
            # Get field mappings
            fields = self.config['structured_insight']['tables']['note_submission']['fields']
            
            # Build the record data
            record_data = {
                fields['find_by_contact_lookup']: [master_record_id],  # Link to master record
                fields['note_submission_type']: self.config['structured_insight']['tables']['note_submission']['status_column_value']['elvis']
            }
            
            # Add processed content
            if 'note_content' in processed_data:
                record_data[fields['note_content']] = processed_data['note_content']
            
            if 'deals' in processed_data:
                record_data[fields['deals']] = processed_data['deals']
            
            if 'introductions' in processed_data:
                record_data[fields['introductions']] = processed_data['introductions']
            
            # Create the record
            created_record = self.note_submission_table.create(record_data)
            logger.info(
                f"Airtable note_submission create success for {contact_id} ({member_name}): record_id={created_record['id']} master_id={master_record_id}"
            )
            
            return StructuredSyncResult(
                success=True,
                record_id=created_record['id'],
                contact_id=contact_id,
                master_record_id=master_record_id,
                created=True
            )
            
        except Exception as e:
            error_msg = f"Failed to create note submission record for {contact_id}: {str(e)}"
            logger.error(error_msg)
            return StructuredSyncResult(
                success=False,
                contact_id=contact_id,
                error=error_msg
            )
    
    def sync_structured_insights_batch(
        self,
        insights_data: List[Dict[str, Any]],
        show_progress: bool = True
    ) -> Dict[str, Any]:
        """
        Sync multiple structured insights to Airtable.
        
        Args:
            insights_data: List of insight data with contact_id and json_data
            show_progress: Whether to show progress updates
            
        Returns:
            Dict[str, Any]: Batch sync results
        """
        results = {
            'total_records': len(insights_data),
            'successful': 0,
            'failed': 0,
            'errors': [],
            'created_records': [],
            'start_time': datetime.now().isoformat()
        }
        
        if not self.connected:
            results['errors'].append("Not connected to Airtable")
            results['end_time'] = datetime.now().isoformat()
            return results
        
        logger.info(f"Starting batch sync of {len(insights_data)} structured insights")
        
        for i, insight_data in enumerate(insights_data, 1):
            if show_progress and i % 5 == 0:
                logger.info(f"Processing insight {i}/{len(insights_data)}")
            
            contact_id = insight_data.get('contact_id')
            json_data = insight_data.get('json_data', {})
            member_name = insight_data.get('member_name', 'Unknown')
            
            if not contact_id:
                error_msg = f"Missing contact_id in insight data #{i}"
                results['errors'].append(error_msg)
                results['failed'] += 1
                continue
            
            sync_result = self.create_note_submission_record(
                contact_id=contact_id,
                structured_json=json_data,
                member_name=member_name
            )
            
            if sync_result.success:
                results['successful'] += 1
                results['created_records'].append(sync_result.record_id)
            else:
                results['failed'] += 1
                results['errors'].append(f"Contact {contact_id}: {sync_result.error}")
        
        results['end_time'] = datetime.now().isoformat()
        logger.info(f"Batch sync completed: {results['successful']} successful, {results['failed']} failed")
        
        return results
    
    def test_connection(self) -> Dict[str, Any]:
        """Test the Airtable connection and return status."""
        result = {
            'connected': self.connected,
            'note_submission_table': False,
            'master_table': False,
            'api_configured': bool(self.api_key),
            'error': None
        }
        
        if not self.connected:
            result['error'] = "Not connected to Airtable"
            return result
        
        try:
            # Test note submission table
            if self.note_submission_table:
                self.note_submission_table.all(max_records=1)
                result['note_submission_table'] = True
            
            # Test master table
            if self.master_table:
                self.master_table.all(max_records=1)
                result['master_table'] = True
            
            logger.info("Structured insights Airtable connection test successful")
            
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Structured insights Airtable connection test failed: {str(e)}")
        
        return result


def create_structured_airtable_writer(
    config: Dict[str, Any],
    api_key: Optional[str] = None
) -> StructuredInsightsAirtableWriter:
    """
    Factory function to create a structured insights Airtable writer.
    
    Args:
        config: Airtable configuration
        api_key: Airtable API key
        
    Returns:
        StructuredInsightsAirtableWriter: Configured writer
    """
    return StructuredInsightsAirtableWriter(config=config, api_key=api_key) 