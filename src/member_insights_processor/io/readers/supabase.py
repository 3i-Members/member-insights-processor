"""
Supabase Client for Structured Insights.

This module provides a comprehensive client for interacting with Supabase
to store, retrieve, and manage structured member insights.
"""

import os
import time
import asyncio
from typing import Any, Dict, List, Optional, Union, Tuple
from contextlib import contextmanager
from datetime import datetime, timedelta
import logging
from functools import wraps

from supabase import create_client, Client
from postgrest.exceptions import APIError
import json
from utils.token_utils import estimate_tokens

from .schema import (
    StructuredInsight,
    InsightMetadata,
    StructuredInsightContent,
    ProcessingStatus,
    is_valid_contact_id,
    normalize_insight_data
)

logger = logging.getLogger(__name__)


class SupabaseConnectionError(Exception):
    """Raised when Supabase connection fails."""
    pass


class SupabaseOperationError(Exception):
    """Raised when Supabase operation fails."""
    pass


def retry_on_failure(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Decorator to retry failed operations with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (APIError, SupabaseOperationError, ConnectionError) as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = delay * (backoff ** attempt)
                        logger.warning(f"Operation failed (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s: {str(e)}")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"Operation failed after {max_retries} attempts: {str(e)}")
            
            raise SupabaseOperationError(f"Operation failed after {max_retries} attempts. Last error: {str(last_exception)}")
        return wrapper
    return decorator


class SupabaseInsightsClient:
    """
    Client for managing structured insights in Supabase.
    
    Provides CRUD operations, batch processing, and connection management
    for the elvis__structured_insights table.
    """
    
    TABLE_NAME = "elvis__structured_insights"
    
    def __init__(self, 
                 supabase_url: Optional[str] = None,
                 supabase_key: Optional[str] = None,
                 max_retries: int = 3,
                 timeout: int = 30,
                 enable_connection_pooling: bool = True):
        """
        Initialize Supabase client.
        
        Args:
            supabase_url: Supabase project URL
            supabase_key: Supabase service role key
            max_retries: Maximum number of retry attempts
            timeout: Operation timeout in seconds
            enable_connection_pooling: Enable connection pooling
        """
        self.supabase_url = supabase_url or os.getenv('SUPABASE_URL')
        self.supabase_key = supabase_key or os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        self.max_retries = max_retries
        self.timeout = timeout
        self.enable_connection_pooling = enable_connection_pooling
        
        if not self.supabase_url or not self.supabase_key:
            raise SupabaseConnectionError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables must be set"
            )
        
        self._client: Optional[Client] = None
        self._connection_pool = {}
        self._last_health_check = None
        self._health_check_interval = timedelta(minutes=5)
        
        # Initialize connection
        self._connect()
    
    def _connect(self) -> None:
        """Establish connection to Supabase."""
        try:
            self._client = create_client(self.supabase_url, self.supabase_key)
            logger.info("Successfully connected to Supabase")
            
            # Verify connection with a simple query
            self._health_check()
            
        except Exception as e:
            raise SupabaseConnectionError(f"Failed to connect to Supabase: {str(e)}")
    
    def _health_check(self) -> bool:
        """Perform health check on Supabase connection."""
        try:
            # Simple query to test connection
            result = self._client.table(self.TABLE_NAME).select("id").limit(1).execute()
            self._last_health_check = datetime.now()
            logger.debug("Supabase health check passed")
            return True
            
        except Exception as e:
            logger.error(f"Supabase health check failed: {str(e)}")
            return False
    
    def _ensure_connection(self) -> Client:
        """Ensure client connection is healthy."""
        if not self._client:
            self._connect()
        
        # Periodic health check
        if (self._last_health_check is None or 
            datetime.now() - self._last_health_check > self._health_check_interval):
            if not self._health_check():
                self._connect()
        
        return self._client
    
    @retry_on_failure(max_retries=3)
    def create_insight(self, insight: StructuredInsight) -> StructuredInsight:
        """
        Create a new structured insight record.
        
        Args:
            insight: StructuredInsight instance to create
            
        Returns:
            StructuredInsight: Created insight with database fields populated
            
        Raises:
            SupabaseOperationError: If creation fails
        """
        client = self._ensure_connection()
        
        try:
            # Validate input
            if not is_valid_contact_id(insight.metadata.contact_id):
                raise ValueError(f"Invalid contact_id format: {insight.metadata.contact_id}")
            
            # Convert to database format
            data = insight.to_db_dict()
            
            # Insert record
            result = client.table(self.TABLE_NAME).insert(data).execute()
            
            if not result.data:
                raise SupabaseOperationError("Insert operation returned no data")
            
            # Return updated insight
            created_insight = StructuredInsight.from_db_dict(result.data[0])
            
            logger.info(f"Successfully created insight for contact_id: {insight.metadata.contact_id}")
            return created_insight
            
        except Exception as e:
            logger.error(f"Failed to create insight: {str(e)}")
            raise SupabaseOperationError(f"Failed to create insight: {str(e)}")
    
    @retry_on_failure(max_retries=3)
    def get_latest_insight_by_contact_id(self, contact_id: str, generator: str = "structured_insight") -> Optional[StructuredInsight]:
        """
        Get the latest structured insight for a specific contact and generator.
        
        Args:
            contact_id: Contact identifier
            generator: Generator identifier (default: "structured_insight")
            
        Returns:
            StructuredInsight: Latest insight record or None if not found
            
        Raises:
            SupabaseOperationError: If retrieval fails
        """
        client = self._ensure_connection()
        
        try:
            if not is_valid_contact_id(contact_id):
                raise ValueError(f"Invalid contact_id format: {contact_id}")
                
            result = client.table(self.TABLE_NAME)\
                           .select("*")\
                           .eq("contact_id", contact_id)\
                           .eq("generator", generator)\
                           .eq("is_latest", True)\
                           .limit(1)\
                           .execute()
            
            if result.data:
                insight = StructuredInsight.from_db_dict(result.data[0])
                logger.debug(f"Retrieved latest insight for contact_id: {contact_id}")
                return insight
            
            logger.debug(f"No latest insight found for contact_id: {contact_id}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to retrieve latest insight for contact_id {contact_id}: {str(e)}")
            raise SupabaseOperationError(f"Failed to retrieve latest insight: {str(e)}")

    @retry_on_failure(max_retries=3)
    def get_insight_by_contact_id(self, contact_id: str) -> Optional[StructuredInsight]:
        """
        Retrieve insight by contact ID.
        
        Args:
            contact_id: Contact identifier
            
        Returns:
            StructuredInsight or None if not found
        """
        client = self._ensure_connection()
        
        try:
            if not is_valid_contact_id(contact_id):
                raise ValueError(f"Invalid contact_id format: {contact_id}")
            
            result = client.table(self.TABLE_NAME)\
                          .select("*")\
                          .eq("contact_id", contact_id)\
                          .order("updated_at", desc=True)\
                          .limit(1)\
                          .execute()
            
            if result.data:
                insight = StructuredInsight.from_db_dict(result.data[0])
                # Build a text to estimate tokens from: concatenate sections that exist
                parts = [
                    insight.personal or "",
                    insight.business or "",
                    insight.investing or "",
                    insight.three_i or "",
                    insight.deals or "",
                    insight.introductions or "",
                ]
                token_estimate = estimate_tokens("\n".join([p for p in parts if p]))
                logger.debug(f"Retrieved insight for contact_id: {contact_id} - Token Estimate ({token_estimate})")
                return insight
            
            logger.debug(f"No insight found for contact_id: {contact_id}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to retrieve insight by contact_id {contact_id}: {str(e)}")
            raise SupabaseOperationError(f"Failed to retrieve insight: {str(e)}")
    
    @retry_on_failure(max_retries=3)
    def get_insight_by_contact_and_eni(self, contact_id: str, eni_id: str) -> Optional[StructuredInsight]:
        """
        Retrieve insight by contact ID and ENI ID.
        
        Args:
            contact_id: Contact identifier
            eni_id: ENI identifier
            
        Returns:
            StructuredInsight or None if not found
        """
        client = self._ensure_connection()
        
        try:
            if not is_valid_contact_id(contact_id):
                raise ValueError(f"Invalid contact_id format: {contact_id}")
                
            result = client.table(self.TABLE_NAME)\
                          .select("*")\
                          .eq("contact_id", contact_id)\
                          .eq("eni_id", eni_id)\
                          .execute()
            
            if result.data:
                insight = StructuredInsight.from_db_dict(result.data[0])
                logger.debug(f"Retrieved insight for contact_id: {contact_id}, eni_id: {eni_id}")
                return insight
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to retrieve insight: {str(e)}")
            raise SupabaseOperationError(f"Failed to retrieve insight: {str(e)}")
    
    @retry_on_failure(max_retries=3)
    def update_insight(self, insight: StructuredInsight) -> StructuredInsight:
        """
        Update an existing insight record.
        
        Args:
            insight: StructuredInsight instance with updated data
            
        Returns:
            StructuredInsight: Updated insight
        """
        client = self._ensure_connection()
        
        try:
            if not insight.id:
                raise ValueError("Insight must have an ID to update")
            
            # Convert to database format and remove id/timestamps that shouldn't be updated
            data = insight.to_db_dict()
            data.pop('id', None)
            data.pop('created_at', None)
            data.pop('updated_at', None)  # Will be set by trigger
            
            # Increment version
            data['version'] = insight.metadata.version + 1
            
            result = client.table(self.TABLE_NAME)\
                          .update(data)\
                          .eq("id", str(insight.id))\
                          .execute()
            
            if not result.data:
                raise SupabaseOperationError("Update operation returned no data")
            
            updated_insight = StructuredInsight.from_db_dict(result.data[0])
            logger.info(f"Successfully updated insight for contact_id: {insight.metadata.contact_id}")
            return updated_insight
            
        except Exception as e:
            logger.error(f"Failed to update insight: {str(e)}")
            raise SupabaseOperationError(f"Failed to update insight: {str(e)}")
    
    @retry_on_failure(max_retries=3)
    def upsert_insight(self, insight: StructuredInsight) -> Tuple[StructuredInsight, bool]:
        """
        Insert or update insight based on contact_id and eni_id.
        
        Args:
            insight: StructuredInsight instance
            
        Returns:
            Tuple of (StructuredInsight, was_created: bool)
        """
        try:
            # Try to find existing record
            existing = self.get_insight_by_contact_and_eni(
                insight.metadata.contact_id, 
                insight.metadata.eni_id or "MISSING"
            )
            
            if existing:
                # Update existing record
                insight.id = existing.id
                insight.metadata.version = existing.metadata.version
                updated_insight = self.update_insight(insight)
                logger.info(f"Updated existing insight for contact_id: {insight.metadata.contact_id}")
                return updated_insight, False
            else:
                # Create new record
                created_insight = self.create_insight(insight)
                logger.info(f"Created new insight for contact_id: {insight.metadata.contact_id}")
                return created_insight, True
                
        except Exception as e:
            logger.error(f"Failed to upsert insight: {str(e)}")
            raise SupabaseOperationError(f"Failed to upsert insight: {str(e)}")
    
    @retry_on_failure(max_retries=3)
    def delete_insight(self, insight_id: str) -> bool:
        """
        Delete an insight by ID.
        
        Args:
            insight_id: UUID of insight to delete
            
        Returns:
            bool: True if deleted successfully
        """
        client = self._ensure_connection()
        
        try:
            result = client.table(self.TABLE_NAME)\
                          .delete()\
                          .eq("id", insight_id)\
                          .execute()
            
            success = len(result.data) > 0
            if success:
                logger.info(f"Successfully deleted insight: {insight_id}")
            else:
                logger.warning(f"No insight found to delete: {insight_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to delete insight: {str(e)}")
            raise SupabaseOperationError(f"Failed to delete insight: {str(e)}")
    
    @retry_on_failure(max_retries=3)
    def list_insights(self, 
                     limit: int = 100,
                     offset: int = 0,
                     contact_ids: Optional[List[str]] = None,
                     eni_source_types: Optional[List[str]] = None,
                     processing_status: Optional[ProcessingStatus] = None,
                     order_by: str = "updated_at",
                     ascending: bool = False) -> List[StructuredInsight]:
        """
        List insights with filtering and pagination.
        
        Args:
            limit: Maximum number of records to return
            offset: Number of records to skip
            contact_ids: Filter by contact IDs
            eni_source_types: Filter by ENI source types
            processing_status: Filter by processing status
            order_by: Field to order by
            ascending: Order direction
            
        Returns:
            List[StructuredInsight]: List of insights
        """
        client = self._ensure_connection()
        
        try:
            query = client.table(self.TABLE_NAME).select("*")
            
            # Apply filters
            if contact_ids:
                query = query.in_("contact_id", contact_ids)
            
            if eni_source_types:
                query = query.in_("eni_source_type", eni_source_types)
            
            if processing_status:
                query = query.eq("processing_status", processing_status.value)
            
            # Apply ordering and pagination
            query = query.order(order_by, desc=not ascending)
            query = query.range(offset, offset + limit - 1)
            
            result = query.execute()
            
            insights = [StructuredInsight.from_db_dict(row) for row in result.data]
            logger.debug(f"Retrieved {len(insights)} insights")
            return insights
            
        except Exception as e:
            logger.error(f"Failed to list insights: {str(e)}")
            raise SupabaseOperationError(f"Failed to list insights: {str(e)}")
    
    @retry_on_failure(max_retries=3)
    def search_insights(self, 
                       search_term: str,
                       search_fields: Optional[List[str]] = None,
                       limit: int = 50) -> List[StructuredInsight]:
        """
        Search insights using full-text search on content fields.
        
        Args:
            search_term: Term to search for
            search_fields: Fields to search in (default: all content fields)
            limit: Maximum number of results
            
        Returns:
            List[StructuredInsight]: Matching insights
        """
        client = self._ensure_connection()
        
        if not search_fields:
            search_fields = ['personal', 'business', 'investing', 'three_i', 'deals', 'introductions']
        
        try:
            # Use PostgreSQL full-text search
            conditions = []
            for field in search_fields:
                conditions.append(f"{field}.ilike.%{search_term}%")
            
            # Use OR conditions for multiple fields
            query = client.table(self.TABLE_NAME).select("*")
            
            # Build complex OR query
            if len(conditions) == 1:
                query = query.or_(conditions[0])
            else:
                or_condition = ",".join(conditions)
                query = query.or_(or_condition)
            
            query = query.limit(limit)
            result = query.execute()
            
            insights = [StructuredInsight.from_db_dict(row) for row in result.data]
            logger.debug(f"Found {len(insights)} insights matching search term: {search_term}")
            return insights
            
        except Exception as e:
            logger.error(f"Failed to search insights: {str(e)}")
            raise SupabaseOperationError(f"Failed to search insights: {str(e)}")
    
    @retry_on_failure(max_retries=3)
    def get_insights_count(self,
                          contact_ids: Optional[List[str]] = None,
                          processing_status: Optional[ProcessingStatus] = None) -> int:
        """
        Get count of insights with optional filtering.
        
        Args:
            contact_ids: Filter by contact IDs
            processing_status: Filter by processing status
            
        Returns:
            int: Count of matching insights
        """
        client = self._ensure_connection()
        
        try:
            query = client.table(self.TABLE_NAME).select("id", count="exact")
            
            if contact_ids:
                query = query.in_("contact_id", contact_ids)
            
            if processing_status:
                query = query.eq("processing_status", processing_status.value)
            
            result = query.execute()
            count = result.count if result.count is not None else 0
            
            logger.debug(f"Insights count: {count}")
            return count
            
        except Exception as e:
            logger.error(f"Failed to get insights count: {str(e)}")
            raise SupabaseOperationError(f"Failed to get insights count: {str(e)}")
    
    def batch_upsert_insights(self, insights: List[StructuredInsight], batch_size: int = 10) -> List[Tuple[StructuredInsight, bool]]:
        """
        Batch upsert multiple insights.
        
        Args:
            insights: List of insights to upsert
            batch_size: Number of insights to process per batch
            
        Returns:
            List[Tuple[StructuredInsight, bool]]: Results with (insight, was_created) tuples
        """
        results = []
        total_batches = (len(insights) + batch_size - 1) // batch_size
        
        logger.info(f"Starting batch upsert of {len(insights)} insights in {total_batches} batches")
        
        for i in range(0, len(insights), batch_size):
            batch = insights[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            
            logger.debug(f"Processing batch {batch_num}/{total_batches} ({len(batch)} insights)")
            
            for insight in batch:
                try:
                    result = self.upsert_insight(insight)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Failed to upsert insight {insight.metadata.contact_id}: {str(e)}")
                    # Continue with next insight rather than failing the entire batch
        
        logger.info(f"Completed batch upsert: {len(results)} successful operations")
        return results
    
    def create_table_if_not_exists(self) -> bool:
        """
        Create the structured insights table if it doesn't exist.
        
        Note: This requires the SQL schema to be executed separately.
        This method just checks if the table exists.
        
        Returns:
            bool: True if table exists or was created
        """
        try:
            # Try a simple query to check if table exists
            result = self._client.table(self.TABLE_NAME).select("id").limit(1).execute()
            logger.info(f"Table {self.TABLE_NAME} exists and is accessible")
            return True
            
        except Exception as e:
            logger.error(f"Table {self.TABLE_NAME} does not exist or is not accessible: {str(e)}")
            logger.info("Please run the SQL schema file to create the table")
            return False
    
    def close(self) -> None:
        """Close the client connection."""
        if self._client:
            # Supabase client doesn't have explicit close method
            self._client = None
            logger.info("Supabase client connection closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Convenience functions

def create_supabase_client(**kwargs) -> SupabaseInsightsClient:
    """Create a new Supabase insights client with default settings."""
    return SupabaseInsightsClient(**kwargs)


@contextmanager
def supabase_client(**kwargs):
    """Context manager for Supabase client."""
    client = create_supabase_client(**kwargs)
    try:
        yield client
    finally:
        client.close()


# Export main classes and functions
__all__ = [
    'SupabaseInsightsClient',
    'SupabaseConnectionError',
    'SupabaseOperationError',
    'create_supabase_client',
    'supabase_client',
] 