#!/usr/bin/env python3
"""
Simple runner script for testing BigQuery Processing Filters

Usage:
    python scripts/run_processing_filters_test.py                    # Use default contact ID
    python scripts/run_processing_filters_test.py CNT-ABC123456     # Use specific contact ID
    python scripts/run_processing_filters_test.py --verbose         # Enable verbose logging
"""

import sys
import os
from pathlib import Path

# Add project root (parent of scripts) to path so 'tests' is importable as a package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tests.test_processing_filters import run_test_with_contact_id, main
from tests import DEFAULT_CONTACT_ID

if __name__ == "__main__":
    if len(sys.argv) > 1 and not sys.argv[1].startswith('--'):
        # Contact ID provided as argument
        contact_id = sys.argv[1]
        print(f"🧪 Running processing filters test with contact ID: {contact_id}")
        try:
            results = run_test_with_contact_id(contact_id)
            print(f"\n✅ Test completed successfully!")
            
            # Print summary
            total_records = sum(result['unprocessed_records'] for result in results)
            print(f"📊 Total unprocessed records found: {total_records}")
            
        except Exception as e:
            print(f"❌ Test failed: {str(e)}")
            sys.exit(1)
    else:
        print(f"ℹ️ Using default contact ID: {DEFAULT_CONTACT_ID}")
        # Use main function with argument parsing
        sys.exit(main()) 