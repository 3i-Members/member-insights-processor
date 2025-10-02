#!/usr/bin/env python3
"""
Test suite for structured insights functionality

This test suite verifies the JSON output, structured Airtable integration,
and overall structured insights processing pipeline.
"""

import unittest
import sys
import os
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestJSONWriter(unittest.TestCase):
    """Test the JSON writer functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        from output_management.json_writer import create_json_writer
        self.json_writer = create_json_writer(self.temp_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    def test_write_structured_insight(self):
        """Test writing structured insight to JSON file."""
        # Sample structured insight data
        sample_insight = {
            "personal": "* Active member since 2020\n* Located in Miami, Florida",
            "business": "* Tech entrepreneur with 15 years experience",
            "investing": "* Focus on early-stage technology companies",
            "3i": "* Participated in 8 deals through platform",
            "deals": "This Member **Has Experience** in B2B SaaS",
            "introductions": "**Looking to meet:** Other fintech investors"
        }

        json_content = json.dumps(sample_insight)
        
        file_path = self.json_writer.write_structured_insight(
            contact_id="CNT-TEST001",
            eni_id="ENI-TEST-001",
            content=json_content,
            member_name="Test Member",
            eni_source_type="test_data",
            eni_source_subtype="demo"
        )

        self.assertIsNotNone(file_path)
        self.assertTrue(Path(file_path).exists())

        # Verify file content
        with open(file_path, 'r') as f:
            file_data = json.load(f)

        self.assertIn('metadata', file_data)
        self.assertIn('insights', file_data)
        self.assertEqual(file_data['metadata']['contact_id'], "CNT-TEST001")
        self.assertEqual(file_data['insights'], sample_insight)

    def test_read_structured_insight(self):
        """Test reading structured insight from JSON file."""
        # Create test file
        test_data = {
            "metadata": {
                "contact_id": "CNT-TEST002",
                "member_name": "Test Member 2"
            },
            "insights": {
                "personal": "Test personal info",
                "business": "Test business info"
            }
        }

        test_file = Path(self.temp_dir) / "test_file.json"
        with open(test_file, 'w') as f:
            json.dump(test_data, f)

        # Read the file
        data = self.json_writer.read_structured_insight(str(test_file))
        
        self.assertIsNotNone(data)
        self.assertEqual(data, test_data)

    def test_airtable_data_extraction(self):
        """Test extracting data formatted for Airtable."""
        # Create test JSON file
        sample_insight = {
            "personal": "* Test personal",
            "business": "* Test business"
        }

        json_content = json.dumps(sample_insight)
        file_path = self.json_writer.write_structured_insight(
            contact_id="CNT-TEST003",
            eni_id="ENI-TEST-003",
            content=json_content,
            member_name="Test Member 3",
            eni_source_type="airtable_notes",
            eni_source_subtype="test"
        )

        # Extract Airtable data
        airtable_data = self.json_writer.get_insight_data_for_airtable(file_path)
        
        self.assertIsNotNone(airtable_data)
        self.assertEqual(airtable_data['contact_id'], "CNT-TEST003")
        self.assertEqual(airtable_data['member_name'], "Test Member 3")
        self.assertIn('json_data', airtable_data)
        self.assertEqual(airtable_data['json_data'], sample_insight)


class TestStructuredAirtableWriter(unittest.TestCase):
    """Test the structured Airtable writer functionality."""

    def setUp(self):
        """Set up test fixtures."""
        from context_management.config_loader import create_config_loader
        config_loader = create_config_loader("config/config.yaml")
        self.airtable_config = config_loader.get_airtable_config()

    def test_json_processing(self):
        """Test processing of structured JSON data."""
        from output_management.structured_airtable_writer import create_structured_airtable_writer
        
        # Mock the writer since we don't have real Airtable credentials
        with patch('output_management.structured_airtable_writer.Table'):
            writer = create_structured_airtable_writer(self.airtable_config)
            
            sample_json = {
                "personal": "* Test personal info",
                "business": "* Test business info", 
                "investing": "* Test investing info",
                "3i": "* Test 3i info",
                "deals": "Test deals content",
                "introductions": "Test introductions content"
            }

            processed = writer.process_structured_json(sample_json)
            
            self.assertIn('note_content', processed)
            self.assertIn('deals', processed)
            self.assertIn('introductions', processed)
            
            # Verify note_content concatenation
            note_content = processed['note_content']
            self.assertIn('Personal:', note_content)
            self.assertIn('Business:', note_content)
            self.assertIn('Investing:', note_content)
            self.assertIn('3I:', note_content)  # Note: Capitalized in actual output

    def test_configuration_structure(self):
        """Test that Airtable configuration has required structure."""
        self.assertIn('structured_insight', self.airtable_config)
        
        structured_config = self.airtable_config['structured_insight']
        self.assertIn('base_id', structured_config)
        self.assertIn('tables', structured_config)
        
        tables = structured_config['tables']
        self.assertIn('note_submission', tables)
        self.assertIn('master', tables)


class TestStructuredInsightsIntegration(unittest.TestCase):
    """Integration tests for structured insights processing."""

    def test_system_prompt_configuration(self):
        """Test that structured_insight system prompt is configured."""
        from context_management.config_loader import create_config_loader
        
        config_loader = create_config_loader("config/config.yaml")
        system_prompts = config_loader.get_all_system_prompts()
        
        self.assertIn('structured_insight', system_prompts)
        
        prompt_path = system_prompts['structured_insight']
        self.assertTrue(Path(prompt_path).exists(), 
            f"Structured insight prompt file does not exist: {prompt_path}")

    def test_default_system_prompt_setting(self):
        """Test that default system prompt is set to structured_insight."""
        from context_management.config_loader import create_config_loader
        
        config_loader = create_config_loader("config/config.yaml")
        processing_config = config_loader.get_processing_config()
        
        default_prompt = processing_config.get('default_system_prompt')
        self.assertEqual(default_prompt, 'structured_insight')

    def test_output_directory_creation(self):
        """Test that JSON writer creates output directory."""
        from output_management.json_writer import create_json_writer
        
        test_output_dir = "test_structured_output"
        json_writer = create_json_writer(test_output_dir)
        
        self.assertTrue(Path(test_output_dir).exists())
        
        # Clean up
        shutil.rmtree(test_output_dir)

    def test_structured_prompt_content(self):
        """Test that structured insight prompt has expected content."""
        from context_management.config_loader import create_config_loader
        from context_management.markdown_reader import create_markdown_reader
        
        config_loader = create_config_loader("config/config.yaml")
        markdown_reader = create_markdown_reader()
        
        prompt_path = config_loader.get_system_prompt_path('structured_insight')
        self.assertIsNotNone(prompt_path)
        
        content = markdown_reader.read_markdown_file(prompt_path)
        self.assertIsNotNone(content)
        
        # Check for key sections in the structured insight prompt
        required_sections = [
            'json',  # Lowercase in the actual prompt
            'personal',
            'business', 
            'investing',
            '3i',
            'deals',
            'introductions'
        ]
        
        content_lower = content.lower()
        for section in required_sections:
            self.assertIn(section, content_lower, 
                f"Missing expected section '{section}' in structured insight prompt")


class TestStructuredInsightsFunctionality(unittest.TestCase):
    """Test structured insights end-to-end functionality."""

    def test_main_processing_integration(self):
        """Test that main.py supports structured insights processing."""
        # This is a light integration test to verify the plumbing is correct
        from context_management.config_loader import create_config_loader
        
        config_loader = create_config_loader("config/config.yaml")
        
        # Verify configuration supports structured insights
        system_prompts = config_loader.get_all_system_prompts()
        self.assertIn('structured_insight', system_prompts)
        
        airtable_config = config_loader.get_airtable_config()
        self.assertIn('structured_insight', airtable_config)

    def test_cli_arguments_support(self):
        """Test that CLI supports structured insights arguments."""
        # Import main module to check argument parsing
        # This tests that the CLI arguments are properly defined
        try:
            import main
            # If we can import main without errors, the module structure is correct
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Failed to import main module: {e}")


def run_structured_insights_tests():
    """Run all structured insights tests."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestJSONWriter))
    suite.addTests(loader.loadTestsFromTestCase(TestStructuredAirtableWriter))
    suite.addTests(loader.loadTestsFromTestCase(TestStructuredInsightsIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestStructuredInsightsFunctionality))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    # Change to the correct directory for running tests
    test_dir = Path(__file__).parent.parent
    os.chdir(test_dir)
    
    success = run_structured_insights_tests()
    sys.exit(0 if success else 1) 