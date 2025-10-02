# Developer Onboarding Guide

Welcome to the Member Insights Processor project! This guide will help you get up and running quickly.

## Prerequisites

- Python 3.9+ installed
- Access to Google Cloud BigQuery (service account credentials)
- Access to Supabase project
- AI API key (OpenAI, Anthropic, or Gemini)
- Git installed

## Quick Start (15 minutes)

### 1. Clone and Setup (5 min)

```bash
# Clone the repository
git clone <repository-url>
cd member-insights-processor-standalone

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment (5 min)

```bash
# Copy example environment file
cp .env.example .env

# Extract Google Cloud credentials from service account JSON
python scripts/extract_service_account.py /path/to/service-account.json --output .env

# Edit .env and add remaining credentials
nano .env
```

Required environment variables:
- `GCP_*` - Google Cloud credentials (extracted from service account JSON)
- `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` or `GEMINI_API_KEY` - AI provider
- `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` - Supabase credentials
- `AIRTABLE_API_KEY` and `AIRTABLE_BASE_ID` - Airtable credentials (optional)

### 3. Validate Setup (2 min)

```bash
# Set PYTHONPATH
export PYTHONPATH=src

# Run validation
python -m member_insights_processor.pipeline.runner --validate
```

You should see:
- ✅ Environment variables loaded
- ✅ BigQuery connection successful
- ✅ Supabase connection successful
- ✅ AI provider configured
- ✅ Config files valid

### 4. Test Run (3 min)

```bash
# Process a single contact
python -m member_insights_processor.pipeline.runner --limit 1

# Or test with specific contact ID
python -m member_insights_processor.pipeline.runner --contact-id "CNT-ABC123"
```

## Project Structure

```
member-insights-processor-standalone/
├── src/member_insights_processor/    # Main package
│   ├── core/                         # Core business logic
│   │   ├── llm/                      # LLM providers (OpenAI, Anthropic, Gemini)
│   │   │   ├── openai.py
│   │   │   ├── anthropic.py
│   │   │   └── gemini.py
│   │   └── utils/                    # Shared utilities
│   │       ├── logging.py            # Enhanced logging
│   │       ├── tokens.py             # Token estimation
│   │       ├── claims.py             # Parallel processing claims
│   │       └── run_summary.py        # Run observability
│   ├── pipeline/                     # Orchestration
│   │   ├── runner.py                 # Main pipeline runner (entry point)
│   │   ├── config.py                 # Configuration loader
│   │   ├── context.py                # Context manager (token budgeting)
│   │   └── filters.py                # Processing filter rules
│   └── io/                           # All I/O boundaries
│       ├── readers/                  # Data readers
│       │   ├── bigquery.py           # BigQuery data source
│       │   └── supabase.py           # Supabase reader
│       └── writers/                  # Data writers
│           ├── airtable.py           # Airtable sync
│           ├── supabase.py           # Supabase writer
│           ├── supabase_sync.py      # Decoupled Airtable sync
│           ├── markdown.py           # Markdown output
│           └── json.py               # JSON output
├── config/                           # Configuration files
│   ├── config.yaml                   # Main configuration
│   ├── processing_filters.yaml       # ENI type/subtype rules
│   └── system_prompts/               # LLM prompt templates
│       └── structured_insight.md     # Primary prompt template
├── var/                              # Runtime artifacts (gitignored)
│   ├── logs/                         # All log files
│   │   ├── runs/                     # Run summary outputs
│   │   └── claims/                   # Parallel processing claims
│   └── output/                       # Generated outputs
├── tests/                            # Test files
└── docs/                             # Documentation
    ├── CLAUDE.md                     # Claude Code guidance
    ├── DEPLOYMENT.md                 # Deployment instructions
    └── ONBOARDING.md                 # This file
```

## Key Concepts

### 1. Per-ENI-Group Processing

The system processes data by `(eni_source_type, eni_source_subtype)` combinations:
- Each group gets one LLM call with token-budgeted context
- Groups are defined in `config/processing_filters.yaml`
- NULL subtypes are always processed first for each type

### 2. Token Budgeting

Context Manager ([pipeline/context.py](../src/member_insights_processor/pipeline/context.py)) enforces token limits:
- Loads existing insights from Supabase (JSON format)
- Renders system prompt with variable substitution
- Allocates remaining tokens to new data
- Truncates rows to fit within budget

Settings in `config/config.yaml`:
```yaml
processing:
  context_window_tokens: 200000
  reserve_output_tokens: 8000
  max_new_data_tokens_per_group: 12000
```

### 3. Processing Log (Deduplication)

BigQuery table `elvis.eni_processing_log` tracks processed ENI IDs:
- LEFT JOIN filtering in queries excludes already processed records
- Batch marking after successful processing
- Prevents duplicate work across runs

### 4. Parallel Processing

Production runs use ThreadPoolExecutor with distributed locking:
- Claims system ([core/utils/claims.py](../src/member_insights_processor/core/utils/claims.py)) prevents duplicate processing
- Run summary ([core/utils/run_summary.py](../src/member_insights_processor/core/utils/run_summary.py)) provides observability
- Configure via `--parallel --max-concurrent-contacts N`

### 5. Supabase Storage

Insights stored in PostgreSQL JSONB format:
- Consolidated ENI ID: `COMBINED-{contact_id}-ALL`
- Versioning with `is_latest` flag
- Intelligent upsert merges new data with existing

### 6. Airtable Sync (Optional)

Post-processing step that requires contact to exist in Airtable master table:
- Looks up contact in master table (`tblkKWKRCEwl6aGDc`)
- Creates note submission record if found
- Fails gracefully if contact doesn't exist

## Common Development Tasks

### Running the Pipeline

```bash
# Always set PYTHONPATH first
export PYTHONPATH=src

# Single contact (testing)
python -m member_insights_processor.pipeline.runner --contact-id CNT-ABC123

# Small batch
python -m member_insights_processor.pipeline.runner --limit 10

# Production run with parallel processing
python -m member_insights_processor.pipeline.runner --limit 100 --parallel --max-concurrent-contacts 5

# Dry run (no database writes)
python -m member_insights_processor.pipeline.runner --limit 5 --dry-run
```

### Viewing Configuration

```bash
# Show processing filter rules
python -m member_insights_processor.pipeline.runner --show-filter

# Validate configuration
python -m member_insights_processor.pipeline.runner --validate
```

### Adding New ENI Types

1. Add context file to `context/` directory:
```bash
mkdir -p context/new_source_type
echo "# Context for new source" > context/new_source_type/default.md
```

2. Update `config/config.yaml`:
```yaml
eni_mappings:
  new_source_type:
    default: "context/new_source_type/default.md"
```

3. Update `config/processing_filters.yaml`:
```yaml
eni_processing_rules:
  default_processing_filter:
    new_source_type:
      enabled: true
      include_null_subtype: true
      subtypes: []
```

4. Test:
```bash
python -m member_insights_processor.pipeline.runner --contact-id CNT-ABC123 --limit 1
```

### Modifying System Prompts

1. Edit template in `config/system_prompts/structured_insight.md`
2. Use `{{variable}}` for substitution (four supported variables)
3. Test with single contact:
```bash
python -m member_insights_processor.pipeline.runner --contact-id CNT-ABC123 --limit 1
```

### Debugging

Enable debug mode in `config/config.yaml`:
```yaml
debug:
  enable_debug_mode: true
  llm_trace:
    enabled: true
```

This writes detailed traces to `var/logs/llm_traces/` including:
- Fully rendered system prompts
- Token statistics
- LLM responses

## Troubleshooting

### ModuleNotFoundError

**Problem**: `ModuleNotFoundError: No module named 'member_insights_processor'`

**Solution**:
```bash
# Always set PYTHONPATH
export PYTHONPATH=src
```

### Environment Variables Not Loading

**Problem**: API key errors or missing credentials

**Solution**:
```bash
# Check .env file exists
ls -la .env

# Verify environment variables load
python -m member_insights_processor.pipeline.runner --validate
```

### BigQuery Connection Errors

**Problem**: Can't connect to BigQuery

**Solution**:
1. Verify service account JSON is valid
2. Re-extract credentials:
```bash
python scripts/extract_service_account.py /path/to/service-account.json --output .env
```
3. Check GCP project has BigQuery API enabled
4. Verify service account has BigQuery permissions

### Airtable Sync Failures

**Problem**: Airtable sync fails with "No master record found"

**Explanation**: This is expected behavior. Contacts must exist in the Airtable master table before note submissions can be created.

**Solution**: Either:
1. Add the contact to Airtable master table first
2. Ignore the error - insights are still saved to Supabase

## Learning Resources

### Documentation
- [README.md](../README.md) - Full project documentation
- [docs/CLAUDE.md](CLAUDE.md) - Claude Code guidance
- [docs/DEPLOYMENT.md](DEPLOYMENT.md) - Deployment instructions
- [docs/SUPABASE_INTEGRATION.md](SUPABASE_INTEGRATION.md) - Supabase setup

### Configuration Files
- `config/config.yaml` - Main configuration with inline comments
- `config/processing_filters.yaml` - ENI type/subtype rules
- `config/system_prompts/structured_insight.md` - LLM prompt template

### Code Entry Points
- [pipeline/runner.py](../src/member_insights_processor/pipeline/runner.py) - Main pipeline orchestration
- [pipeline/context.py](../src/member_insights_processor/pipeline/context.py) - Context assembly and token budgeting
- [io/readers/bigquery.py](../src/member_insights_processor/io/readers/bigquery.py) - Data source queries

## Getting Help

1. Check existing documentation in `docs/`
2. Review configuration files for inline comments
3. Run validation: `python -m member_insights_processor.pipeline.runner --validate`
4. Check logs in `var/logs/` for detailed error messages
5. Open an issue on GitHub or contact the maintainers

## Next Steps

After completing onboarding:

1. **Explore the codebase**: Read through key files mentioned above
2. **Run a test**: Process a single contact end-to-end
3. **Review logs**: Check `var/logs/` to understand output format
4. **Try parallel processing**: Run with `--parallel --max-concurrent-contacts 3`
5. **Make a change**: Add a new ENI type or modify a prompt

Welcome to the team! 🎉
