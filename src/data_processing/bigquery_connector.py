"""
BigQuery Connector for Member Insights Processing

This module handles connections to BigQuery and data loading for processing
member insights using the eni_vectorizer__all table.
"""

import pandas as pd
import logging
import os
from google.cloud import bigquery
from google.auth.exceptions import DefaultCredentialsError
from typing import Optional, List, Dict, Any

# Set up logging
logger = logging.getLogger(__name__)


class BigQueryConnector:
    """Handles BigQuery connections and data loading for member insights processing.
    
    This connector loads data from the eni_vectorizer__all table which contains
    member notes, affiliations, and preferences data for AI processing.
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
    
    def load_contact_data(self, contact_id: str, processed_eni_ids: Optional[List[str]] = None) -> pd.DataFrame:
        """Load data for a specific contact ID, optionally filtering out processed ENI IDs.
        
        Args:
            contact_id: The contact ID to load data for
            processed_eni_ids: List of ENI IDs that have already been processed (will be excluded)
            
        Returns:
            pandas.DataFrame: Contact data with columns including eni_source_type, eni_source_subtype, description, etc.
        """
        if not self.client:
            raise ConnectionError("Not connected to BigQuery. Call connect() first.")
        
        try:
            # Build exclusion clause for processed ENI IDs
            exclusion_clause = ""
            if processed_eni_ids:
                eni_id_list = "', '".join(processed_eni_ids)
                exclusion_clause = f"AND eni_id NOT IN ('{eni_id_list}')"
            
            query = f"""
                SELECT 
                    eni_source_type,
                    eni_source_subtype,
                    contact_id,
                    member_name,
                    description,
                    logged_date,
                    eni_id,
                    affiliation_id,
                    recurroo_id,
                    pd_deal_id,
                    pd_note_id,
                    at_deal_id,
                    at_deal_activity_id,
                    at_request_id,
                    at_request_activity_id,
                    at_note_id
                FROM `{self.project_id}.{self.dataset_id}.{self.table_name}`
                WHERE contact_id = '{contact_id}'
                  AND description IS NOT NULL
                  AND TRIM(description) != ''
                  {exclusion_clause}
                ORDER BY logged_date DESC
            """
            
            logger.info(f"Loading contact data for: {contact_id}")
            if processed_eni_ids:
                logger.info(f"Excluding {len(processed_eni_ids)} already processed ENI IDs")
            
            query_job = self.client.query(query)
            results = query_job.result()
            
            df = results.to_dataframe()
            logger.info(f"Loaded {len(df)} records for contact {contact_id}")
            
            return df
            
        except Exception as e:
            logger.error(f"Error loading contact data for {contact_id}: {str(e)}")
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