"""
Supabase Insights Processor.

This module provides a memory-efficient processing service that integrates
Supabase storage with the existing AI processing pipeline.
"""

import gc
import weakref
from typing import Any, Dict, List, Optional, Tuple, Set
from datetime import datetime
from collections import defaultdict
import logging
import json
import re

from .supabase_client import SupabaseInsightsClient, SupabaseOperationError
from .schema import (
    StructuredInsight,
    InsightMetadata,
    StructuredInsightContent,
    ProcessingStatus,
    normalize_insight_data,
    is_valid_contact_id
)

logger = logging.getLogger(__name__)


class MemoryManager:
    """Manages memory usage during processing."""
    
    def __init__(self, max_items: int = 1000, use_weak_references: bool = True):
        self.max_items = max_items
        self.use_weak_references = use_weak_references
        self._cache = weakref.WeakValueDictionary() if use_weak_references else {}
        self._access_order = []
        
    def add_item(self, key: str, item: Any) -> None:
        """Add item to memory cache."""
        if len(self._cache) >= self.max_items:
            self._evict_oldest()
        
        self._cache[key] = item
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)
    
    def get_item(self, key: str) -> Optional[Any]:
        """Get item from cache."""
        item = self._cache.get(key)
        if item and key in self._access_order:
            self._access_order.remove(key)
            self._access_order.append(key)
        return item
    
    def remove_item(self, key: str) -> None:
        """Remove item from cache."""
        self._cache.pop(key, None)
        if key in self._access_order:
            self._access_order.remove(key)
    
    def _evict_oldest(self) -> None:
        """Evict oldest item from cache."""
        if self._access_order:
            oldest_key = self._access_order.pop(0)
            self._cache.pop(oldest_key, None)
    
    def clear(self) -> None:
        """Clear all cached items."""
        self._cache.clear()
        self._access_order.clear()
        gc.collect()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory usage statistics."""
        return {
            'cached_items': len(self._cache),
            'max_items': self.max_items,
            'use_weak_references': self.use_weak_references,
            'access_order_length': len(self._access_order)
        }


class ProcessingState:
    """Tracks processing state for a batch of insights."""
    
    def __init__(self):
        self.processed_contact_ids: Set[str] = set()
        self.failed_contact_ids: Set[str] = set()
        self.created_insights: List[str] = []  # Contact IDs of created insights
        self.updated_insights: List[str] = []  # Contact IDs of updated insights
        self.errors: Dict[str, str] = {}  # contact_id -> error_message
        
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None
        
    def mark_processed(self, contact_id: str, was_created: bool) -> None:
        """Mark a contact as successfully processed."""
        self.processed_contact_ids.add(contact_id)
        if was_created:
            self.created_insights.append(contact_id)
        else:
            self.updated_insights.append(contact_id)
    
    def mark_failed(self, contact_id: str, error: str) -> None:
        """Mark a contact as failed."""
        self.failed_contact_ids.add(contact_id)
        self.errors[contact_id] = error
    
    def finalize(self) -> None:
        """Finalize processing state."""
        self.end_time = datetime.now()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get processing summary."""
        duration = None
        if self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()
        
        return {
            'total_processed': len(self.processed_contact_ids),
            'created': len(self.created_insights),
            'updated': len(self.updated_insights),
            'failed': len(self.failed_contact_ids),
            'duration_seconds': duration,
            'errors': self.errors
        }


class SupabaseInsightsProcessor:
    """
    Memory-efficient processor for structured insights with Supabase integration.
    
    This class provides the core processing pipeline that:
    1. Loads existing insights from Supabase before processing
    2. Merges new data with existing insights
    3. Implements memory-efficient batch processing
    4. Provides comprehensive error handling and logging
    """
    
    def __init__(self, 
                 supabase_client: SupabaseInsightsClient,
                 memory_manager: Optional[MemoryManager] = None,
                 batch_size: int = 10,
                 enable_memory_optimization: bool = True):
        """
        Initialize the processor.
        
        Args:
            supabase_client: Supabase client instance
            memory_manager: Memory management instance
            batch_size: Batch size for processing
            enable_memory_optimization: Enable memory optimization features
        """
        self.supabase_client = supabase_client
        self.memory_manager = memory_manager or MemoryManager()
        self.batch_size = batch_size
        self.enable_memory_optimization = enable_memory_optimization
        
        # Processing state
        self.current_state: Optional[ProcessingState] = None
        
        logger.info(f"Initialized SupabaseInsightsProcessor with batch_size={batch_size}")
    
    def load_existing_insight(self, contact_id: str, eni_id: Optional[str] = None) -> Optional[StructuredInsight]:
        """
        Load existing insight from Supabase with memory caching.
        
        Args:
            contact_id: Contact identifier
            eni_id: Optional ENI identifier for specific lookup
            
        Returns:
            Existing StructuredInsight or None
        """
        cache_key = f"{contact_id}_{eni_id or 'latest'}"
        
        # Check memory cache first
        cached_insight = self.memory_manager.get_item(cache_key)
        if cached_insight:
            logger.debug(f"Retrieved cached insight for {contact_id}")
            return cached_insight
        
        try:
            # Load from Supabase
            if eni_id:
                insight = self.supabase_client.get_insight_by_contact_and_eni(contact_id, eni_id)
            else:
                insight = self.supabase_client.get_insight_by_contact_id(contact_id)
            
            # Cache the result
            if insight:
                self.memory_manager.add_item(cache_key, insight)
                logger.debug(f"Loaded and cached insight for {contact_id}")
            
            return insight
            
        except Exception as e:
            logger.error(f"Failed to load existing insight for {contact_id}: {str(e)}")
            return None
    
    def merge_insights(self, 
                      existing: StructuredInsight, 
                      new_content: StructuredInsightContent,
                      new_metadata: Dict[str, Any]) -> StructuredInsight:
        """
        Merge new insight content with existing insight.
        
        Args:
            existing: Existing StructuredInsight
            new_content: New insight content to merge
            new_metadata: New metadata to incorporate
            
        Returns:
            Merged StructuredInsight
        """
        logger.debug(f"Merging insights for contact_id: {existing.metadata.contact_id}")
        
        # Create updated metadata
        updated_metadata = InsightMetadata(
            contact_id=existing.metadata.contact_id,
            eni_id=existing.metadata.eni_id,
            member_name=existing.metadata.member_name or new_metadata.get('member_name'),
            eni_source_type=existing.metadata.eni_source_type,
            eni_source_subtype=existing.metadata.eni_source_subtype,
            eni_source_types=self._merge_lists(existing.metadata.eni_source_types, new_metadata.get('eni_source_types')),
            eni_source_subtypes=self._merge_lists(existing.metadata.eni_source_subtypes, new_metadata.get('eni_source_subtypes')),
            generator=existing.metadata.generator,
            system_prompt_key=new_metadata.get('system_prompt_key') or existing.metadata.system_prompt_key,
            context_files=new_metadata.get('context_files') or existing.metadata.context_files,
            record_count=existing.metadata.record_count + new_metadata.get('record_count', 1),
            total_eni_ids=existing.metadata.total_eni_ids + new_metadata.get('total_eni_ids', 1),
            generated_at=existing.metadata.generated_at,  # Keep original generation time
            processing_status=ProcessingStatus.COMPLETED,
            version=existing.metadata.version,  # Will be incremented by update
            additional_metadata=self._merge_metadata(existing.metadata.additional_metadata, new_metadata.get('additional_metadata'))
        )
        
        # Merge content sections
        merged_content = self._merge_content_sections(existing.insights, new_content)
        
        # Create updated insight
        updated_insight = StructuredInsight(
            id=existing.id,
            created_at=existing.created_at,
            updated_at=existing.updated_at,
            metadata=updated_metadata,
            insights=merged_content
        )
        
        logger.debug(f"Successfully merged insights for contact_id: {existing.metadata.contact_id}")
        return updated_insight
    
    def _merge_lists(self, existing: Optional[List[str]], new: Optional[List[str]]) -> Optional[List[str]]:
        """Merge two lists, removing duplicates."""
        if not existing and not new:
            return None
        
        combined = set(existing or [])
        combined.update(new or [])
        
        return list(combined) if combined else None
    
    def _merge_metadata(self, existing: Optional[Dict[str, Any]], new: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Merge metadata dictionaries."""
        if not existing and not new:
            return None
        
        merged = dict(existing or {})
        merged.update(new or {})
        
        return merged if merged else None
    
    def _merge_content_sections(self, 
                               existing: StructuredInsightContent, 
                               new: StructuredInsightContent) -> StructuredInsightContent:
        """
        Merge content sections intelligently.
        
        This is a simple merge that appends new content. In a production system,
        you might want more sophisticated merging logic.
        """
        
        def merge_section(existing_text: Optional[str], new_text: Optional[str]) -> Optional[str]:
            if not existing_text:
                return new_text
            if not new_text:
                return existing_text
            
            # Simple append with separator
            return f"{existing_text}\n\n{new_text}"
        
        if isinstance(existing, dict):
            existing_content = StructuredInsightContent(**existing)
        else:
            existing_content = existing
        
        return StructuredInsightContent(
            personal=merge_section(existing_content.personal, new.personal),
            business=merge_section(existing_content.business, new.business),
            investing=merge_section(existing_content.investing, new.investing),
            three_i=merge_section(existing_content.three_i, new.three_i),
            deals=merge_section(existing_content.deals, new.deals),
            introductions=merge_section(existing_content.introductions, new.introductions)
        )
    
    def process_insight(self, 
                       contact_id: str,
                       eni_id: str,
                       insight_content: StructuredInsightContent,
                       metadata: Dict[str, Any],
                       force_create: bool = False) -> Tuple[StructuredInsight, bool]:
        """
        Process a single insight with merge logic.
        
        Args:
            contact_id: Contact identifier
            eni_id: ENI identifier
            insight_content: New insight content
            metadata: Processing metadata
            force_create: Force creation of new insight (skip merge)
            
        Returns:
            Tuple of (processed_insight, was_created)
        """
        if not is_valid_contact_id(contact_id):
            raise ValueError(f"Invalid contact_id format: {contact_id}")
        
        try:
            # Load existing insight if not forcing creation
            existing_insight = None
            if not force_create:
                existing_insight = self.load_existing_insight(contact_id, eni_id)
            
            if existing_insight:
                # Merge with existing insight
                merged_insight = self.merge_insights(existing_insight, insight_content, metadata)
                result_insight, was_created = self.supabase_client.upsert_insight(merged_insight)
                
                # Update cache
                cache_key = f"{contact_id}_{eni_id}"
                self.memory_manager.add_item(cache_key, result_insight)
                
                logger.info(f"Merged and updated insight for contact_id: {contact_id}")
                return result_insight, was_created
            
            else:
                # Create new insight
                new_metadata = InsightMetadata(
                    contact_id=contact_id,
                    eni_id=eni_id,
                    **metadata
                )
                
                new_insight = StructuredInsight(
                    metadata=new_metadata,
                    insights=insight_content
                )
                
                result_insight, was_created = self.supabase_client.upsert_insight(new_insight)
                
                # Update cache
                cache_key = f"{contact_id}_{eni_id}"
                self.memory_manager.add_item(cache_key, result_insight)
                
                logger.info(f"Created new insight for contact_id: {contact_id}")
                return result_insight, was_created
        
        except Exception as e:
            logger.error(f"Failed to process insight for {contact_id}: {str(e)}")
            raise
    
    def batch_process_insights(self, 
                              insights_data: List[Dict[str, Any]],
                              clear_memory_after_batch: bool = True) -> ProcessingState:
        """
        Process multiple insights in batches with memory management.
        
        Args:
            insights_data: List of insight data dictionaries
            clear_memory_after_batch: Clear memory cache after each batch
            
        Returns:
            ProcessingState with results summary
        """
        self.current_state = ProcessingState()
        total_insights = len(insights_data)
        total_batches = (total_insights + self.batch_size - 1) // self.batch_size
        
        logger.info(f"Starting batch processing of {total_insights} insights in {total_batches} batches")
        
        try:
            for i in range(0, total_insights, self.batch_size):
                batch = insights_data[i:i + self.batch_size]
                batch_num = (i // self.batch_size) + 1
                
                logger.debug(f"Processing batch {batch_num}/{total_batches} ({len(batch)} insights)")
                
                # Process batch
                self._process_batch(batch)
                
                # Memory management
                if clear_memory_after_batch and self.enable_memory_optimization:
                    self.memory_manager.clear()
                    gc.collect()
                    logger.debug(f"Cleared memory after batch {batch_num}")
        
        finally:
            self.current_state.finalize()
            
        logger.info(f"Completed batch processing: {self.current_state.get_summary()}")
        return self.current_state
    
    def _process_batch(self, batch: List[Dict[str, Any]]) -> None:
        """Process a single batch of insights."""
        
        for insight_data in batch:
            contact_id = insight_data.get('contact_id')
            
            if not contact_id:
                logger.warning("Skipping insight data without contact_id")
                continue
            
            try:
                # Extract required fields
                eni_id = insight_data.get('eni_id', 'UNKNOWN')
                
                # Parse insight content
                if 'insights' in insight_data:
                    content_data = insight_data['insights']
                    if isinstance(content_data, str):
                        # Try to parse JSON string
                        try:
                            content_data = json.loads(content_data)
                        except json.JSONDecodeError:
                            logger.warning(f"Could not parse insights JSON for {contact_id}")
                            content_data = {"raw_content": content_data}
                    
                    insight_content = StructuredInsightContent(**content_data)
                else:
                    logger.warning(f"No insights content found for {contact_id}")
                    continue
                
                # Extract metadata
                metadata = {
                    'member_name': insight_data.get('member_name'),
                    'eni_source_type': insight_data.get('eni_source_type'),
                    'eni_source_subtype': insight_data.get('eni_source_subtype'),
                    'eni_source_types': insight_data.get('eni_source_types'),
                    'eni_source_subtypes': insight_data.get('eni_source_subtypes'),
                    'generator': insight_data.get('generator', 'structured_insight'),
                    'system_prompt_key': insight_data.get('system_prompt_key'),
                    'context_files': insight_data.get('context_files'),
                    'record_count': insight_data.get('record_count', 1),
                    'total_eni_ids': insight_data.get('total_eni_ids', 1),
                    'additional_metadata': insight_data.get('additional_metadata')
                }
                
                # Process the insight
                processed_insight, was_created = self.process_insight(
                    contact_id=contact_id,
                    eni_id=eni_id,
                    insight_content=insight_content,
                    metadata=metadata
                )
                
                # Track success
                self.current_state.mark_processed(contact_id, was_created)
                
            except Exception as e:
                error_msg = f"Failed to process insight: {str(e)}"
                logger.error(f"Error processing {contact_id}: {error_msg}")
                self.current_state.mark_failed(contact_id, error_msg)
    
    def get_processing_statistics(self) -> Dict[str, Any]:
        """Get comprehensive processing statistics."""
        stats = {
            'memory_stats': self.memory_manager.get_stats(),
            'supabase_table_exists': self.supabase_client.create_table_if_not_exists(),
            'batch_size': self.batch_size,
            'memory_optimization_enabled': self.enable_memory_optimization
        }
        
        if self.current_state:
            stats['current_processing'] = self.current_state.get_summary()
        
        # Get insight counts from Supabase
        try:
            total_insights = self.supabase_client.get_insights_count()
            stats['total_insights_in_db'] = total_insights
        except Exception as e:
            logger.warning(f"Could not get insight count from Supabase: {str(e)}")
            stats['total_insights_in_db'] = None
        
        return stats
    
    def cleanup(self) -> None:
        """Clean up resources."""
        self.memory_manager.clear()
        logger.info("Cleaned up SupabaseInsightsProcessor resources")


def create_insights_processor(supabase_client: SupabaseInsightsClient, **kwargs) -> SupabaseInsightsProcessor:
    """Create a new insights processor with default settings."""
    return SupabaseInsightsProcessor(supabase_client, **kwargs)


# Export main classes
__all__ = [
    'SupabaseInsightsProcessor',
    'MemoryManager',
    'ProcessingState',
    'create_insights_processor'
] 