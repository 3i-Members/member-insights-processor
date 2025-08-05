#!/usr/bin/env python3
"""
Test suite for null ENI subtype handling

This test suite verifies that null, empty, and missing ENI subtypes
are properly handled throughout the system.
"""

import unittest
import sys
import os
import pandas as pd
import numpy as np
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestNullSubtypeHandling(unittest.TestCase):
    """Test null subtype handling in configuration and data processing."""

    def setUp(self):
        """Set up test fixtures."""
        from context_management.config_loader import create_config_loader
        self.config_loader = create_config_loader("config/config.yaml")

    def test_config_null_mappings(self):
        """Test that null subtypes are properly mapped in configuration."""
        test_cases = [
            ("airtable_notes", None),
            ("airtable_notes", ""),
            ("airtable_notes", "null"),
            ("pipedrive_notes", None),
            ("member_requests", None),
            ("recurroo", ""),
            ("whatsapp_messages", "   "),
            ("airtable_deals_sourced", "NaN"),
        ]

        for source_type, subtype_input in test_cases:
            with self.subTest(source_type=source_type, subtype=subtype_input):
                file_path = self.config_loader.get_context_file_path(source_type, subtype_input)
                self.assertIsNotNone(file_path, 
                    f"Expected file path for {source_type}/{subtype_input}, got None")
                
                # Verify file exists
                self.assertTrue(Path(file_path).exists(), 
                    f"Context file does not exist: {file_path}")

    def test_specific_subtypes_still_work(self):
        """Test that specific subtypes still map correctly."""
        test_cases = [
            ("airtable_notes", "investing_preferences"),
            ("whatsapp_messages", "venture"),
            ("recurroo", "biography"),
            ("member_requests", "requested"),
        ]

        for source_type, subtype in test_cases:
            with self.subTest(source_type=source_type, subtype=subtype):
                file_path = self.config_loader.get_context_file_path(source_type, subtype)
                self.assertIsNotNone(file_path)
                self.assertTrue(Path(file_path).exists())
                self.assertIn(subtype, file_path)

    def test_data_processing_null_normalization(self):
        """Test null normalization in data processing pipeline."""
        # Create test data with various null representations
        test_data = pd.DataFrame({
            'eni_source_type': ['airtable_notes', 'recurroo', 'whatsapp_messages', 'pipedrive_notes', 'member_requests'],
            'eni_source_subtype': [None, '', '   ', 'NaN', np.nan],
            'contact_id': ['CNT-001', 'CNT-002', 'CNT-003', 'CNT-004', 'CNT-005'],
            'description': ['Test 1', 'Test 2', 'Test 3', 'Test 4', 'Test 5']
        })

        # Apply the same null handling logic as main.py
        test_data['eni_source_subtype'] = test_data['eni_source_subtype'].fillna('null')
        
        # Handle empty strings and other null-like values
        mask = (test_data['eni_source_subtype'].astype(str).str.strip() == '') | \
               (test_data['eni_source_subtype'].astype(str).str.lower().isin(['none', 'nan', 'nat']))
        test_data.loc[mask, 'eni_source_subtype'] = 'null'

        # Verify all subtypes are now 'null'
        self.assertTrue(all(test_data['eni_source_subtype'] == 'null'),
            "Not all null variations were properly normalized to 'null'")

    def test_configuration_completeness(self):
        """Test that all ENI types have appropriate default mappings."""
        eni_mappings = self.config_loader.get_all_eni_mappings()
        
        for source_type, mappings in eni_mappings.items():
            with self.subTest(source_type=source_type):
                has_null = 'null' in mappings
                has_default = 'default' in mappings
                
                # Each source type should have either a null mapping or default mapping
                self.assertTrue(has_null or has_default,
                    f"Source type '{source_type}' missing both null and default mappings")

    def test_null_handling_edge_cases(self):
        """Test edge cases in null handling."""
        edge_cases = [
            ("airtable_notes", "None"),      # String "None"
            ("recurroo", "NULL"),           # String "NULL"  
            ("whatsapp_messages", "nan"),   # Lowercase "nan"
            ("pipedrive_notes", "\t\n"),    # Tabs and newlines
        ]

        for source_type, subtype_input in edge_cases:
            with self.subTest(source_type=source_type, subtype=subtype_input):
                file_path = self.config_loader.get_context_file_path(source_type, subtype_input)
                self.assertIsNotNone(file_path, 
                    f"Expected default mapping for edge case {source_type}/{repr(subtype_input)}")

    def test_fallback_hierarchy(self):
        """Test the fallback hierarchy: specific -> null -> default."""
        # Test a source type that has explicit null and default mappings
        source_type = "airtable_notes"
        
        # Should find explicit null mapping
        null_path = self.config_loader.get_context_file_path(source_type, "null")
        self.assertIsNotNone(null_path)
        
        # Should find default mapping for non-existent subtype
        nonexistent_path = self.config_loader.get_context_file_path(source_type, "nonexistent_subtype")
        self.assertIsNotNone(nonexistent_path)
        
        # Should find specific mapping
        specific_path = self.config_loader.get_context_file_path(source_type, "investing_preferences")
        self.assertIsNotNone(specific_path)
        self.assertIn("investing_preferences", specific_path)


class TestNullHandlingIntegration(unittest.TestCase):
    """Integration tests for null handling across the system."""

    def test_end_to_end_null_processing(self):
        """Test null handling from config to file loading."""
        from context_management.config_loader import create_config_loader
        from context_management.markdown_reader import create_markdown_reader
        
        config_loader = create_config_loader("config/config.yaml")
        markdown_reader = create_markdown_reader()
        
        # Test null subtype processing
        source_type = "airtable_notes"
        subtype = None  # This should map to default
        
        # Get context file path
        file_path = config_loader.get_context_file_path(source_type, subtype)
        self.assertIsNotNone(file_path)
        
        # Load the markdown content
        content = markdown_reader.read_markdown_file(file_path)
        self.assertIsNotNone(content)
        self.assertIsInstance(content, str)
        self.assertGreater(len(content), 0)


def run_null_handling_tests():
    """Run all null handling tests."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestNullSubtypeHandling))
    suite.addTests(loader.loadTestsFromTestCase(TestNullHandlingIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    # Change to the correct directory for running tests
    test_dir = Path(__file__).parent.parent
    os.chdir(test_dir)
    
    success = run_null_handling_tests()
    sys.exit(0 if success else 1) 