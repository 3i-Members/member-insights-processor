"""
Tests for Supabase Integration.

This module contains comprehensive tests for the Supabase client, schema validation,
and processing pipeline.
"""

import pytest
import json
import os
from datetime import datetime
from typing import Dict, Any
from unittest.mock import Mock, patch, MagicMock

# Import modules to test
from src.data_processing.schema import (
    StructuredInsight,
    InsightMetadata,
    StructuredInsightContent,
    ProcessingStatus,
    LegacyInsightData,
    is_valid_contact_id,
    is_valid_eni_id,
    validate_structured_insight_json,
    normalize_insight_data
)

from src.data_processing.supabase_client import (
    SupabaseInsightsClient,
    SupabaseConnectionError,
    SupabaseOperationError
)

from src.data_processing.supabase_insights_processor import (
    SupabaseInsightsProcessor,
    MemoryManager,
    ProcessingState
)


class TestSchemaValidation:
    """Test schema validation and data models."""
    
    def test_contact_id_validation(self):
        """Test contact ID validation."""
        # Valid contact IDs
        assert is_valid_contact_id("CNT-c9M007641")
        assert is_valid_contact_id("CNT-ABC123DEF")
        assert is_valid_contact_id("CNT-123456789")
        
        # Invalid contact IDs
        assert not is_valid_contact_id("ABC-123456")  # Wrong prefix
        assert not is_valid_contact_id("CNT-123")     # Too short
        assert not is_valid_contact_id("CNT-")        # Missing suffix
        assert not is_valid_contact_id("")            # Empty
        assert not is_valid_contact_id(None)          # None
    
    def test_eni_id_validation(self):
        """Test ENI ID validation."""
        # Valid ENI IDs
        assert is_valid_eni_id("ENI-123456789")
        assert is_valid_eni_id("COMBINED-CNT-c9M007641-9ENI")
        
        # Invalid ENI IDs
        assert not is_valid_eni_id("ABC-123456")      # Wrong format
        assert not is_valid_eni_id("ENI-")            # Missing number
        assert not is_valid_eni_id("")                # Empty
        assert not is_valid_eni_id(None)              # None
    
    def test_insight_metadata_creation(self):
        """Test InsightMetadata creation and validation."""
        metadata = InsightMetadata(
            contact_id="CNT-c9M007641",
            eni_id="ENI-123456789",
            member_name="Test Member"
        )
        
        assert metadata.contact_id == "CNT-c9M007641"
        assert metadata.eni_id == "ENI-123456789"
        assert metadata.member_name == "Test Member"
        assert metadata.processing_status == ProcessingStatus.COMPLETED
        assert metadata.version == 1
    
    def test_structured_insight_content_creation(self):
        """Test StructuredInsightContent creation."""
        content = StructuredInsightContent(
            personal="* Test personal info\n  * [2024-01-01,ENI-123]",
            business="* Test business info\n  * [2024-01-01,ENI-456]",
            investing="* Test investing info\n  * [2024-01-01,ENI-789]"
        )
        
        assert content.personal is not None
        assert content.business is not None
        assert content.investing is not None
        
        # Test citation extraction
        citations = content.extract_citations(content.personal)
        assert len(citations) == 1
        assert citations[0] == ("2024-01-01", "ENI-123")
    
    def test_structured_insight_creation(self):
        """Test complete StructuredInsight creation."""
        metadata = InsightMetadata(
            contact_id="CNT-c9M007641",
            eni_id="ENI-123456789"
        )
        
        content = StructuredInsightContent(
            personal="Test personal info",
            business="Test business info"
        )
        
        insight = StructuredInsight(
            metadata=metadata,
            insights=content
        )
        
        assert insight.metadata.contact_id == "CNT-c9M007641"
        assert insight.personal == "Test personal info"
        assert insight.business == "Test business info"
    
    def test_legacy_data_conversion(self):
        """Test conversion from legacy data format."""
        legacy_data = {
            "metadata": {
                "contact_id": "CNT-c9M007641",
                "eni_id": "ENI-123456789",
                "generated_at": "2024-01-01T12:00:00"
            },
            "insights": {
                "personal": "Test personal",
                "business": "Test business"
            }
        }
        
        legacy_insight = LegacyInsightData(**legacy_data)
        structured_insight = legacy_insight.to_structured_insight()
        
        assert structured_insight.metadata.contact_id == "CNT-c9M007641"
        assert structured_insight.personal == "Test personal"
        assert structured_insight.business == "Test business"
    
    def test_json_validation(self):
        """Test JSON validation function."""
        # Valid new format
        valid_new_data = {
            "metadata": {
                "contact_id": "CNT-c9M007641",
                "eni_id": "ENI-123456789"
            },
            "insights": {
                "personal": "Test personal"
            }
        }
        
        is_valid, errors = validate_structured_insight_json(valid_new_data)
        assert is_valid
        assert len(errors) == 0
        
        # Invalid data
        invalid_data = {
            "metadata": {
                "contact_id": "INVALID-ID"  # Invalid format
            },
            "insights": {}
        }
        
        is_valid, errors = validate_structured_insight_json(invalid_data)
        assert not is_valid
        assert len(errors) > 0


class TestMemoryManager:
    """Test memory management functionality."""
    
    def test_memory_manager_basic_operations(self):
        """Test basic memory manager operations."""
        manager = MemoryManager(max_items=3)
        
        # Add items
        manager.add_item("key1", "value1")
        manager.add_item("key2", "value2")
        manager.add_item("key3", "value3")
        
        assert manager.get_item("key1") == "value1"
        assert manager.get_item("key2") == "value2"
        assert manager.get_item("key3") == "value3"
        
        # Test eviction
        manager.add_item("key4", "value4")  # Should evict key1
        assert manager.get_item("key1") is None
        assert manager.get_item("key4") == "value4"
    
    def test_memory_manager_stats(self):
        """Test memory manager statistics."""
        manager = MemoryManager(max_items=5)
        manager.add_item("key1", "value1")
        manager.add_item("key2", "value2")
        
        stats = manager.get_stats()
        assert stats['cached_items'] == 2
        assert stats['max_items'] == 5
        assert stats['use_weak_references'] == True


class TestProcessingState:
    """Test processing state tracking."""
    
    def test_processing_state_tracking(self):
        """Test processing state operations."""
        state = ProcessingState()
        
        # Mark successful processing
        state.mark_processed("CNT-123", was_created=True)
        state.mark_processed("CNT-456", was_created=False)
        
        # Mark failures
        state.mark_failed("CNT-789", "Test error")
        
        # Finalize and get summary
        state.finalize()
        summary = state.get_summary()
        
        assert summary['total_processed'] == 2
        assert summary['created'] == 1
        assert summary['updated'] == 1
        assert summary['failed'] == 1
        assert "CNT-789" in summary['errors']


@pytest.fixture
def mock_supabase_client():
    """Create a mock Supabase client for testing."""
    client = Mock(spec=SupabaseInsightsClient)
    
    # Mock table existence check
    client.create_table_if_not_exists.return_value = True
    
    # Mock insight retrieval
    client.get_insight_by_contact_id.return_value = None
    client.get_insight_by_contact_and_eni.return_value = None
    
    # Mock upsert
    def mock_upsert(insight):
        insight.id = "test-uuid"
        return insight, True
    
    client.upsert_insight.side_effect = mock_upsert
    
    return client


class TestSupabaseInsightsProcessor:
    """Test the main insights processor."""
    
    def test_processor_initialization(self, mock_supabase_client):
        """Test processor initialization."""
        processor = SupabaseInsightsProcessor(
            supabase_client=mock_supabase_client,
            batch_size=5
        )
        
        assert processor.batch_size == 5
        assert processor.enable_memory_optimization == True
        assert processor.memory_manager is not None
    
    def test_load_existing_insight_with_cache(self, mock_supabase_client):
        """Test loading existing insights with caching."""
        processor = SupabaseInsightsProcessor(mock_supabase_client)
        
        # First call should hit Supabase
        result1 = processor.load_existing_insight("CNT-123")
        assert mock_supabase_client.get_insight_by_contact_id.called
        
        # Reset mock and call again - should use cache
        mock_supabase_client.reset_mock()
        result2 = processor.load_existing_insight("CNT-123")
        assert not mock_supabase_client.get_insight_by_contact_id.called
    
    def test_process_single_insight(self, mock_supabase_client):
        """Test processing a single insight."""
        processor = SupabaseInsightsProcessor(mock_supabase_client)
        
        content = StructuredInsightContent(
            personal="Test personal info",
            business="Test business info"
        )
        
        metadata = {
            "member_name": "Test Member",
            "eni_source_type": "test_type"
        }
        
        result_insight, was_created = processor.process_insight(
            contact_id="CNT-123",
            eni_id="ENI-456",
            insight_content=content,
            metadata=metadata
        )
        
        assert result_insight is not None
        assert was_created == True
        assert mock_supabase_client.upsert_insight.called
    
    def test_batch_processing(self, mock_supabase_client):
        """Test batch processing of insights."""
        processor = SupabaseInsightsProcessor(
            mock_supabase_client,
            batch_size=2
        )
        
        insights_data = [
            {
                "contact_id": "CNT-123",
                "eni_id": "ENI-456",
                "insights": {
                    "personal": "Test personal 1"
                },
                "member_name": "Member 1"
            },
            {
                "contact_id": "CNT-789",
                "eni_id": "ENI-012",
                "insights": {
                    "personal": "Test personal 2"
                },
                "member_name": "Member 2"
            }
        ]
        
        state = processor.batch_process_insights(insights_data)
        
        assert state.get_summary()['total_processed'] == 2
        assert state.get_summary()['created'] == 2
        assert state.get_summary()['failed'] == 0
    
    def test_processing_statistics(self, mock_supabase_client):
        """Test getting processing statistics."""
        mock_supabase_client.get_insights_count.return_value = 42
        
        processor = SupabaseInsightsProcessor(mock_supabase_client)
        stats = processor.get_processing_statistics()
        
        assert 'memory_stats' in stats
        assert 'supabase_table_exists' in stats
        assert stats['total_insights_in_db'] == 42


class TestIntegrationWithRealData:
    """Test integration with real data samples."""
    
    def test_real_json_sample_parsing(self):
        """Test parsing real JSON sample from the codebase."""
        # Use the actual sample data from the codebase
        sample_data = {
            "metadata": {
                "contact_id": "CNT-c9M007641",
                "eni_id": "COMBINED-CNT-c9M007641-9ENI",
                "member_name": None,
                "eni_source_type": None,
                "eni_source_subtype": None,
                "generated_at": "2025-08-05T18:13:46.023414",
                "generator": "structured_insight",
                "eni_source_types": ["airtable_notes", "recurroo"],
                "eni_source_subtypes": ["social", "asset_class", "intro_preferences", "null", "biography", "sector"],
                "system_prompt_key": "structured_insight",
                "context_files": "combined_all_eni_groups",
                "record_count": 9,
                "total_eni_ids": 9
            },
            "insights": {
                "raw_content": "Sample content with JSON structure..."
            }
        }
        
        # Test validation
        is_valid, errors = validate_structured_insight_json(sample_data)
        assert is_valid, f"Validation errors: {errors}"
        
        # Test normalization
        normalized = normalize_insight_data(sample_data)
        assert normalized.metadata.contact_id == "CNT-c9M007641"
        assert normalized.metadata.record_count == 9
    
    def test_database_dict_conversion(self):
        """Test conversion to and from database dictionary format."""
        # Create a structured insight
        metadata = InsightMetadata(
            contact_id="CNT-c9M007641",
            eni_id="ENI-123456789",
            member_name="Test Member",
            eni_source_types=["type1", "type2"],
            record_count=5
        )
        
        content = StructuredInsightContent(
            personal="Test personal info",
            business="Test business info"
        )
        
        insight = StructuredInsight(
            metadata=metadata,
            insights=content
        )
        
        # Convert to database format
        db_dict = insight.to_db_dict()
        
        assert db_dict['contact_id'] == "CNT-c9M007641"
        assert db_dict['eni_id'] == "ENI-123456789"
        assert db_dict['member_name'] == "Test Member"
        assert db_dict['eni_source_types'] == ["type1", "type2"]
        assert db_dict['record_count'] == 5
        assert 'insights' in db_dict
        assert db_dict['personal'] == "Test personal info"
        
        # Convert back from database format
        restored_insight = StructuredInsight.from_db_dict(db_dict)
        
        assert restored_insight.metadata.contact_id == "CNT-c9M007641"
        assert restored_insight.metadata.member_name == "Test Member"
        assert restored_insight.personal == "Test personal info"


@pytest.fixture
def sample_processing_data():
    """Create sample processing data for tests."""
    return [
        {
            "contact_id": "CNT-sample001",
            "eni_id": "ENI-123456789",
            "insights": {
                "personal": "* Sample personal info\n  * [2024-01-01,ENI-123456789]",
                "business": "* Sample business info\n  * [2024-01-01,ENI-123456789]"
            },
            "member_name": "Sample Member 1",
            "eni_source_type": "sample_type",
            "record_count": 3
        },
        {
            "contact_id": "CNT-sample002", 
            "eni_id": "ENI-987654321",
            "insights": {
                "investing": "* Sample investing info\n  * [2024-01-02,ENI-987654321]"
            },
            "member_name": "Sample Member 2",
            "eni_source_type": "sample_type",
            "record_count": 1
        }
    ]


class TestEndToEndProcessing:
    """Test end-to-end processing scenarios."""
    
    def test_complete_processing_workflow(self, mock_supabase_client, sample_processing_data):
        """Test complete processing workflow from data to Supabase."""
        processor = SupabaseInsightsProcessor(
            mock_supabase_client,
            batch_size=1
        )
        
        # Process the sample data
        state = processor.batch_process_insights(sample_processing_data)
        
        # Verify results
        summary = state.get_summary()
        assert summary['total_processed'] == 2
        assert summary['created'] == 2
        assert summary['failed'] == 0
        
        # Verify Supabase calls
        assert mock_supabase_client.upsert_insight.call_count == 2
        
    def test_error_handling_in_batch_processing(self, mock_supabase_client):
        """Test error handling during batch processing."""
        # Configure mock to raise an error
        mock_supabase_client.upsert_insight.side_effect = SupabaseOperationError("Test error")
        
        processor = SupabaseInsightsProcessor(mock_supabase_client)
        
        invalid_data = [{
            "contact_id": "CNT-error001",
            "eni_id": "ENI-123",
            "insights": {"personal": "Test"},
            "member_name": "Error Member"
        }]
        
        state = processor.batch_process_insights(invalid_data)
        
        # Should have failed gracefully
        summary = state.get_summary()
        assert summary['failed'] == 1
        assert "CNT-error001" in summary['errors']


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__, "-v"]) 