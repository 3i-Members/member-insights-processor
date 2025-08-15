#!/usr/bin/env python3
"""
Test suite for BigQuery Processing Filters Integration

This test suite verifies that the BigQuery connector correctly applies
processing filters from processing_filters.yaml and returns the expected
ENI type/subtype combinations with proper record counts.
"""

import unittest
import sys
import os
import logging
import argparse
from pathlib import Path
from typing import Dict, Any, List, Tuple

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestProcessingFilters(unittest.TestCase):
    """Test BigQuery processing filters integration."""

    def setUp(self):
        """Set up test fixtures."""
        # Import after adding to path
        from data_processing.bigquery_connector import create_bigquery_connector
        from context_management.config_loader import create_config_loader
        from context_management.processing_filter import create_processing_filter
        
        # Default test contact ID
        from tests import DEFAULT_CONTACT_ID
        self.default_contact_id = DEFAULT_CONTACT_ID
        
        # Initialize components
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')
        filter_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'processing_filters.yaml')
        
        self.config_loader = create_config_loader(config_path)
        self.processing_filter = create_processing_filter(filter_path)
        self.bigquery_connector = create_bigquery_connector(self.config_loader.config_data)
        
        # Establish BigQuery connection
        if not self.bigquery_connector.connect():
            self.skipTest("Cannot connect to BigQuery - skipping integration tests")
        
        logger.info("✅ Test setup completed successfully")

    def test_processing_filter_combinations_generation(self):
        """Test that processing filter generates expected combinations."""
        logger.info("🧪 Testing processing filter combinations generation")
        
        processing_rules = self.processing_filter.processing_rules
        combinations = self.bigquery_connector.get_eni_combinations_for_processing(processing_rules)
        
        # Log the generated combinations
        logger.info(f"📊 Generated {len(combinations)} ENI combinations:")
        for eni_type, eni_subtype in combinations:
            subtype_display = eni_subtype if eni_subtype else "NULL"
            logger.info(f"  - {eni_type} / {subtype_display}")
        
        # Verify that combinations were generated
        self.assertGreater(len(combinations), 0, "Should generate at least one combination")
        
        # Verify that NULL subtypes are always included
        eni_types_in_combinations = set(combo[0] for combo in combinations)
        null_combinations = [(eni_type, subtype) for eni_type, subtype in combinations if subtype == "null"]
        
        # Every ENI type should have a NULL combination
        for eni_type in processing_rules.keys():
            null_combo_exists = any(combo[0] == eni_type and combo[1] == "null" for combo in combinations)
            self.assertTrue(null_combo_exists, f"ENI type {eni_type} should have a NULL subtype combination")
        
        logger.info(f"✅ Found {len(null_combinations)} NULL subtype combinations (expected for all ENI types)")
        
        return combinations

    def test_contact_data_filtering_by_combination(self):
        """Test filtering contact data by individual ENI type/subtype combinations."""
        contact_id = getattr(self, 'contact_id', self.default_contact_id)
        logger.info(f"🧪 Testing contact data filtering for contact: {contact_id}")
        
        processing_rules = self.processing_filter.processing_rules
        combinations = self.bigquery_connector.get_eni_combinations_for_processing(processing_rules)
        
        total_records = 0
        results_summary = []
        
        for eni_source_type, eni_source_subtype in combinations:
            logger.info(f"📋 Testing combination: {eni_source_type} / {eni_source_subtype or 'NULL'}")
            
            try:
                # Load data for this specific combination
                data = self.bigquery_connector.load_contact_data_filtered(
                    contact_id=contact_id,
                    eni_source_type=eni_source_type,
                    eni_source_subtype=eni_source_subtype
                )
                
                record_count = len(data)
                total_records += record_count
                
                result_info = {
                    'eni_source_type': eni_source_type,
                    'eni_source_subtype': eni_source_subtype or 'NULL',
                    'unprocessed_records': record_count
                }
                results_summary.append(result_info)
                
                # Log the results
                subtype_display = eni_source_subtype or "NULL"
                logger.info(f"  📊 {eni_source_type}/{subtype_display}: {record_count} unprocessed records")
                
                # Verify data integrity if records exist
                if record_count > 0:
                    # Verify that all records have the correct eni_source_type
                    unique_types = data['eni_source_type'].unique()
                    self.assertEqual(len(unique_types), 1, f"Should only have one eni_source_type: {eni_source_type}")
                    self.assertEqual(unique_types[0], eni_source_type, f"All records should have eni_source_type: {eni_source_type}")
                    
                    # Verify subtype filtering
                    if eni_source_subtype == "null":
                        null_count = data['eni_source_subtype'].isna().sum()
                        self.assertEqual(null_count, record_count, "All records should have NULL eni_source_subtype")
                    elif eni_source_subtype:
                        non_null_data = data.dropna(subset=['eni_source_subtype'])
                        if len(non_null_data) > 0:
                            unique_subtypes = non_null_data['eni_source_subtype'].unique()
                            self.assertIn(eni_source_subtype, unique_subtypes, f"Should contain subtype: {eni_source_subtype}")
                
            except Exception as e:
                error_msg = f"Error testing {eni_source_type}/{eni_source_subtype}: {str(e)}"
                logger.error(f"❌ {error_msg}")
                self.fail(error_msg)
        
        # Log summary
        logger.info("\n" + "="*80)
        logger.info(f"📈 FILTERING TEST SUMMARY for contact {contact_id}")
        logger.info("="*80)
        logger.info(f"Total combinations tested: {len(combinations)}")
        logger.info(f"Total unprocessed records found: {total_records}")
        logger.info("\nRecords by ENI Type/Subtype:")
        
        for result in results_summary:
            eni_type = result['eni_source_type']
            eni_subtype = result['eni_source_subtype']
            count = result['unprocessed_records']
            logger.info(f"  {eni_type:25} / {eni_subtype:20} : {count:6} records")
        
        logger.info("="*80)
        
        return results_summary

    def test_processing_rules_validation(self):
        """Test that processing rules are correctly loaded and validated."""
        logger.info("🧪 Testing processing rules validation")
        
        processing_rules = self.processing_filter.processing_rules
        
        # Verify rules are loaded
        self.assertIsNotNone(processing_rules, "Processing rules should be loaded")
        self.assertGreater(len(processing_rules), 0, "Should have at least one processing rule")
        
        logger.info(f"📋 Loaded {len(processing_rules)} processing rules:")
        
        for eni_type, rule in processing_rules.items():
            if rule is None or rule == "none":
                logger.info(f"  {eni_type:25} : NULL subtypes only")
            elif isinstance(rule, list):
                logger.info(f"  {eni_type:25} : NULL + {len(rule)} explicit subtypes {rule}")
            else:
                logger.warning(f"  {eni_type:25} : Invalid rule format: {rule}")
        
        # Test combination generation
        combinations = self.bigquery_connector.get_eni_combinations_for_processing(processing_rules)
        
        # Verify each ENI type has at least a NULL combination
        eni_types_with_combinations = set(combo[0] for combo in combinations)
        for eni_type in processing_rules.keys():
            self.assertIn(eni_type, eni_types_with_combinations, 
                         f"ENI type {eni_type} should have at least one combination")

    def test_bigquery_connection_and_basic_query(self):
        """Test BigQuery connection and basic querying capability."""
        logger.info("🧪 Testing BigQuery connection and basic query")
        
        # Test connection
        self.assertTrue(self.bigquery_connector.connect(), "Should be able to connect to BigQuery")
        
        # Test basic table access
        contact_id = getattr(self, 'contact_id', self.default_contact_id)
        
        try:
            # Test with a simple combination
            data = self.bigquery_connector.load_contact_data_filtered(
                contact_id=contact_id,
                eni_source_type="airtable_affiliations",
                eni_source_subtype="null"
            )
            
            logger.info(f"✅ Successfully queried airtable_affiliations/NULL: {len(data)} records")
            
            # Verify data structure
            if len(data) > 0:
                required_columns = ['eni_source_type', 'eni_source_subtype', 'contact_id', 'eni_id', 'description']
                for col in required_columns:
                    self.assertIn(col, data.columns, f"Required column {col} should be present")
                
                # Verify contact_id filtering
                unique_contacts = data['contact_id'].unique()
                self.assertEqual(len(unique_contacts), 1, "Should only have one contact_id")
                self.assertEqual(unique_contacts[0], contact_id, f"All records should have contact_id: {contact_id}")
            
        except Exception as e:
            self.fail(f"Basic BigQuery query failed: {str(e)}")

    def run_comprehensive_test(self, contact_id: str = None):
        """Run comprehensive test for a specific contact."""
        if contact_id:
            self.contact_id = contact_id
            
        logger.info(f"\n🚀 RUNNING COMPREHENSIVE PROCESSING FILTERS TEST")
        logger.info(f"Contact ID: {getattr(self, 'contact_id', self.default_contact_id)}")
        logger.info("="*80)
        
        # Run all tests
        self.test_bigquery_connection_and_basic_query()
        self.test_processing_rules_validation()
        combinations = self.test_processing_filter_combinations_generation()
        results_summary = self.test_contact_data_filtering_by_combination()
        
        return results_summary


from tests import DEFAULT_CONTACT_ID

def run_test_with_contact_id(contact_id: str = DEFAULT_CONTACT_ID):
    """
    Run the processing filters test with a specific contact ID.
    
    Args:
        contact_id: The contact ID to test with
    """
    # Create test suite
    suite = unittest.TestSuite()
    
    # Create test instance
    test_instance = TestProcessingFilters()
    test_instance.setUp()
    
    # Run comprehensive test
    try:
        results = test_instance.run_comprehensive_test(contact_id)
        logger.info("\n✅ All tests completed successfully!")
        return results
    except Exception as e:
        logger.error(f"❌ Test failed: {str(e)}")
        raise


def main():
    """Main function to run tests with command line arguments."""
    parser = argparse.ArgumentParser(description="Test BigQuery Processing Filters")
    parser.add_argument(
        '--contact-id', 
        type=str, 
        default=DEFAULT_CONTACT_ID,
        help=f"Contact ID to test with (default: {DEFAULT_CONTACT_ID})"
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info(f"🧪 Starting BigQuery Processing Filters Test")
    logger.info(f"📋 Contact ID: {args.contact_id}")
    
    try:
        results = run_test_with_contact_id(args.contact_id)
        
        # Print final summary
        total_records = sum(result['unprocessed_records'] for result in results)
        logger.info(f"\n🎉 TEST COMPLETED SUCCESSFULLY!")
        logger.info(f"📊 Total unprocessed records found: {total_records}")
        
        return 0
    except Exception as e:
        logger.error(f"💥 TEST FAILED: {str(e)}")
        return 1


if __name__ == "__main__":
    exit(main()) 