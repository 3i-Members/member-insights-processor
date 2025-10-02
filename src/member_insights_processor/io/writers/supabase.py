"""
Supabase Insights Processor.

This module provides a memory-efficient processing service that integrates
Supabase storage with the existing AI processing pipeline.
"""

import gc
import weakref
from typing import Any, Dict, List, Optional, Tuple, Set, Union
from datetime import datetime
from collections import defaultdict
import logging
import json
import re

from member_insights_processor.io.readers.supabase import (
    SupabaseInsightsClient,
    SupabaseOperationError,
)
from member_insights_processor.io.schema import (
    StructuredInsight,
    InsightMetadata,
    StructuredInsightContent,
    ProcessingStatus,
    normalize_insight_data,
    is_valid_contact_id,
)

logger = logging.getLogger(__name__)


class ProcessingState:
    """Track processing state for memory efficiency."""

    def __init__(self):
        self.processed_contacts: Set[str] = set()
        self.failed_contacts: Set[str] = set()
        self.processing_metrics = {
            "total_processed": 0,
            "total_created": 0,
            "total_updated": 0,
            "total_failed": 0,
            "start_time": datetime.now(),
            "errors": [],
        }

    def mark_processed(self, contact_id: str, was_created: bool) -> None:
        """Mark a contact as successfully processed."""
        self.processed_contacts.add(contact_id)
        self.processing_metrics["total_processed"] += 1
        if was_created:
            self.processing_metrics["total_created"] += 1
        else:
            self.processing_metrics["total_updated"] += 1

    def mark_failed(self, contact_id: str, error: str) -> None:
        """Mark a contact as failed."""
        self.failed_contacts.add(contact_id)
        self.processing_metrics["total_failed"] += 1
        self.processing_metrics["errors"].append(f"{contact_id}: {error}")

    def get_summary(self) -> Dict[str, Any]:
        """Get processing summary."""
        elapsed = (datetime.now() - self.processing_metrics["start_time"]).total_seconds()
        return {
            **self.processing_metrics,
            "elapsed_seconds": elapsed,
            "processing_rate": self.processing_metrics["total_processed"] / max(elapsed, 1),
        }

    def cleanup(self) -> None:
        """Clean up memory."""
        self.processed_contacts.clear()
        self.failed_contacts.clear()
        # Keep metrics for final reporting
        gc.collect()


class SupabaseInsightsProcessor:
    """
    Memory-efficient processor for structured insights with Supabase backend.

    This processor handles individual insight processing and batch operations
    while maintaining memory efficiency through state cleanup and weak references.
    """

    def __init__(self, supabase_client: SupabaseInsightsClient, batch_size: int = 10):
        """
        Initialize the processor.

        Args:
            supabase_client: Configured Supabase client instance
            batch_size: Number of records to process in each batch
        """
        self.client = supabase_client
        self.batch_size = batch_size
        self.current_state = ProcessingState()

        # Use weak references for memory efficiency
        self._contact_cache = weakref.WeakValueDictionary()

        logger.info(f"Initialized SupabaseInsightsProcessor with batch_size={batch_size}")

    def process_insight(
        self,
        contact_id: str,
        eni_id: str,
        insight_content: StructuredInsightContent,
        metadata: Optional[Dict[str, Any]] = None,
        est_input_tokens_delta: Optional[int] = None,
        est_insights_tokens_current: Optional[int] = None,
        generation_time_seconds_delta: Optional[float] = None,
    ) -> Tuple[Optional[StructuredInsight], bool]:
        """
        Process a single insight by creating a new versioned record.

        Args:
            contact_id: Contact identifier
            eni_id: ENI identifier
            insight_content: Structured insight content
            metadata: Optional metadata dictionary
            est_input_tokens_delta: Input tokens for this iteration
            est_insights_tokens_current: Current insights tokens
            generation_time_seconds_delta: Generation time for this iteration

        Returns:
            Tuple of (processed_insight, was_created)
        """
        try:
            if not is_valid_contact_id(contact_id):
                raise ValueError(f"Invalid contact_id format: {contact_id}")

            # Get generator from metadata (default to 'structured_insight')
            generator = (
                metadata.get("generator", "structured_insight")
                if metadata
                else "structured_insight"
            )

            # Step 1: Set all previous records for this contact_id + generator to is_latest=false
            try:
                self.client._ensure_connection()
                update_result = (
                    self.client._client.table(self.client.TABLE_NAME)
                    .update({"is_latest": False})
                    .eq("contact_id", contact_id)
                    .eq("generator", generator)
                    .eq("is_latest", True)
                    .execute()
                )
                logger.debug(
                    f"Set previous records to is_latest=false for {contact_id} + {generator}"
                )
            except Exception as e:
                logger.warning(f"Failed to update previous records for {contact_id}: {e}")
                # Continue with creation even if update fails

            # Step 2: Get the next version number
            try:
                latest_version_result = (
                    self.client._client.table(self.client.TABLE_NAME)
                    .select("version")
                    .eq("contact_id", contact_id)
                    .eq("generator", generator)
                    .order("version", desc=True)
                    .limit(1)
                    .execute()
                )

                next_version = 1
                if latest_version_result.data:
                    latest_version = latest_version_result.data[0].get("version", 0)
                    next_version = latest_version + 1

                logger.debug(f"Next version for {contact_id} + {generator}: {next_version}")
            except Exception as e:
                logger.warning(
                    f"Failed to get latest version for {contact_id}: {e}, defaulting to version 1"
                )
                next_version = 1

            # Step 3: Create new versioned record
            new_insight = self._create_new_versioned_insight(
                contact_id,
                eni_id,
                insight_content,
                metadata or {},
                next_version,
                est_input_tokens_delta,
                est_insights_tokens_current,
                generation_time_seconds_delta,
            )

            # Step 4: Insert the new record
            result = self.client.create_insight(new_insight)

            # Cache result for potential reuse (weak reference)
            self._contact_cache[contact_id] = result

            logger.info(
                f"Created new versioned insight v{next_version} for contact_id: {contact_id}"
            )
            return result, True

        except Exception as e:
            logger.error(f"Failed to process insight for contact_id {contact_id}: {str(e)}")
            return None, False

    def _create_new_versioned_insight(
        self,
        contact_id: str,
        eni_id: str,
        insight_content: StructuredInsightContent,
        metadata: Dict[str, Any],
        version: int,
        est_input_tokens_delta: Optional[int],
        est_insights_tokens_current: Optional[int],
        generation_time_seconds_delta: Optional[float],
    ) -> StructuredInsight:
        """Create a new versioned StructuredInsight instance."""

        # Create metadata - store only current iteration's ENI types/subtypes (not cumulative)
        insight_metadata = InsightMetadata(
            contact_id=contact_id,
            eni_id=eni_id,
            member_name=metadata.get("member_name"),
            eni_source_types=metadata.get("eni_source_types", []),  # Current iteration only
            eni_source_subtypes=metadata.get("eni_source_subtypes", []),  # Current iteration only
            generator=metadata.get("generator", "structured_insight"),
            system_prompt_key=metadata.get("system_prompt_key"),
            context_files=metadata.get("context_files"),
            record_count=metadata.get("record_count", 1),
            total_eni_ids=metadata.get("total_eni_ids", 1),
            generated_at=datetime.now(),
            processing_status=ProcessingStatus.COMPLETED,
            version=version,
        )

        return StructuredInsight(
            metadata=insight_metadata,
            insights=insight_content,
            is_latest=True,  # New records are always the latest
            est_input_tokens=est_input_tokens_delta or 0,
            est_insights_tokens=est_insights_tokens_current or 0,
            generation_time_seconds=generation_time_seconds_delta or 0.0,
        )

    def process_batch(self, insights_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process a batch of insights.

        Args:
            insights_data: List of insight data dictionaries

        Returns:
            Dict[str, Any]: Processing results summary
        """
        logger.info(f"Starting batch processing of {len(insights_data)} insights")

        # Clear state for new batch
        self.current_state.cleanup()
        self.current_state = ProcessingState()

        # Process in chunks for memory efficiency
        total_chunks = (len(insights_data) + self.batch_size - 1) // self.batch_size

        for chunk_idx in range(total_chunks):
            start_idx = chunk_idx * self.batch_size
            end_idx = min(start_idx + self.batch_size, len(insights_data))
            chunk = insights_data[start_idx:end_idx]

            logger.info(f"Processing chunk {chunk_idx + 1}/{total_chunks} ({len(chunk)} records)")

            self._process_batch(chunk)

            # Force garbage collection after each chunk
            gc.collect()

        summary = self.current_state.get_summary()
        logger.info(f"Batch processing complete: {summary}")

        return summary

    def _process_batch(self, batch: List[Dict[str, Any]]) -> None:
        """Process a single batch chunk."""
        for insight_data in batch:
            try:
                # Normalize the data format
                normalized_data = normalize_insight_data(insight_data)

                contact_id = normalized_data.get("contact_id")
                eni_id = normalized_data.get("eni_id", f"BATCH-{contact_id}")

                if not contact_id:
                    self.current_state.mark_failed("unknown", "Missing contact_id")
                    continue

                # Extract insight content
                insights_content_data = normalized_data.get("insights", {})
                if not insights_content_data:
                    logger.warning(f"No insights content found for {contact_id}")
                    continue

                try:
                    insight_content = StructuredInsightContent(**insights_content_data)
                except Exception as e:
                    logger.error(f"Failed to parse insight content for {contact_id}: {e}")
                    self.current_state.mark_failed(contact_id, f"Invalid content format: {str(e)}")
                    continue

                # Extract metadata (excluding dropped fields)
                metadata = {
                    "member_name": insight_data.get("member_name"),
                    "eni_source_types": insight_data.get("eni_source_types"),
                    "eni_source_subtypes": insight_data.get("eni_source_subtypes"),
                    "generator": insight_data.get("generator", "structured_insight"),
                    "system_prompt_key": insight_data.get("system_prompt_key"),
                    "context_files": insight_data.get("context_files"),
                    "record_count": insight_data.get("record_count", 1),
                    "total_eni_ids": insight_data.get("total_eni_ids", 1),
                }

                # Process the insight (batch path doesn't pass token metrics)
                processed_insight, was_created = self.process_insight(
                    contact_id=contact_id,
                    eni_id=eni_id,
                    insight_content=insight_content,
                    metadata=metadata,
                )

                # Track success
                self.current_state.mark_processed(contact_id, was_created)

            except Exception as e:
                error_msg = f"Failed to process insight: {str(e)}"
                logger.error(f"Error processing {contact_id}: {error_msg}")
                self.current_state.mark_failed(contact_id, error_msg)

    def get_processing_statistics(self) -> Dict[str, Any]:
        """Get comprehensive processing statistics."""
        return {
            "current_batch": self.current_state.get_summary(),
            "cache_size": len(self._contact_cache),
            "batch_size": self.batch_size,
            "client_stats": {
                "table_name": self.client.TABLE_NAME,
                "connection_status": "connected" if self.client._client else "disconnected",
            },
        }

    def load_existing_insight(self, contact_id: str) -> Optional[StructuredInsight]:
        """
        Load existing insight for a contact from cache or database.

        Args:
            contact_id: Contact identifier

        Returns:
            Optional[StructuredInsight]: Existing insight or None
        """
        # Check cache first
        if contact_id in self._contact_cache:
            logger.debug(f"Cache hit for contact_id: {contact_id}")
            return self._contact_cache[contact_id]

        # Query from database
        try:
            existing = self.client.get_latest_insight_by_contact_id(
                contact_id, generator="structured_insight"
            )
            if existing:
                # Store in cache with weak reference
                self._contact_cache[contact_id] = existing
                logger.debug(f"Loaded existing insight for contact_id: {contact_id}")
            return existing
        except Exception as e:
            logger.warning(f"Failed to load existing insight for contact_id {contact_id}: {e}")
            return None

    def cleanup(self) -> None:
        """Clean up resources and memory."""
        logger.info("Cleaning up SupabaseInsightsProcessor resources")

        # Clear cache
        self._contact_cache.clear()

        # Clean up current state
        self.current_state.cleanup()

        # Force garbage collection
        gc.collect()

        logger.info("SupabaseInsightsProcessor cleanup complete")

    def __del__(self):
        """Destructor to ensure cleanup."""
        try:
            self.cleanup()
        except Exception:
            pass  # Ignore errors during cleanup in destructor
