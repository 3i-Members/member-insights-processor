"""
Supabase-Powered Airtable Writer.

This module provides an Airtable writer that pulls structured insights from Supabase
instead of receiving them during processing. This allows for decoupled processing
and better memory management.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

from data_processing.supabase_client import SupabaseInsightsClient, SupabaseOperationError
from data_processing.schema import StructuredInsight, ProcessingStatus
from output_management.structured_airtable_writer import StructuredInsightsAirtableWriter

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Result of a sync operation."""
    contact_id: str
    success: bool
    action: str  # 'created', 'updated', 'skipped', 'failed'
    error_message: Optional[str] = None
    airtable_record_id: Optional[str] = None


class SupabaseAirtableSync:
    """
    Syncs structured insights from Supabase to Airtable.
    
    This class provides a decoupled approach where insights are stored in Supabase
    first, then synced to Airtable separately. This improves memory efficiency
    and allows for better error handling.
    """
    
    def __init__(self,
                 supabase_client: SupabaseInsightsClient,
                 airtable_writer: StructuredInsightsAirtableWriter,
                 sync_interval_hours: int = 24):
        """
        Initialize the sync service.
        
        Args:
            supabase_client: Supabase client for reading insights
            airtable_writer: Airtable writer for syncing data
            sync_interval_hours: Hours between automatic syncs
        """
        self.supabase_client = supabase_client
        self.airtable_writer = airtable_writer
        self.sync_interval_hours = sync_interval_hours
        
        self.last_sync_time: Optional[datetime] = None
        self.sync_results: List[SyncResult] = []
        
        logger.info(f"Initialized SupabaseAirtableSync with {sync_interval_hours}h interval")
    
    def sync_contact_to_airtable(self, contact_id: str, force_update: bool = False) -> SyncResult:
        """
        Sync a single contact's latest structured insight to Airtable.
        
        Args:
            contact_id: Contact identifier
            force_update: Force update even if record exists
            
        Returns:
            SyncResult: Result of the sync operation
        """
        try:
            # Get latest structured insight from Supabase
            insight = self.supabase_client.get_latest_insight_by_contact_id(contact_id, generator='structured_insight')
            if not insight:
                return SyncResult(
                    contact_id=contact_id,
                    success=False,
                    action="failed",
                    error_message="No latest structured insight found in Supabase"
                )
            
            # Check if we should skip this sync
            if not force_update and self._should_skip_sync(insight):
                return SyncResult(
                    contact_id=contact_id,
                    success=True,
                    action="skipped",
                    error_message="Sync skipped based on skip criteria"
                )
            
            # Convert to Airtable format
            airtable_data = self._convert_insight_to_airtable_format(insight)
            
            # Sync to Airtable
            sync_res = self.airtable_writer.create_note_submission_record(
                contact_id=contact_id,
                structured_json=airtable_data
            )
            
            if sync_res and getattr(sync_res, 'success', False):
                action = "created" if getattr(sync_res, 'created', False) else ("updated" if getattr(sync_res, 'updated', False) else "created")
                return SyncResult(
                    contact_id=contact_id,
                    success=True,
                    action=action,
                    airtable_record_id=getattr(sync_res, 'record_id', None)
                )
            else:
                return SyncResult(
                    contact_id=contact_id,
                    success=False,
                    action="failed",
                    error_message=getattr(sync_res, 'error', "Failed to create/update Airtable record")
                )
                
        except Exception as e:
            logger.error(f"Error syncing contact {contact_id} to Airtable: {e}")
            return SyncResult(
                contact_id=contact_id,
                success=False,
                action="failed",
                error_message=str(e)
            )
    
    def sync_recent_insights(self, 
                            hours_back: int = 24,
                            max_records: int = 100,
                            force_update: bool = False) -> List[SyncResult]:
        """
        Sync insights that have been updated recently.
        
        Args:
            hours_back: How many hours back to look for updates
            max_records: Maximum number of records to sync
            force_update: Force update even if already synced
            
        Returns:
            List[SyncResult]: Results of sync operations
        """
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        logger.info(f"Syncing insights updated since {cutoff_time}")
        
        try:
            # Get recent insights from Supabase
            recent_insights = self.supabase_client.list_insights(
                limit=max_records,
                order_by='updated_at',
                ascending=False
            )
            
            # Filter by update time
            filtered_insights = [
                insight for insight in recent_insights
                if insight.updated_at and insight.updated_at >= cutoff_time
            ]
            
            logger.info(f"Found {len(filtered_insights)} insights to sync")
            
            # Sync each insight
            results = []
            for insight in filtered_insights:
                result = self.sync_contact_to_airtable(
                    insight.metadata.contact_id,
                    force_update=force_update
                )
                results.append(result)
            
            self.sync_results.extend(results)
            self.last_sync_time = datetime.now()
            
            # Log summary
            summary = self._get_sync_summary(results)
            logger.info(f"Sync completed: {summary}")
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to sync recent insights: {str(e)}")
            return []
    
    def sync_all_insights(self, 
                         batch_size: int = 50,
                         force_update: bool = False) -> List[SyncResult]:
        """
        Sync all insights from Supabase to Airtable.
        
        Args:
            batch_size: Number of insights to process per batch
            force_update: Force update all records
            
        Returns:
            List[SyncResult]: Results of all sync operations
        """
        logger.info("Starting full sync of all insights")
        
        try:
            # Get total count
            total_count = self.supabase_client.get_insights_count(
                processing_status=ProcessingStatus.COMPLETED
            )
            
            logger.info(f"Found {total_count} insights to sync")
            
            all_results = []
            offset = 0
            
            while offset < total_count:
                # Get batch of insights
                batch_insights = self.supabase_client.list_insights(
                    limit=batch_size,
                    offset=offset,
                    processing_status=ProcessingStatus.COMPLETED,
                    order_by='updated_at',
                    ascending=False
                )
                
                if not batch_insights:
                    break
                
                logger.info(f"Processing batch {offset//batch_size + 1}: {len(batch_insights)} insights")
                
                # Sync each insight in the batch
                batch_results = []
                for insight in batch_insights:
                    result = self.sync_contact_to_airtable(
                        insight.metadata.contact_id,
                        force_update=force_update
                    )
                    batch_results.append(result)
                
                all_results.extend(batch_results)
                offset += len(batch_insights)
                
                # Log batch summary
                batch_summary = self._get_sync_summary(batch_results)
                logger.info(f"Batch completed: {batch_summary}")
            
            self.sync_results.extend(all_results)
            self.last_sync_time = datetime.now()
            
            # Log final summary
            final_summary = self._get_sync_summary(all_results)
            logger.info(f"Full sync completed: {final_summary}")
            
            return all_results
            
        except Exception as e:
            logger.error(f"Failed to sync all insights: {str(e)}")
            return []
    
    def sync_specific_contacts(self, 
                              contact_ids: List[str],
                              force_update: bool = False) -> List[SyncResult]:
        """
        Sync specific contacts to Airtable.
        
        Args:
            contact_ids: List of contact IDs to sync
            force_update: Force update even if recently synced
            
        Returns:
            List[SyncResult]: Results of sync operations
        """
        logger.info(f"Syncing {len(contact_ids)} specific contacts")
        
        results = []
        for contact_id in contact_ids:
            result = self.sync_contact_to_airtable(contact_id, force_update)
            results.append(result)
        
        self.sync_results.extend(results)
        
        summary = self._get_sync_summary(results)
        logger.info(f"Specific contacts sync completed: {summary}")
        
        return results
    
    def _should_skip_sync(self, insight: StructuredInsight) -> bool:
        """Check if we should skip syncing this insight."""
        # Skip if updated very recently (within 1 hour)
        if insight.updated_at:
            time_since_update = datetime.now() - insight.updated_at.replace(tzinfo=None)
            if time_since_update < timedelta(hours=1):
                return True
        
        return False
    
    def _convert_insight_to_airtable_format(self, insight: StructuredInsight) -> Dict[str, Any]:
        """Convert StructuredInsight to Airtable-compatible format."""
        # Extract the insights content from the JSON structure
        if hasattr(insight.insights, 'dict'):
            insights_dict = insight.insights.dict()
        elif isinstance(insight.insights, dict):
            insights_dict = insight.insights
        else:
            # If insights is a StructuredInsightContent object, extract its fields
            insights_dict = {
                'personal': getattr(insight.insights, 'personal', ''),
                'business': getattr(insight.insights, 'business', ''),
                'investing': getattr(insight.insights, 'investing', ''),
                '3i': getattr(insight.insights, 'three_i', ''),
                'deals': getattr(insight.insights, 'deals', ''),
                'introductions': getattr(insight.insights, 'introductions', '')
            }
        
        # Add metadata
        insights_dict.update({
            'metadata': {
                'contact_id': insight.metadata.contact_id,
                'eni_id': insight.metadata.eni_id,
                'member_name': insight.metadata.member_name,
                'generated_at': insight.metadata.generated_at.isoformat() if insight.metadata.generated_at else None,
                'version': insight.metadata.version,
                'record_count': insight.metadata.record_count,
                'total_eni_ids': insight.metadata.total_eni_ids
            }
        })
        
        return insights_dict
    
    def _get_sync_summary(self, results: List[SyncResult]) -> Dict[str, Any]:
        """Get summary of sync results."""
        if not results:
            return {'total': 0}
        
        summary = {
            'total': len(results),
            'successful': len([r for r in results if r.success]),
            'failed': len([r for r in results if not r.success]),
            'created': len([r for r in results if r.action == 'created']),
            'updated': len([r for r in results if r.action == 'updated']),
            'skipped': len([r for r in results if r.action == 'skipped']),
            'success_rate': len([r for r in results if r.success]) / len(results) if results else 0
        }
        
        return summary
    
    def get_sync_statistics(self) -> Dict[str, Any]:
        """Get comprehensive sync statistics."""
        recent_results = [r for r in self.sync_results if r.success]
        
        stats = {
            'last_sync_time': self.last_sync_time.isoformat() if self.last_sync_time else None,
            'sync_interval_hours': self.sync_interval_hours,
            'total_sync_attempts': len(self.sync_results),
            'recent_summary': self._get_sync_summary(self.sync_results[-100:]) if self.sync_results else {},
            'overall_summary': self._get_sync_summary(self.sync_results) if self.sync_results else {}
        }
        
        return stats
    
    def clear_sync_history(self) -> None:
        """Clear sync result history."""
        self.sync_results.clear()
        logger.info("Cleared sync history")


class SupabaseAirtableBridge:
    """
    Bridge between Supabase insights and Airtable.
    
    This class provides a high-level interface for managing the sync
    between Supabase and Airtable.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the bridge.
        
        Args:
            config: Configuration dictionary with Supabase and Airtable settings
        """
        self.config = config
        
        # Initialize clients
        self.supabase_client = SupabaseInsightsClient(
            **config.get('supabase', {})
        )
        
        self.airtable_writer = StructuredInsightsAirtableWriter(
            config.get('airtable', {})
        )
        
        # Initialize sync service
        sync_config = config.get('sync', {})
        self.sync_service = SupabaseAirtableSync(
            supabase_client=self.supabase_client,
            airtable_writer=self.airtable_writer,
            sync_interval_hours=sync_config.get('interval_hours', 24)
        )
        
        logger.info("Initialized SupabaseAirtableBridge")
    
    def sync_if_needed(self) -> bool:
        """
        Sync to Airtable if needed based on interval.
        
        Returns:
            bool: True if sync was performed
        """
        if not self.sync_service.last_sync_time:
            # Never synced before
            self.sync_service.sync_recent_insights()
            return True
        
        # Check if enough time has passed
        time_since_sync = datetime.now() - self.sync_service.last_sync_time
        if time_since_sync >= timedelta(hours=self.sync_service.sync_interval_hours):
            self.sync_service.sync_recent_insights()
            return True
        
        return False
    
    def force_sync_all(self) -> List[SyncResult]:
        """Force sync all insights to Airtable."""
        return self.sync_service.sync_all_insights(force_update=True)
    
    def sync_contact(self, contact_id: str) -> SyncResult:
        """Sync a specific contact."""
        return self.sync_service.sync_contact_to_airtable(contact_id, force_update=True)
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the bridge."""
        return {
            'supabase_connected': self.supabase_client.create_table_if_not_exists(),
            'airtable_connected': True,  # Assume connected if no error
            'last_sync': self.sync_service.last_sync_time,
            'sync_stats': self.sync_service.get_sync_statistics()
        }


def create_supabase_airtable_bridge(config: Dict[str, Any]) -> SupabaseAirtableBridge:
    """Create a Supabase-Airtable bridge with configuration."""
    return SupabaseAirtableBridge(config)


# Export main classes
__all__ = [
    'SupabaseAirtableSync',
    'SupabaseAirtableBridge',
    'SyncResult',
    'create_supabase_airtable_bridge'
] 