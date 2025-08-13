# Member Insights Processor Test Suite

This directory contains comprehensive tests for the Member Insights Processor system.

## Test Structure

### Test Files

- **`test_components.py`** - Unit tests for individual components without external dependencies
- **`test_with_env.py`** - Integration tests that require environment variables and external connections
- **`test_null_handling.py`** - Comprehensive tests for null ENI subtype handling
- **`test_structured_insights.py`** - Tests for structured insights JSON processing and Airtable integration
- **`test_processing_filters.py`** - BigQuery processing filters integration tests with real data
- **`test_airtable_sync.py`** - Airtable synchronization integration tests
- **`test_main_integration.py`** - End-to-end main processing pipeline tests
- **`test_single_contact.py`** - Single contact processing tests
- **`test_supabase_upload.py`** - Supabase upload and integration tests
- **`simple_upload_test.py`** - Simple upload functionality tests
- **`test_runner.py`** - Main test runner with colored output and reporting

### Test Categories

#### Component Tests
- Configuration loader
- Markdown reader
- Log manager
- JSON writer
- Airtable writers

#### Integration Tests  
- Environment variable validation
- BigQuery connectivity
- BigQuery processing filters with real data
- Gemini API integration
- End-to-end processing workflows

#### Feature Tests
- Null subtype handling
- Structured insights processing
- JSON output generation
- Airtable sync functionality

## Running Tests

### Run All Tests
```bash
# Run all tests with detailed output
python tests/test_runner.py

# Run all tests quietly
python tests/test_runner.py -q

# Run all tests with maximum verbosity
python tests/test_runner.py -vv
```

### Run Specific Test Categories
```bash
# Run only component tests (no external dependencies)
python tests/test_runner.py --components-only

# Run only integration tests (requires environment setup)
python tests/test_runner.py --integration-only
```

### Run Individual Test Files
```bash
# Run a specific test file
python tests/test_runner.py --test test_null_handling

# Run specific test file with verbose output
python tests/test_runner.py --test test_components -vv
```

### Run Individual Test Files Directly
```bash
# Run component tests directly
python tests/test_components.py

# Run environment tests directly  
python tests/test_with_env.py

# Run null handling tests directly
python tests/test_null_handling.py

# Run structured insights tests directly
python tests/test_structured_insights.py
```

## Test Requirements

### Component Tests
- No external dependencies required
- Tests configuration, file operations, and basic functionality
- Safe to run in any environment

### Integration Tests
- Require environment variables to be set
- May require external service connectivity (BigQuery, Gemini)
- Use appropriate test/mock data

### Required Environment Variables (for integration tests)
```bash
export PROJECT_ID="your-project-id"
export BQ_DATASET="your-dataset"
export GOOGLE_CLOUD_PROJECT_ID="your-project-id"
export GEMINI_API_KEY="your-gemini-key"  # Optional for testing
export AIRTABLE_API_KEY="your-airtable-key"  # Optional for testing
```

## Test Features

### Colored Output
- ✅ Green checkmarks for passing tests
- ❌ Red X marks for failing tests  
- ⏭️ Yellow arrows for skipped tests
- 💥 Red explosion for errors

### Detailed Reporting
- Test execution time
- Pass/fail statistics
- Error summaries
- Individual test results

### Flexible Execution
- Run all tests or specific subsets
- Control verbosity levels
- Filter by test categories
- Run individual test files

## Writing New Tests

### Adding Component Tests
Add unit tests for new components to `test_components.py` or create new test files following the naming convention `test_*.py`.

### Adding Integration Tests
Add integration tests that require external services to `test_with_env.py` or create specialized test files.

### Test File Template
```python
#!/usr/bin/env python3
"""
Test suite for [component/feature name]
"""

import unittest
import sys
import os
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestYourComponent(unittest.TestCase):
    """Test your component functionality."""

    def setUp(self):
        """Set up test fixtures."""
        pass

    def test_your_functionality(self):
        """Test specific functionality."""
        self.assertTrue(True)


if __name__ == "__main__":
    # Change to the correct directory for running tests
    test_dir = Path(__file__).parent.parent
    os.chdir(test_dir)
    
    unittest.main()
```

## Continuous Integration

The test suite is designed to be run in CI/CD environments:

```bash
# CI-friendly test execution
python tests/test_runner.py --components-only -q
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Make sure you're running tests from the project root or that the test files have proper path setup.

2. **Configuration Errors**: Ensure `config/config.yaml` exists and is properly formatted.

3. **Environment Variable Issues**: For integration tests, make sure required environment variables are set.

4. **File Path Issues**: Tests should be run from the project root directory.

### Debug Mode
Run tests with maximum verbosity to see detailed error information:
```bash
python tests/test_runner.py -vv
```

## BigQuery Processing Filters Test

The `test_processing_filters.py` test validates that BigQuery filtering is working correctly with the `processing_filters.yaml` configuration.

### Features

- **Real Data Testing** - Tests against actual BigQuery data
- **Comprehensive Coverage** - Tests all ENI type/subtype combinations from processing_filters.yaml
- **Detailed Logging** - Shows unprocessed record counts for each combination
- **Parameterized Testing** - Allows testing with different contact IDs
- **Data Integrity Validation** - Verifies proper filtering and data structure

### Usage

#### Basic Usage (Default Contact ID)
```bash
cd member-insights-processor
python tests/test_processing_filters.py
```

#### Test Specific Contact ID
```bash
python tests/test_processing_filters.py --contact-id CNT-ABC123456
```

#### Verbose Logging
```bash
python tests/test_processing_filters.py --contact-id CNT-QS0006256 --verbose
```

#### Using the Runner Script
```bash
# Default contact ID
python scripts/run_processing_filters_test.py

# Specific contact ID
python scripts/run_processing_filters_test.py CNT-ABC123456

# With verbose logging
python scripts/run_processing_filters_test.py --verbose
```

### Test Output

The test provides detailed output including:

- **Processing Rules Validation** - Confirms processing_filters.yaml is loaded correctly
- **Combination Generation** - Shows all ENI type/subtype combinations to be tested
- **Record Counts by Combination** - Number of unprocessed records for each combination
- **Data Integrity Checks** - Validates proper filtering and data structure
- **Summary Report** - Total combinations tested and total unprocessed records

### Example Output
```
🧪 Testing processing filter combinations generation
📊 Generated 12 ENI combinations:
  - airtable_affiliations / NULL
  - airtable_deals_sourced / NULL
  - airtable_notes / NULL
  - airtable_notes / investing_preferences
  - airtable_notes / intro_preferences
  - recurroo / NULL
  - recurroo / biography
  ...

📈 FILTERING TEST SUMMARY for contact CNT-QS0006256
================================================================================
Total combinations tested: 12
Total unprocessed records found: 45
Records by ENI Type/Subtype:
  airtable_affiliations     / NULL                :      5 records
  airtable_deals_sourced    / NULL                :      0 records
  airtable_notes           / NULL                :     12 records
  airtable_notes           / investing_preferences:      8 records
  ...
```

### Prerequisites

- BigQuery credentials configured
- Access to the `i-sales-analytics.3i_analytics.eni_vectorizer__all` table
- Access to the `i-sales-analytics.elvis.eni_processing_log` table
- Valid contact ID with data in the system 

# Tests

## Context Preview (Per-Group) — Markdown Log

`tests/test_context_preview.py` builds a token-aware context per `(eni_source_type, eni_source_subtype)` group and writes a readable markdown report.

Run:

```bash
pytest -q tests/test_context_preview.py
```

Output:
- `logs/context_preview_{CONTACT_ID}_{TIMESTAMP}.md`
- Summary table with columns:
  - `run_number | eni_source_type | eni_source_sub_type | tokens_system_plus_source_ctx | remaining_tokens | total_rows_in_group | rows_processed | total_tokens_rendered`
- For each run (group):
  - Fully rendered system prompt including:
    - `{{current_structured_insight}}`
    - `{{eni_source_type_context}}`
    - `{{eni_source_subtype_context}}`
    - `{{new_data_to_process}}` (now includes citation lines: `[logged_date,eni_id,source_type]`)
  - Token stats as JSON

Notes:
- The test will attempt to connect to BigQuery using your config; if unavailable, it falls back to a small synthetic dataset.
- Assertion ensures ENI IDs appear in the rendered prompt.
- This test does not call the LLM or upsert to Supabase; it’s for preview and token budgeting only. 