# Member Insights Processor Test Suite

This directory contains comprehensive tests for the Member Insights Processor system.

## Test Structure

Tests are organized into three categories:

### Unit Tests (`unit/`)
Tests for individual components without external dependencies:
- **`test_components.py`** - Core component functionality
- **`test_null_handling.py`** - Null ENI subtype handling
- **`test_processing_filters.py`** - Processing filter logic
- **`test_context_preview.py`** - Context preview generation

### Integration Tests (`integration/`)
Tests requiring external services and environment configuration:
- **`test_api_connections.py`** - API connectivity tests
- **`test_airtable_sync.py`** - Airtable synchronization
- **`test_supabase_integration.py`** - Supabase integration
- **`test_supabase_setup.py`** - Supabase setup validation
- **`test_supabase_upload.py`** - Supabase upload functionality
- **`test_local_setup.py`** - Local environment validation

### End-to-End Tests (`e2e/`)
Full pipeline tests:
- **`test_main_integration.py`** - Main processing pipeline
- **`test_single_contact.py`** - Single contact processing
- **`test_structured_insights.py`** - Structured insights processing
- **`test_with_env.py`** - Environment-based workflows
- **`simple_upload_test.py`** - Simple upload workflows
- **`test_runner.py`** - Test runner with colored output

## Running Tests

### Using pytest (Recommended)

```bash
# Run all tests
pytest

# Run specific category
pytest tests/unit/          # Unit tests only
pytest tests/integration/   # Integration tests only
pytest tests/e2e/          # End-to-end tests only

# Run with markers
pytest -m unit             # All unit tests
pytest -m integration      # All integration tests
pytest -m e2e             # All e2e tests

# Skip slow tests
pytest -m "not slow"

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_components.py
```

## Test Requirements

### Unit Tests
- No external dependencies required
- Safe to run in any environment
- Fast execution

### Integration Tests
- Require environment variables
- External service connectivity (BigQuery, Supabase, Airtable)

### Required Environment Variables

See [.env.example](../.env.example) for full list.

## Test Markers

- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.e2e` - End-to-end tests
- `@pytest.mark.slow` - Slow-running tests

## Writing New Tests

See [CONTRIBUTING.md](../CONTRIBUTING.md#testing) for guidelines.

## Troubleshooting

```bash
# Debug mode
pytest -vv --showlocals

# Show print statements
pytest -s
```

Target: **>80% code coverage**
