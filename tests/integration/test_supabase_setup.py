"""
Test Supabase Setup and Configuration.

This module contains tests to validate the Supabase setup, table creation,
and basic connectivity.
"""

import pytest
import os
from unittest.mock import patch, Mock
from datetime import datetime

from src.data_processing.supabase_client import (
    SupabaseInsightsClient,
    SupabaseConnectionError,
    SupabaseOperationError
)
from src.data_processing.schema import (
    StructuredInsight,
    InsightMetadata,
    StructuredInsightContent
)


class TestSupabaseSetup:
    """Test Supabase setup and configuration."""
    
    def test_environment_variables_validation(self):
        """Test that required environment variables are validated."""
        with patch.dict(os.environ, {}, clear=True):
            # Should raise error when env vars are missing
            with pytest.raises(SupabaseConnectionError):
                SupabaseInsightsClient()
    
    def test_client_initialization_with_params(self):
        """Test client initialization with explicit parameters."""
        with patch('src.data_processing.supabase_client.create_client') as mock_create:
            mock_client = Mock()
            mock_create.return_value = mock_client
            
            # Mock the health check
            mock_client.table.return_value.select.return_value.limit.return_value.execute.return_value = Mock()
            
            client = SupabaseInsightsClient(
                supabase_url="https://test.supabase.co",
                supabase_key="test-key"
            )
            
            assert client.supabase_url == "https://test.supabase.co"
            assert client.supabase_key == "test-key"
            assert client.TABLE_NAME == "elvis__structured_insights"
    
    @patch('src.data_processing.supabase_client.create_client')
    def test_health_check_functionality(self, mock_create):
        """Test health check functionality."""
        mock_client = Mock()
        mock_create.return_value = mock_client
        
        # Mock successful health check
        mock_client.table.return_value.select.return_value.limit.return_value.execute.return_value = Mock()
        
        client = SupabaseInsightsClient(
            supabase_url="https://test.supabase.co",
            supabase_key="test-key"
        )
        
        # Health check should pass
        assert client._health_check() == True
        
        # Mock failed health check
        mock_client.table.return_value.select.return_value.limit.return_value.execute.side_effect = Exception("Connection failed")
        
        assert client._health_check() == False


class TestTableOperations:
    """Test table operations and CRUD functionality."""
    
    @patch('src.data_processing.supabase_client.create_client')
    def test_table_existence_check(self, mock_create):
        """Test table existence validation."""
        mock_client = Mock()
        mock_create.return_value = mock_client
        
        # Mock table exists
        mock_client.table.return_value.select.return_value.limit.return_value.execute.return_value = Mock()
        
        client = SupabaseInsightsClient(
            supabase_url="https://test.supabase.co",
            supabase_key="test-key"
        )
        
        assert client.create_table_if_not_exists() == True
        
        # Mock table doesn't exist
        mock_client.table.return_value.select.return_value.limit.return_value.execute.side_effect = Exception("Table not found")
        
        assert client.create_table_if_not_exists() == False
    
    @patch('src.data_processing.supabase_client.create_client')
    def test_insight_creation_flow(self, mock_create):
        """Test the complete insight creation flow."""
        mock_client = Mock()
        mock_create.return_value = mock_client
        
        # Mock successful operations
        mock_client.table.return_value.select.return_value.limit.return_value.execute.return_value = Mock()
        mock_client.table.return_value.insert.return_value.execute.return_value.data = [{
            'id': '550e8400-e29b-41d4-a716-446655440000',
            'contact_id': 'CNT-test123',
            'eni_id': 'ENI-test456',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'insights': {'personal': 'Test personal info'}
        }]
        
        client = SupabaseInsightsClient(
            supabase_url="https://test.supabase.co",
            supabase_key="test-key"
        )
        
        # Create test insight
        metadata = InsightMetadata(
            contact_id="CNT-test123",
            eni_id="ENI-test456"
        )
        content = StructuredInsightContent(personal="Test personal info")
        insight = StructuredInsight(metadata=metadata, insights=content)
        
        # Should not raise an exception
        result = client.create_insight(insight)
        assert result.metadata.contact_id == "CNT-test123"


class TestSchemaCompatibility:
    """Test schema compatibility with existing data."""
    
    def test_legacy_json_compatibility(self):
        """Test compatibility with legacy JSON structure."""
        from src.data_processing.schema import normalize_insight_data
        
        # Test with the actual legacy format from the codebase
        legacy_data = {
            "metadata": {
                "contact_id": "CNT-c9M007641",
                "eni_id": "COMBINED-CNT-c9M007641-9ENI",
                "member_name": None,
                "eni_source_type": None,
                "eni_source_subtype": None,
                "generated_at": "2025-08-05T18:13:46.023414",
                "generator": "structured_insight",
                "eni_source_types": ["airtable_notes", "recurroo"],
                "eni_source_subtypes": ["social", "asset_class"],
                "system_prompt_key": "structured_insight",
                "context_files": "combined_all_eni_groups",
                "record_count": 9,
                "total_eni_ids": 9
            },
            "insights": {
                "raw_content": "Test content"
            }
        }
        
        # Should normalize without errors
        normalized = normalize_insight_data(legacy_data)
        assert normalized.metadata.contact_id == "CNT-c9M007641"
        assert normalized.metadata.record_count == 9
    
    def test_new_format_compatibility(self):
        """Test compatibility with new structured format."""
        from src.data_processing.schema import normalize_insight_data
        
        new_data = {
            "metadata": {
                "contact_id": "CNT-new123",
                "eni_id": "ENI-new456"
            },
            "insights": {
                "personal": "New personal info",
                "business": "New business info"
            }
        }
        
        # Should normalize without errors
        normalized = normalize_insight_data(new_data)
        assert normalized.metadata.contact_id == "CNT-new123"
        assert normalized.insights.personal == "New personal info"


class TestConfigurationValidation:
    """Test configuration file validation."""
    
    def test_yaml_config_structure(self):
        """Test that YAML config has required Supabase settings."""
        import yaml
        
        config_path = "config/config.yaml"
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Check for Supabase section
            assert 'supabase' in config
            assert 'table_name' in config['supabase']
            assert 'max_retries' in config['supabase']
            assert 'batch_size' in config['supabase']
            
            # Check for processing settings
            assert 'processing' in config
            assert 'enable_supabase_storage' in config['features']
            
        except FileNotFoundError:
            pytest.skip("Config file not found - this is expected in some test environments")


class TestRetryLogic:
    """Test retry logic and error handling."""
    
    @patch('src.data_processing.supabase_client.create_client')
    def test_retry_on_failure_decorator(self, mock_create):
        """Test retry logic for failed operations."""
        mock_client = Mock()
        mock_create.return_value = mock_client
        
        # Setup: Health check succeeds first time
        mock_client.table.return_value.select.return_value.limit.return_value.execute.return_value = Mock()
        
        client = SupabaseInsightsClient(
            supabase_url="https://test.supabase.co",
            supabase_key="test-key"
        )
        
        # Mock insert to fail twice then succeed
        mock_client.table.return_value.insert.return_value.execute.side_effect = [
            Exception("Network error"),
            Exception("Timeout error"),
            Mock(data=[{'id': '550e8400-e29b-41d4-a716-446655440001', 'contact_id': 'CNT-test'}])
        ]
        
        # Create test insight
        metadata = InsightMetadata(contact_id="CNT-test123")
        content = StructuredInsightContent(personal="Test")
        insight = StructuredInsight(metadata=metadata, insights=content)
        
        # Should succeed after retries
        result = client.create_insight(insight)
        assert result is not None
        
        # Verify it tried 3 times
        assert mock_client.table.return_value.insert.return_value.execute.call_count == 3


if __name__ == "__main__":
    # Run specific setup tests
    pytest.main([__file__, "-v", "-k", "TestSupabaseSetup or TestSchemaCompatibility"]) 