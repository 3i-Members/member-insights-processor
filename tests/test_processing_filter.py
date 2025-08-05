#!/usr/bin/env python3
"""
Test suite for processing filter functionality

This test suite verifies that the processing filter correctly filters
ENI records based on type and subtype rules.
"""

import unittest
import sys
import os
import tempfile
import shutil
import pandas as pd
import yaml
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestProcessingFilter(unittest.TestCase):
    """Test processing filter functionality."""

    def setUp(self):
        """Set up test fixtures."""
        from context_management.processing_filter import create_processing_filter
        
        # Create temporary directory for test files
        self.temp_dir = Path(tempfile.mkdtemp())
        
        # Create test filter configuration
        self.test_filter_config = {
            'filter_info': {
                'name': 'test_filter',
                'description': 'Test processing filter',
                'version': '1.0'
            },
            'eni_processing_rules': {
                'airtable_notes': 'all',
                'recurroo': 'all',
                'whatsapp_messages': ['venture', 'needs_leads'],
                'member_requests': ['requested'],
                'pipedrive_notes': 'none'
            },
            'processing_settings': {
                'log_skipped_records': True,
                'show_processing_stats': True,
                'validate_subtypes': True
            }
        }
        
        # Write test filter config to file
        self.filter_file = self.temp_dir / 'test_filter.yaml'
        with open(self.filter_file, 'w') as f:
            yaml.dump(self.test_filter_config, f)
        
        # Create processing filter
        self.processing_filter = create_processing_filter(str(self.filter_file))

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    def test_filter_initialization(self):
        """Test that the filter initializes correctly."""
        self.assertIsNotNone(self.processing_filter)
        self.assertEqual(len(self.processing_filter.processing_rules), 5)
        self.assertEqual(self.processing_filter.processing_rules['airtable_notes'], 'all')
        self.assertEqual(self.processing_filter.processing_rules['whatsapp_messages'], ['venture', 'needs_leads'])

    def test_should_process_record_all_rule(self):
        """Test 'all' rule processing."""
        # Should process all subtypes for airtable_notes
        self.assertTrue(self.processing_filter.should_process_record('airtable_notes', 'investing_preferences'))
        self.assertTrue(self.processing_filter.should_process_record('airtable_notes', 'intro_preferences'))
        self.assertTrue(self.processing_filter.should_process_record('airtable_notes', 'null'))
        self.assertTrue(self.processing_filter.should_process_record('airtable_notes', None))

    def test_should_process_record_list_rule(self):
        """Test list of specific subtypes rule."""
        # Should only process specified subtypes for whatsapp_messages
        self.assertTrue(self.processing_filter.should_process_record('whatsapp_messages', 'venture'))
        self.assertTrue(self.processing_filter.should_process_record('whatsapp_messages', 'needs_leads'))
        self.assertFalse(self.processing_filter.should_process_record('whatsapp_messages', 'blockchain'))
        self.assertFalse(self.processing_filter.should_process_record('whatsapp_messages', 'travel'))

    def test_should_process_record_none_rule(self):
        """Test 'none' rule processing."""
        # Should not process any subtypes for pipedrive_notes
        self.assertFalse(self.processing_filter.should_process_record('pipedrive_notes', 'any_subtype'))
        self.assertFalse(self.processing_filter.should_process_record('pipedrive_notes', 'null'))

    def test_should_process_record_unknown_type(self):
        """Test handling of unknown ENI types."""
        # Should not process unknown ENI types
        self.assertFalse(self.processing_filter.should_process_record('unknown_type', 'any_subtype'))

    def test_null_subtype_handling(self):
        """Test handling of various null subtype representations."""
        # Test various null representations for member_requests (which allows only 'requested')
        self.assertFalse(self.processing_filter.should_process_record('member_requests', None))
        self.assertFalse(self.processing_filter.should_process_record('member_requests', ''))
        self.assertFalse(self.processing_filter.should_process_record('member_requests', '   '))
        self.assertFalse(self.processing_filter.should_process_record('member_requests', 'NaN'))
        self.assertFalse(self.processing_filter.should_process_record('member_requests', 'none'))
        
        # Should process 'requested'
        self.assertTrue(self.processing_filter.should_process_record('member_requests', 'requested'))

    def test_filter_dataframe(self):
        """Test filtering a complete DataFrame."""
        # Create test DataFrame
        test_data = pd.DataFrame({
            'eni_source_type': [
                'airtable_notes', 'airtable_notes', 'whatsapp_messages', 
                'whatsapp_messages', 'whatsapp_messages', 'member_requests',
                'member_requests', 'pipedrive_notes', 'unknown_type'
            ],
            'eni_source_subtype': [
                'investing_preferences', 'intro_preferences', 'venture',
                'needs_leads', 'blockchain', 'requested',
                'responded', 'some_note', 'some_subtype'
            ],
            'description': ['desc1', 'desc2', 'desc3', 'desc4', 'desc5', 'desc6', 'desc7', 'desc8', 'desc9'],
            'contact_id': ['CNT-001'] * 9
        })

        # Apply filter
        filtered_df, stats = self.processing_filter.filter_dataframe(test_data)

        # Check results
        self.assertEqual(stats['original_count'], 9)
        self.assertEqual(stats['filtered_count'], 5)  # Should keep 5 records
        self.assertEqual(stats['skipped_count'], 4)   # Should skip 4 records

        # Check which records were kept
        expected_kept = [
            ('airtable_notes', 'investing_preferences'),
            ('airtable_notes', 'intro_preferences'),
            ('whatsapp_messages', 'venture'),
            ('whatsapp_messages', 'needs_leads'),
            ('member_requests', 'requested')
        ]
        
        actual_kept = list(zip(filtered_df['eni_source_type'], filtered_df['eni_source_subtype']))
        self.assertEqual(len(actual_kept), len(expected_kept))
        
        for expected in expected_kept:
            self.assertIn(expected, actual_kept)

    def test_get_allowed_eni_types(self):
        """Test getting allowed ENI types."""
        allowed_types = self.processing_filter.get_allowed_eni_types()
        expected_types = {'airtable_notes', 'recurroo', 'whatsapp_messages', 'member_requests', 'pipedrive_notes'}
        self.assertEqual(allowed_types, expected_types)

    def test_get_allowed_subtypes_for_type(self):
        """Test getting allowed subtypes for specific ENI types."""
        # Test 'all' rule
        self.assertEqual(self.processing_filter.get_allowed_subtypes_for_type('airtable_notes'), 'all')
        
        # Test list rule
        self.assertEqual(self.processing_filter.get_allowed_subtypes_for_type('whatsapp_messages'), ['venture', 'needs_leads'])
        
        # Test unknown type
        self.assertIsNone(self.processing_filter.get_allowed_subtypes_for_type('unknown_type'))

    def test_validate_filter_against_data(self):
        """Test validation of filter against actual data."""
        # Create test data that matches and doesn't match filter
        test_data = pd.DataFrame({
            'eni_source_type': [
                'airtable_notes', 'whatsapp_messages', 'whatsapp_messages',
                'member_requests', 'new_eni_type'
            ],
            'eni_source_subtype': [
                'investing_preferences', 'venture', 'unknown_subtype',
                'requested', 'some_subtype'
            ]
        })

        validation = self.processing_filter.validate_filter_against_data(test_data)
        
        self.assertTrue(validation['valid'])
        self.assertIn('Data types not configured for processing', str(validation['warnings']))
        self.assertGreater(validation['statistics']['filter_coverage_percent'], 0)

    def test_get_filter_summary(self):
        """Test getting filter summary."""
        summary = self.processing_filter.get_filter_summary()
        
        self.assertEqual(summary['total_eni_types'], 5)
        self.assertIn('airtable_notes', summary['processing_rules_summary'])
        self.assertEqual(summary['processing_rules_summary']['airtable_notes'], 'All subtypes')
        self.assertIn('venture', summary['processing_rules_summary']['whatsapp_messages'])

    def test_empty_dataframe_filtering(self):
        """Test filtering an empty DataFrame."""
        empty_df = pd.DataFrame(columns=['eni_source_type', 'eni_source_subtype'])
        filtered_df, stats = self.processing_filter.filter_dataframe(empty_df)
        
        self.assertTrue(filtered_df.empty)
        self.assertEqual(stats['original_count'], 0)
        self.assertEqual(stats['filtered_count'], 0)
        self.assertEqual(stats['skipped_count'], 0)


class TestProcessingFilterIntegration(unittest.TestCase):
    """Integration tests for processing filter with main system."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    def test_config_loader_integration(self):
        """Test processing filter integration with config loader."""
        from context_management.config_loader import create_config_loader
        
        # Create test configuration
        test_config = {
            'processing': {
                'filter_config': {
                    'default_filter_file': 'config/processing_filters.yaml',
                    'strict_filtering': True,
                    'log_filtered_records': True
                }
            }
        }
        
        config_file = self.temp_dir / 'test_config.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(test_config, f)
        
        config_loader = create_config_loader(str(config_file))
        
        # Test filter config methods
        filter_config = config_loader.get_filter_config()
        self.assertIn('default_filter_file', filter_config)
        self.assertEqual(filter_config['strict_filtering'], True)
        
        default_filter_file = config_loader.get_default_filter_file()
        self.assertEqual(default_filter_file, 'config/processing_filters.yaml')

    def test_main_processor_integration(self):
        """Test that main processor can be initialized with filter."""
        # This is a light integration test since full initialization requires external dependencies
        from context_management.processing_filter import ProcessingFilter
        
        # Create minimal filter config
        filter_config = {
            'eni_processing_rules': {'test_type': 'all'},
            'processing_settings': {}
        }
        
        filter_file = self.temp_dir / 'minimal_filter.yaml'
        with open(filter_file, 'w') as f:
            yaml.dump(filter_config, f)
        
        # Test that ProcessingFilter can be created
        processing_filter = ProcessingFilter(str(filter_file))
        self.assertIsNotNone(processing_filter)
        self.assertIn('test_type', processing_filter.processing_rules)


def run_processing_filter_tests():
    """Run all processing filter tests."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestProcessingFilter))
    suite.addTests(loader.loadTestsFromTestCase(TestProcessingFilterIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    # Change to the correct directory for running tests
    test_dir = Path(__file__).parent.parent
    os.chdir(test_dir)
    
    success = run_processing_filter_tests()
    sys.exit(0 if success else 1) 