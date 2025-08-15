"""
BigQuery Connector for Member Insights Processing

This module handles connections to BigQuery and data loading for processing
member insights using the eni_vectorizer__all table.
"""

import pandas as pd
import logging
import os
import yaml
from datetime import datetime, timezone
from google.cloud import bigquery
from google.auth.exceptions import DefaultCredentialsError
from typing import Optional, List, Dict, Any, Tuple

# Set up logging
logger = logging.getLogger(__name__)


class BigQueryConnector:
    """Handles BigQuery connections and data loading for member insights processing.
    
    This connector loads data from the eni_vectorizer__all table which contains
    member notes, affiliations, and preferences data for AI processing.
    It also manages processing logs in the eni_processing_log table.
    """
    
    def __init__(self, project_id: Optional[str] = None, dataset_id: Optional[str] = None, table_name: Optional[str] = None):
        """Initialize BigQuery connector.
        
        Args:
            project_id: Google Cloud project ID (uses PROJECT_ID env var if not provided)
            dataset_id: BigQuery dataset ID (uses BQ_DATASET env var if not provided) 
            table_name: BigQuery table name (defaults to eni_vectorizer__all)
        """
        self.project_id = project_id or os.getenv('PROJECT_ID') or os.getenv('GOOGLE_CLOUD_PROJECT_ID')
        self.dataset_id = dataset_id or os.getenv('BQ_DATASET')
        self.table_name = table_name or "eni_vectorizer__all"
        self.client = None
        
        # Processing log table configuration
        self.log_project_id = 'i-sales-analytics'
        self.log_dataset_id = 'elvis'
        self.log_table_name = 'eni_processing_log'
        self.log_table_ref = f"{self.log_project_id}.{self.log_dataset_id}.{self.log_table_name}"
        
        # Set up Google credentials if path is provided
        credentials_path = os.getenv('GOOGLE_CREDENTIALS_PATH') or os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if credentials_path:
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
            logger.info(f"Using Google credentials from: {credentials_path}")
    
    def connect(self) -> bool:
        """Establish connection to BigQuery.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            if not all([self.project_id, self.dataset_id, self.table_name]):
                missing = []
                if not self.project_id: missing.append("project_id")
                if not self.dataset_id: missing.append("dataset_id") 
                if not self.table_name: missing.append("table_name")
                raise ValueError(f"Missing required BigQuery configuration: {', '.join(missing)}")
            
            self.client = bigquery.Client(project=self.project_id)
            # Test connection with a simple query
            query = f"SELECT COUNT(*) as count FROM `{self.project_id}.{self.dataset_id}.{self.table_name}` LIMIT 1"
            self.client.query(query).result()
            logger.info(f"Successfully connected to BigQuery project: {self.project_id}")
            logger.info(f"Using dataset: {self.dataset_id}, table: {self.table_name}")
            return True
            
        except DefaultCredentialsError as e:
            logger.error(f"Google Cloud credentials not found: {str(e)}")
            logger.error("Set GOOGLE_APPLICATION_CREDENTIALS or GOOGLE_CREDENTIALS_PATH environment variable")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to BigQuery: {str(e)}")
            return False
    
    def _build_eni_filter_clause(self, eni_source_type: str, eni_source_subtype: Optional[str] = None) -> str:
        """
        Build SQL WHERE clause for a specific ENI type/subtype combination.
        
        Args:
            eni_source_type: The specific ENI source type to filter for
            eni_source_subtype: Optional ENI source subtype to filter for (None means no subtype filter)
            
        Returns:
            str: SQL WHERE clause for ENI filtering
        """
        if not eni_source_type:
            return ""
        
        # Always filter by eni_source_type
        filter_clause = f"AND eva.eni_source_type = '{eni_source_type}'"
        
        # Add subtype filter if specified
        if eni_source_subtype is not None:
            if eni_source_subtype == "null":
                filter_clause += " AND eva.eni_source_subtype IS NULL"
            else:
                filter_clause += f" AND eva.eni_source_subtype = '{eni_source_subtype}'"
        
        return filter_clause
    
    def load_contact_data_filtered(
        self, 
        contact_id: str, 
        eni_source_type: str,
        eni_source_subtype: Optional[str] = None
    ) -> pd.DataFrame:
        """Load data for a specific contact/eni_source_type/eni_source_subtype combination with SQL-based filtering.
        
        Args:
            contact_id: The contact ID to load data for
            eni_source_type: The specific ENI source type to filter for
            eni_source_subtype: Optional ENI source subtype to filter for
            
        Returns:
            pandas.DataFrame: Filtered contact data for the specific eni_source_type/subtype
        """
        if not self.client:
            raise ConnectionError("Not connected to BigQuery. Call connect() first.")
        
        try:
            # Build ENI filter clause for specific type/subtype
            eni_filter_clause = self._build_eni_filter_clause(eni_source_type, eni_source_subtype)
            
            # Base query with LEFT JOIN to exclude already processed records
            query = f"""
                SELECT eva.* 
                FROM `{self.project_id}.{self.dataset_id}.{self.table_name}` eva
                LEFT JOIN `{self.log_table_ref}` AS epl
                    ON epl.eni_id = eva.eni_id
                    AND epl.processing_status = 'completed'
                WHERE TRUE
                    AND epl.eni_id IS NULL
                    AND eva.contact_id = '{contact_id}'
                    AND eva.description IS NOT NULL
                    AND TRIM(eva.description) != ''
                    {eni_filter_clause}
                ORDER BY eva.logged_date DESC
            """
            
            subtype_desc = f"/{eni_source_subtype}" if eni_source_subtype else ""
            logger.info(f"Loading contact data for: {contact_id}, eni_source_type: {eni_source_type}{subtype_desc}")
            
            query_job = self.client.query(query)
            results = query_job.result()
            
            df = results.to_dataframe()
            logger.info(f"Loaded {len(df)} records for {contact_id}, {eni_source_type}{subtype_desc}")
            
            return df
            
        except Exception as e:
            logger.error(f"Error loading contact data for {contact_id}, {eni_source_type}: {str(e)}")
            raise
    

    
    def get_unique_contact_ids(self, limit: Optional[int] = None) -> List[str]:
        """Get list of unique contact IDs in the dataset.
        
        Args:
            limit: Maximum number of contact IDs to return
            
        Returns:
            List[str]: List of unique contact IDs
        """
        if not self.client:
            raise ConnectionError("Not connected to BigQuery. Call connect() first.")
        
        try:
            limit_clause = f"LIMIT {limit}" if limit else ""
            
            query = f"""
                SELECT DISTINCT contact_id, COUNT(*) as record_count
                FROM `{self.project_id}.{self.dataset_id}.{self.table_name}`
                WHERE contact_id IS NOT NULL 
                  AND description IS NOT NULL
                  AND TRIM(description) != ''
                GROUP BY contact_id
                ORDER BY record_count DESC
                {limit_clause}
            """
            
            logger.info("Fetching unique contact IDs")
            query_job = self.client.query(query)
            results = query_job.result()
            
            contact_ids = [row.contact_id for row in results]
            logger.info(f"Found {len(contact_ids)} unique contact IDs")
            
            return contact_ids
            
        except Exception as e:
            logger.error(f"Error fetching unique contact IDs: {str(e)}")
            raise
    
    def get_eni_combinations_for_processing(self, processing_rules: Dict[str, Any]) -> List[Tuple[str, Optional[str]]]:
        """
        Get list of (eni_source_type, eni_source_subtype) combinations to process based on processing rules.
        
        Always processes NULL subtypes first, then any explicitly defined subtypes.
        If no subtypes are defined in the rules, only NULL subtypes are processed.
        
        Args:
            processing_rules: Processing rules from processing_filters.yaml
            
        Returns:
            List[Tuple[str, Optional[str]]]: List of (eni_source_type, eni_source_subtype) combinations to process
        """
        combinations = []
        
        if not processing_rules:
            return combinations
        
        for eni_source_type, rule in processing_rules.items():
            if rule == "none" or rule is None:
                # Process only NULL subtypes when no explicit subtypes are defined
                combinations.append((eni_source_type, "null"))
                logger.debug(f"Adding NULL subtype for {eni_source_type} (no explicit subtypes defined)")
            elif isinstance(rule, list):
                # Always add NULL subtype first
                combinations.append((eni_source_type, "null"))
                
                # Then add specific eni_source_type/subtype combinations
                for subtype in rule:
                    if subtype != "null":  # Avoid duplicating null
                        combinations.append((eni_source_type, subtype))
                
                logger.debug(f"Adding NULL + {len(rule)} explicit subtypes for {eni_source_type}")
            else:
                # Invalid rule format - process only NULL subtypes as fallback
                combinations.append((eni_source_type, "null"))
                logger.warning(f"Invalid rule for {eni_source_type}: {rule}. Processing NULL subtypes only.")
        
        logger.info(f"Generated {len(combinations)} eni_source_type/subtype combinations for processing (NULL subtypes always included)")
        return combinations
    
    def get_eni_source_types_and_subtypes(self) -> pd.DataFrame:
        """
        Get all unique combinations of ENI source types and subtypes.
        
        Returns:
            pandas.DataFrame: DataFrame with eni_source_type and eni_source_subtype columns
        """
        if not self.client:
            raise ConnectionError("Not connected to BigQuery. Call connect() first.")
        
        try:
            query = f"""
                SELECT DISTINCT eni_source_type, eni_source_subtype, COUNT(*) as count
                FROM `{self.project_id}.{self.dataset_id}.{self.table_name}`
                WHERE eni_source_type IS NOT NULL
                GROUP BY eni_source_type, eni_source_subtype
                ORDER BY eni_source_type, eni_source_subtype
            """
            
            logger.info("Fetching ENI source types and subtypes")
            query_job = self.client.query(query)
            results = query_job.result()
            
            df = results.to_dataframe()
            logger.info(f"Found {len(df)} unique ENI source type/subtype combinations")
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching ENI source types and subtypes: {str(e)}")
            raise
    
    # Processing Log Methods (from big_query_processing_manager.py)
    
    def get_processed_eni_ids(self, contact_id: str) -> List[str]:
        """
        Get list of already processed ENI IDs for a contact from BigQuery processing log.
        
        Args:
            contact_id: Contact ID to check
            
        Returns:
            List[str]: List of processed ENI IDs
        """
        if not self.client:
            if not self.connect():
                logger.warning("Failed to connect to BigQuery - returning empty processed list")
                return []
        
        try:
            query = f"""
                SELECT DISTINCT eni_id
                FROM `{self.log_table_ref}`
                WHERE contact_id = '{contact_id}'
                  AND processing_status IN ('completed', 'skipped')
                ORDER BY eni_id
            """
            
            query_job = self.client.query(query)
            results = query_job.result()
            
            processed_eni_ids = [row.eni_id for row in results]
            logger.debug(f"Found {len(processed_eni_ids)} processed ENI IDs for contact {contact_id}")
            
            return processed_eni_ids
            
        except Exception as e:
            logger.error(f"Error getting processed ENI IDs for {contact_id}: {str(e)}")
            # Return empty list on error to avoid blocking processing
            return []
    
    def mark_eni_processed(
        self,
        eni_id: str,
        contact_id: str,
        processing_status: str = 'completed',
        processor_version: str = '1.0.0',
        processing_duration_ms: Optional[int] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Mark a single ENI record as processed in BigQuery processing log.
        
        Args:
            eni_id: ENI ID that was processed
            contact_id: Contact ID the ENI belongs to
            processing_status: Status ('completed', 'failed', 'skipped')
            processor_version: Version of the processor that handled this record
            processing_duration_ms: Processing time in milliseconds
            error_message: Error message if processing failed
            metadata: Additional metadata as JSON
            
        Returns:
            bool: True if successful
        """
        if not self.client:
            if not self.connect():
                logger.error("Failed to connect to BigQuery - cannot mark ENI as processed")
                return False
        
        try:
            # Prepare the record
            processed_at = datetime.now(timezone.utc).isoformat()
            
            # Extract metadata fields
            batch_id = metadata.get('batch_id') if metadata and isinstance(metadata, dict) else None
            processing_mode = 'batch' if batch_id else 'single'
            
            # Build the INSERT query
            error_msg_value = f"'{error_message}'" if error_message else 'NULL'
            duration_value = processing_duration_ms if processing_duration_ms is not None else 'NULL'
            batch_id_value = f"'{batch_id}'" if batch_id else 'NULL'
            
            query = f"""
                INSERT INTO `{self.log_table_ref}` 
                (eni_id, contact_id, processed_at, processing_status, processor_version, 
                 processing_duration_ms, error_message, batch_id, processing_mode, processing_environment)
                VALUES 
                ('{eni_id}', '{contact_id}', '{processed_at}', '{processing_status}', 
                 '{processor_version}', {duration_value}, {error_msg_value}, {batch_id_value}, 
                 '{processing_mode}', 'production')
            """
            
            query_job = self.client.query(query)
            query_job.result()  # Wait for completion
            
            logger.debug(f"Marked ENI {eni_id} as {processing_status} for contact {contact_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error marking ENI {eni_id} as processed: {str(e)}")
            return False
    
    def batch_mark_processed(
        self,
        records: List[Dict[str, Any]]
    ) -> Tuple[int, int]:
        """
        Mark multiple ENI records as processed in a single batch operation.
        
        Args:
            records: List of record dictionaries with keys:
                    - eni_id, contact_id, processing_status, processor_version,
                      processing_duration_ms (optional), error_message (optional),
                      metadata (optional)
                      
        Returns:
            Tuple[int, int]: (successful_count, failed_count)
        """
        if not self.client:
            if not self.connect():
                logger.error("Failed to connect to BigQuery - cannot batch mark as processed")
                return 0, len(records)
        
        if not records:
            return 0, 0
        
        try:
            # Prepare batch insert data
            rows_to_insert = []
            processed_at = datetime.now(timezone.utc).isoformat()
            
            for record in records:
                # Extract metadata fields and map to proper columns
                metadata = record.get('metadata', {})
                
                row = {
                    'eni_id': record['eni_id'],
                    'contact_id': record['contact_id'],
                    'processed_at': processed_at,
                    'processing_status': record.get('processing_status', 'completed'),
                    'processor_version': record.get('processor_version', '1.0.0'),
                    'processing_duration_ms': record.get('processing_duration_ms'),
                    'error_message': record.get('error_message'),
                    'batch_id': metadata.get('batch_id') if isinstance(metadata, dict) else None,
                    'processing_mode': 'batch' if isinstance(metadata, dict) and metadata.get('batch_id') else 'single',
                    'processing_environment': 'production'
                }
                rows_to_insert.append(row)
            
            # Get table reference and insert
            table = self.client.get_table(self.log_table_ref)
            errors = self.client.insert_rows_json(table, rows_to_insert)
            
            if errors:
                logger.error(f"Batch insert errors: {errors}")
                return 0, len(records)
            
            logger.info(f"Successfully batch marked {len(records)} ENI records as processed")
            return len(records), 0
            
        except Exception as e:
            logger.error(f"Error in batch mark processed: {str(e)}")
            return 0, len(records)
    
    def get_processing_statistics(self, contact_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get processing statistics from the log table.
        
        Args:
            contact_id: Optional contact ID to filter statistics
            
        Returns:
            Dict[str, Any]: Processing statistics
        """
        if not self.client:
            if not self.connect():
                return {'error': 'Failed to connect to BigQuery'}
        
        try:
            where_clause = f"WHERE contact_id = '{contact_id}'" if contact_id else ""
            
            query = f"""
                SELECT 
                    processing_status,
                    COUNT(*) as count,
                    AVG(processing_duration_ms) as avg_duration_ms,
                    MIN(processed_at) as earliest_processed,
                    MAX(processed_at) as latest_processed
                FROM `{self.log_table_ref}`
                {where_clause}
                GROUP BY processing_status
                ORDER BY processing_status
            """
            
            query_job = self.client.query(query)
            results = query_job.result()
            
            stats = {
                'by_status': {},
                'total_processed': 0,
                'contact_filter': contact_id
            }
            
            for row in results:
                stats['by_status'][row.processing_status] = {
                    'count': row.count,
                    'avg_duration_ms': float(row.avg_duration_ms) if row.avg_duration_ms else None,
                    'earliest_processed': row.earliest_processed.isoformat() if row.earliest_processed else None,
                    'latest_processed': row.latest_processed.isoformat() if row.latest_processed else None
                }
                stats['total_processed'] += row.count
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting processing statistics: {str(e)}")
            return {'error': str(e)}


def create_bigquery_connector(config: dict = None) -> BigQueryConnector:
    """
    Factory function to create a BigQuery connector from configuration.
    
    Args:
        config: Configuration dictionary with BigQuery settings
        
    Returns:
        BigQueryConnector: Configured BigQuery connector instance
    """
    if config is None:
        # Use environment variables and defaults
        return BigQueryConnector()
    
    bigquery_config = config.get('bigquery', {})
    project_id = bigquery_config.get('project_id')
    dataset_id = bigquery_config.get('dataset_id')
    table_name = bigquery_config.get('table_name')
    
    if not all([project_id, dataset_id, table_name]):
        raise ValueError("Missing required BigQuery configuration: project_id, dataset_id, table_name")
    
    return BigQueryConnector(project_id, dataset_id, table_name) 