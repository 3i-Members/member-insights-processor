# Member Insights Processor Test Suite

This directory contains comprehensive tests for the Member Insights Processor system.

## Test Structure

### Test Files

- **`test_components.py`** - Unit tests for individual components without external dependencies
- **`test_with_env.py`** - Integration tests that require environment variables and external connections
- **`test_null_handling.py`** - Comprehensive tests for null ENI subtype handling
- **`test_structured_insights.py`** - Tests for structured insights JSON processing and Airtable integration
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