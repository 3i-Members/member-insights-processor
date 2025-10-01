"""
Enhanced Airtable Writer Module

This module provides advanced functionality for syncing member insights data
to Airtable with batch processing, rate limiting, and robust error handling.
"""

import os
import time
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass
import logging

try:
    from pyairtable import Table
    from pyairtable.api.types import CreateRecordDict, UpdateRecordDict
    PYAIRTABLE_AVAILABLE = True
except ImportError:
    PYAIRTABLE_AVAILABLE = False
    Table = None

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Result of a sync operation."""
    success: bool
    record_id: Optional[str] = None
    contact_id: Optional[str] = None
    error: Optional[str] = None
    created: bool = False
    updated: bool = False


@dataclass
class BatchSyncResult:
    """Result of a batch sync operation."""
    total_records: int
    successful: int
    failed: int
    errors: List[str]
    created_records: List[str]
    updated_records: List[str]
    processing_time: float
    start_time: str
    end_time: str


class MemberInsightsAirtableWriter:
    """
    Enhanced Airtable writer specifically designed for member insights data.
    
    Features:
    - Batch processing with rate limiting
    - Robust error handling and retry logic
    - Progress tracking for large operations
    - Member insights specific templates
    - Data validation and sanitization
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_id: Optional[str] = None,
        table_id: Optional[str] = None,
        rate_limit_delay: float = 0.2,  # 5 requests per second
        max_retries: int = 3
    ):
        """
        Initialize the enhanced Airtable writer.

        Args:
            api_key: Airtable API key
            base_id: Airtable base ID
            table_id: Airtable table ID
            rate_limit_delay: Delay between requests (seconds)
            max_retries: Maximum retry attempts for failed requests
        """
        if not PYAIRTABLE_AVAILABLE:
            logger.error("pyairtable library not available. Install with: pip install pyairtable")
            self.table = None
            self.connected = False
            return
        
        self.api_key = api_key or os.getenv('AIRTABLE_API_KEY')
        self.base_id = base_id or os.getenv('AIRTABLE_BASE_ID')
        self.table_id = table_id or os.getenv('AIRTABLE_TABLE_ID')
        self.rate_limit_delay = rate_limit_delay
        self.max_retries = max_retries
        
        self.table = None
        self.connected = False
        self.last_request_time = 0
        
        # Initialize connection
        self._initialize_connection()
    
    def _initialize_connection(self) -> bool:
        """Initialize the Airtable connection."""
        try:
            if not all([self.api_key, self.base_id, self.table_id]):
                missing = []
                if not self.api_key: missing.append("API key")
                if not self.base_id: missing.append("base ID")
                if not self.table_id: missing.append("table ID")

                logger.error(f"Missing Airtable configuration: {', '.join(missing)}")
                return False

            self.table = Table(self.api_key, self.base_id, self.table_id)
            self.connected = True
            logger.info(f"Successfully connected to Airtable table: {self.table_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Airtable connection: {str(e)}")
            self.connected = False
            return False
    
    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last)
        self.last_request_time = time.time()
    
    def test_connection(self) -> Dict[str, Any]:
        """Test the Airtable connection and return status."""
        result = {
            'connected': False,
            'table_accessible': False,
            'record_count': None,
            'error': None
        }
        
        if not self.connected:
            result['error'] = "Not connected to Airtable"
            return result
        
        try:
            # Try to fetch a single record to test access
            records = self.table.all(max_records=1)
            result['connected'] = True
            result['table_accessible'] = True
            result['record_count'] = len(records)
            logger.info("Airtable connection test successful")
            
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Airtable connection test failed: {str(e)}")
        
        return result
    
    def validate_record_data(self, record_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate record data before sending to Airtable.
        
        Args:
            record_data: Data to validate
            
        Returns:
            Tuple[bool, List[str]]: (is_valid, error_messages)
        """
        errors = []
        
        # Check for required fields
        required_fields = ['Contact ID']
        for field in required_fields:
            if field not in record_data or not record_data[field]:
                errors.append(f"Missing required field: {field}")
        
        # Validate field types and lengths
        for field_name, value in record_data.items():
            if value is None:
                continue
                
            # String length validation (Airtable has limits)
            if isinstance(value, str) and len(value) > 100000:  # 100KB limit
                errors.append(f"Field '{field_name}' exceeds maximum length")
            
            # Validate specific field formats
            if field_name == 'Contact ID' and isinstance(value, str):
                if not value.startswith('CNT-'):
                    errors.append(f"Invalid Contact ID format: {value}")
        
        return len(errors) == 0, errors
    
    def create_member_insights_record(
        self,
        contact_id: str,
        member_name: str,
        insights_content: str,
        eni_source_type: str,
        eni_source_subtype: str,
        eni_id: str,
        record_count: int = 1,
        additional_fields: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a properly formatted member insights record.
        
        Args:
            contact_id: Contact ID
            member_name: Member name
            insights_content: AI-generated insights
            eni_source_type: ENI source type
            eni_source_subtype: ENI source subtype  
            eni_id: ENI ID
            record_count: Number of source records processed
            additional_fields: Additional fields to include
            
        Returns:
            Dict[str, Any]: Formatted record ready for Airtable
        """
        record = {
            'Contact ID': contact_id,
            'Member Name': member_name,
            'AI Insights': insights_content,
            'ENI Source Type': eni_source_type,
            'ENI Source Subtype': eni_source_subtype,
            'ENI ID': eni_id,
            'Source Record Count': record_count,
            'Generated At': datetime.now().isoformat(),
            'Last Updated': datetime.now().isoformat(),
            'Processing Status': 'Completed'
        }
        
        # Add additional fields
        if additional_fields:
            record.update(additional_fields)
        
        return record
    
    def find_existing_record_by_contact_and_eni(
        self,
        contact_id: str,
        eni_id: str
    ) -> Optional[Dict[str, Any]]:
        """Find existing record by contact ID and ENI ID."""
        if not self.connected:
            return None
        
        try:
            self._rate_limit()
            
            # Search for existing record
            formula = f"AND({{Contact ID}} = '{contact_id}', {{ENI ID}} = '{eni_id}')"
            records = self.table.all(formula=formula)
            
            return records[0] if records else None
            
        except Exception as e:
            logger.error(f"Error finding existing record: {str(e)}")
            return None
    
    def sync_single_record(
        self,
        record_data: Dict[str, Any],
        update_existing: bool = True
    ) -> SyncResult:
        """
        Sync a single record to Airtable.
        
        Args:
            record_data: Record data to sync
            update_existing: Whether to update existing records
            
        Returns:
            SyncResult: Result of the sync operation
        """
        if not self.connected:
            return SyncResult(
                success=False,
                contact_id=record_data.get('Contact ID'),
                error="Not connected to Airtable"
            )
        
        # Validate record data
        is_valid, errors = self.validate_record_data(record_data)
        if not is_valid:
            return SyncResult(
                success=False,
                contact_id=record_data.get('Contact ID'),
                error=f"Validation failed: {', '.join(errors)}"
            )
        
        contact_id = record_data.get('Contact ID')
        eni_id = record_data.get('ENI ID')
        
        # Try to find existing record
        existing_record = None
        if contact_id and eni_id and update_existing:
            existing_record = self.find_existing_record_by_contact_and_eni(contact_id, eni_id)
        
        # Retry logic
        for attempt in range(self.max_retries):
            try:
                self._rate_limit()
                
                if existing_record:
                    # Update existing record
                    updated_record = self.table.update(existing_record['id'], record_data)
                    return SyncResult(
                        success=True,
                        record_id=updated_record['id'],
                        contact_id=contact_id,
                        updated=True
                    )
                else:
                    # Create new record
                    created_record = self.table.create(record_data)
                    return SyncResult(
                        success=True,
                        record_id=created_record['id'],
                        contact_id=contact_id,
                        created=True
                    )
                    
            except Exception as e:
                if attempt == self.max_retries - 1:  # Last attempt
                    return SyncResult(
                        success=False,
                        contact_id=contact_id,
                        error=f"Failed after {self.max_retries} attempts: {str(e)}"
                    )
                else:
                    logger.warning(f"Attempt {attempt + 1} failed for {contact_id}: {str(e)}")
                    time.sleep(2 ** attempt)  # Exponential backoff
    
    def sync_batch_records(
        self,
        records: List[Dict[str, Any]],
        update_existing: bool = True,
        show_progress: bool = True
    ) -> BatchSyncResult:
        """
        Sync multiple records to Airtable with progress tracking.
        
        Args:
            records: List of record data to sync
            update_existing: Whether to update existing records
            show_progress: Whether to show progress updates
            
        Returns:
            BatchSyncResult: Result of the batch operation
        """
        start_time = datetime.now()
        start_time_str = start_time.isoformat()
        
        result = BatchSyncResult(
            total_records=len(records),
            successful=0,
            failed=0,
            errors=[],
            created_records=[],
            updated_records=[],
            processing_time=0.0,
            start_time=start_time_str,
            end_time=""
        )
        
        if not self.connected:
            result.errors.append("Not connected to Airtable")
            result.end_time = datetime.now().isoformat()
            return result
        
        logger.info(f"Starting batch sync of {len(records)} records")
        
        for i, record_data in enumerate(records, 1):
            if show_progress and i % 10 == 0:
                logger.info(f"Processing record {i}/{len(records)}")
            
            sync_result = self.sync_single_record(record_data, update_existing)
            
            if sync_result.success:
                result.successful += 1
                if sync_result.created:
                    result.created_records.append(sync_result.record_id)
                elif sync_result.updated:
                    result.updated_records.append(sync_result.record_id)
            else:
                result.failed += 1
                error_msg = f"Record {sync_result.contact_id}: {sync_result.error}"
                result.errors.append(error_msg)
                logger.error(error_msg)
        
        end_time = datetime.now()
        result.end_time = end_time.isoformat()
        result.processing_time = (end_time - start_time).total_seconds()
        
        logger.info(f"Batch sync completed: {result.successful} successful, {result.failed} failed")
        return result
    
    def sync_member_insights_from_processor_results(
        self,
        processor_results: Dict[str, Any],
        show_progress: bool = True
    ) -> BatchSyncResult:
        """
        Sync results from the member insights processor to Airtable.
        
        Args:
            processor_results: Results from process_multiple_contacts
            show_progress: Whether to show progress updates
            
        Returns:
            BatchSyncResult: Result of the sync operation
        """
        records_to_sync = []
        
        # Extract successful processing results
        for contact_id, contact_result in processor_results.get('contact_results', {}).items():
            if not contact_result.get('success', False):
                continue
            
            # Create records for each processed ENI ID
            for eni_id in contact_result.get('processed_eni_ids', []):
                # Try to find corresponding file or use basic data
                insights_content = f"AI insights generated for contact {contact_id}, ENI {eni_id}"
                
                # Extract member name from files if available
                member_name = "Unknown Member"  # Could be enhanced to extract from data
                
                record = self.create_member_insights_record(
                    contact_id=contact_id,
                    member_name=member_name,
                    insights_content=insights_content,
                    eni_source_type="mixed",  # Could be enhanced to be more specific
                    eni_source_subtype="processed",
                    eni_id=eni_id,
                    additional_fields={
                        'Processing Date': processor_results.get('start_time'),
                        'Files Created': len(contact_result.get('files_created', [])),
                        'Processing Method': 'Batch Processing'
                    }
                )
                
                records_to_sync.append(record)
        
        if not records_to_sync:
            logger.warning("No successful processing results to sync")
            return BatchSyncResult(
                total_records=0,
                successful=0,
                failed=0,
                errors=["No data to sync"],
                created_records=[],
                updated_records=[],
                processing_time=0.0,
                start_time=datetime.now().isoformat(),
                end_time=datetime.now().isoformat()
            )
        
        return self.sync_batch_records(records_to_sync, show_progress=show_progress)
    
    def get_table_info(self) -> Dict[str, Any]:
        """Get information about the Airtable table."""
        info = {
            'connected': self.connected,
            'api_configured': bool(self.api_key),
            'base_id': self.base_id,
            'table_id': self.table_id,
            'table_initialized': self.table is not None,
            'connection_test': False,
            'record_count': None
        }

        if self.connected:
            test_result = self.test_connection()
            # Map test_connection result to connection_test
            info['connection_test'] = test_result.get('connected', False) and test_result.get('table_accessible', False)
            info['record_count'] = test_result.get('record_count')
            if test_result.get('error'):
                info['error'] = test_result['error']

        return info
    
    def export_sync_report(
        self,
        batch_result: BatchSyncResult,
        output_file: Optional[str] = None
    ) -> str:
        """
        Export a detailed sync report.
        
        Args:
            batch_result: Result of batch sync operation
            output_file: Optional file path to save report
            
        Returns:
            str: Path to the saved report file
        """
        report = {
            'summary': {
                'total_records': batch_result.total_records,
                'successful': batch_result.successful,
                'failed': batch_result.failed,
                'success_rate': f"{(batch_result.successful / batch_result.total_records * 100):.1f}%" if batch_result.total_records > 0 else "0%",
                'processing_time': f"{batch_result.processing_time:.2f} seconds"
            },
            'details': {
                'start_time': batch_result.start_time,
                'end_time': batch_result.end_time,
                'created_records': batch_result.created_records,
                'updated_records': batch_result.updated_records,
                'errors': batch_result.errors
            },
            'airtable_info': {
                'base_id': self.base_id,
                'table_id': self.table_id,
                'connected': self.connected
            }
        }
        
        # Generate filename if not provided
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"logs/airtable_sync_report_{timestamp}.json"
        
        # Ensure directory exists
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        
        # Save report
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Sync report saved to: {output_file}")
        return output_file


def create_enhanced_airtable_writer(
    api_key: Optional[str] = None,
    base_id: Optional[str] = None,
    table_id: Optional[str] = None
) -> MemberInsightsAirtableWriter:
    """
    Factory function to create an enhanced Airtable writer.
    
    Args:
        api_key: Airtable API key
        base_id: Airtable base ID
        table_id: Airtable table ID

    Returns:
        MemberInsightsAirtableWriter: Configured Airtable writer
    """
    return MemberInsightsAirtableWriter(
        api_key=api_key,
        base_id=base_id,
        table_id=table_id
    ) 