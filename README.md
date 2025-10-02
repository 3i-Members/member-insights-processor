# Member Insights Processor

AI-powered system that processes member data from BigQuery, generates structured insights using Claude/Gemini/OpenAI, and stores results in Supabase. Features intelligent upsert logic, decoupled Airtable syncing, and Docker-optimized performance.

## Quick Start

### 1. Prerequisites
- Python 3.9+
- Google Cloud credentials (BigQuery access)
- Supabase account
- AI API key (OpenAI, Claude, or Gemini)

### 2. Setup

```bash
# Clone and navigate
cd member-insights-processor-standalone

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file from example
cp .env.example .env

# Extract Google Cloud credentials from your service account JSON
# Option 1: Use helper script (recommended)
python scripts/extract_service_account.py /path/to/service-account.json --output .env

# Option 2: Manual - open .env and copy values from your JSON
nano .env

# Add your AI provider API key and Supabase credentials
nano .env
```

**Important**: All credentials are now stored as environment variables (no JSON file mounting required). This makes container deployment much simpler.

```

### 3. Validate Setup

```bash
export PYTHONPATH=src
python -m member_insights_processor.pipeline.runner --validate
```

This checks:
- ✅ Environment variables loaded
- ✅ BigQuery connection
- ✅ Supabase connection
- ✅ AI provider configured
- ✅ Config files valid

### 4. Test with Single Contact

```bash
# Set PYTHONPATH
export PYTHONPATH=src

# Process one contact (recommended first test)
python -m member_insights_processor.pipeline.runner --limit 1

# Or specify a contact ID
python -m member_insights_processor.pipeline.runner --contact-id "CNT-ABC123"

# Dry run (no database writes)
python -m member_insights_processor.pipeline.runner --limit 1 --dry-run
```

## How It Works

The system processes data in **per-ENI-group mode**:

1. Queries BigQuery for unprocessed member data (filtered by processing log)
2. Groups data by `(eni_source_type, eni_source_subtype)` from [config/processing_filters.yaml](config/processing_filters.yaml)
3. For each group: assembles token-budgeted context → calls AI → stores in Supabase
4. Marks processed records in BigQuery to avoid reprocessing
5. Optional: Sync results to Airtable (decoupled, post-processing)

## Common Commands

```bash
# Always activate venv and set PYTHONPATH first
source venv/bin/activate
export PYTHONPATH=src

# Validate configuration
python -m member_insights_processor.pipeline.runner --validate

# Process single contact (recommended for testing)
python -m member_insights_processor.pipeline.runner --contact-id "CNT-ABC123"

# Process batch
python -m member_insights_processor.pipeline.runner --limit 10

# Process with parallel workers (production)
python -m member_insights_processor.pipeline.runner --limit 100 --parallel --max-concurrent-contacts 5

# Dry run (don't save results)
python -m member_insights_processor.pipeline.runner --limit 5 --dry-run

# Check processing statistics
python -m member_insights_processor.pipeline.runner --stats

# View processing filter rules
python -m member_insights_processor.pipeline.runner --show-filter
```

## Supabase Integration

This system now features **full Supabase integration** for scalable, memory-efficient processing:

### 🗄️ **Database Setup**

1. **Create Supabase Table**
   ```sql
   -- Run this SQL in your Supabase SQL Editor
   -- See config/supabase_schema.sql for the complete schema
   ```

2. **Validate Supabase Connection**
   ```bash
   python scripts/setup_supabase.py --validate
   ```

3. **Migrate Existing Data** (Optional)
   ```bash
   # Migrate existing JSON files to Supabase
   python scripts/setup_supabase.py --migrate --dry-run
   python scripts/setup_supabase.py --migrate  # Actually migrate
   ```

### 🔄 **Processing Workflow**

The system now uses **intelligent upsert logic**:

1. **Load existing insights** from Supabase before processing
2. **Merge new data** with existing insights automatically  
3. **Save to Supabase** with PostgreSQL JSONB for fast queries
4. **Sync to Airtable** independently using decoupled service (post-processing)
   - Consolidated upserts under a single per-contact ENI ID: `COMBINED-{contact_id}-ALL`
   - Versioning maintained via `is_latest` flag and incremented `version`

### 🎯 **Decoupled Airtable Sync**

Test the new Airtable sync that pulls from Supabase:

```bash
# Test Supabase-powered Airtable sync for specific contact (from tests)
python test_airtable_sync.py

# Bulk sync all latest insights where is_latest = true (new standalone script)
PYTHONPATH="src" python scripts/airtable_sync_insights.py --limit 1000 --force

# This will:
# 1. Select rows from Supabase where is_latest = true and generator='structured_insight'
# 2. For each contact_id, fetch the latest insight and write a note submission to Airtable
# 3. Run decoupled from the main processing pipeline
```

### 📊 **Memory Benefits**

- ✅ **No local file bottlenecks** - structured insights stored in Supabase
- ✅ **Docker optimized** - reduced memory footprint for containers
- ✅ **Batch processing** - configurable batch sizes for large datasets
- ✅ **Smart caching** - only loads existing data when needed

For detailed setup instructions, see **[SUPABASE_INTEGRATION.md](./SUPABASE_INTEGRATION.md)**.

## Configuration

The system uses a YAML configuration file (`config/config.yaml`) to define:

- **BigQuery Settings**: Project, dataset, and table information
- **ENI Mappings**: Map ENI types/subtypes to context files
- **System Prompts**: Define different AI processing modes
- **Airtable Integration**: Field mappings and sync settings

### Example Configuration

```yaml
bigquery:
  project_id: "your-project-id"
  dataset_id: "your-dataset-id"
  table_name: "eni_vectorizer__all"

eni_mappings:
  professional:
    consultant: "context/professional/consultant.md"
    developer: "context/professional/developer.md"
    default: "context/professional/default.md"

system_prompts:
  member_summary: "config/system_prompts/member_summary.md"
  insight_generation: "config/system_prompts/insight_generation.md"

airtable:
  field_mapping:
    content: "AI Summary"
    contact_id: "Contact ID"
    eni_id: "ENI ID"
```

## Usage Examples

### Command Line Interface

```bash
# Set PYTHONPATH for all commands
export PYTHONPATH=src

# Basic processing
python -m member_insights_processor.pipeline.runner

# Process specific contact with custom prompt
python -m member_insights_processor.pipeline.runner --contact-id "CNT-ABC123" --system-prompt "structured_insight"

# Batch processing with limit
python -m member_insights_processor.pipeline.runner --limit 50

# Parallel processing (production)
python -m member_insights_processor.pipeline.runner --limit 100 --parallel --max-concurrent-contacts 5

# Dry run for testing
python -m member_insights_processor.pipeline.runner --contact-id "CNT-ABC123" --dry-run

# View processing filter rules
python -m member_insights_processor.pipeline.runner --show-filter
```

### Programmatic Usage

```python
import sys
sys.path.insert(0, 'src')

from member_insights_processor.pipeline.config import ConfigLoader
from member_insights_processor.io.readers.bigquery import BigQueryReader
from member_insights_processor.io.writers.supabase import SupabaseInsightsClient

# Load configuration
config_loader = ConfigLoader('config/config.yaml')

# Initialize BigQuery reader
bq_reader = BigQueryReader(
    project_id=config_loader.config_data['bigquery']['project_id'],
    dataset_id=config_loader.config_data['bigquery']['dataset_id'],
    table_name=config_loader.config_data['bigquery']['table_name']
)

# Initialize Supabase client
supabase_client = SupabaseInsightsClient(config_loader.config_data)

# Process contact...
```

## Project Structure

```
member-insights-processor-standalone/
├── src/member_insights_processor/    # Main package
│   ├── core/                         # Core business logic
│   │   ├── llm/                      # LLM providers (OpenAI, Anthropic, Gemini)
│   │   └── utils/                    # Shared utilities (logging, tokens, claims)
│   ├── pipeline/                     # Orchestration and workflow
│   │   ├── runner.py                 # Main pipeline runner
│   │   ├── config.py                 # Configuration loader
│   │   ├── context.py                # Context manager (token budgeting)
│   │   └── filters.py                # Processing filter rules
│   └── io/                           # All I/O boundaries
│       ├── readers/                  # Data readers (BigQuery, Supabase)
│       └── writers/                  # Data writers (Airtable, Supabase, Markdown)
├── config/                           # Configuration files
│   ├── config.yaml                   # Main configuration
│   ├── processing_filters.yaml       # ENI type/subtype rules
│   └── system_prompts/               # LLM prompt templates
├── var/                              # Runtime artifacts (gitignored)
│   ├── logs/                         # All log files
│   │   ├── runs/                     # Run summary outputs
│   │   └── claims/                   # Parallel processing claims
│   └── output/                       # Generated outputs
└── tests/                            # Test files
```

## Components

### 1. BigQuery Reader ([io/readers/bigquery.py](src/member_insights_processor/io/readers/bigquery.py))
- Connects to Google BigQuery with environment variable credentials
- SQL-first filtering: queries per `(eni_source_type, eni_source_subtype)` with LEFT JOIN to processing log
- Always processes `eni_source_subtype IS NULL` first, then explicit subtypes from `config/processing_filters.yaml`
- Prevents reprocessing via `elvis.eni_processing_log` table
- Prioritized contact selection for batch processing

### 2. Configuration Loader ([pipeline/config.py](src/member_insights_processor/pipeline/config.py))
- Manages YAML configuration files (`config/config.yaml`, `config/processing_filters.yaml`)
- Maps ENI types to context files
- Handles system prompt configurations
- Provides parallel processing configuration

### 3. Multi-AI Processor ([core/llm/](src/member_insights_processor/core/llm/))
- **OpenAI** ([openai.py](src/member_insights_processor/core/llm/openai.py)) - GPT-4, GPT-5, o1 models
- **Anthropic** ([anthropic.py](src/member_insights_processor/core/llm/anthropic.py)) - Claude 3.5, 3.7 models
- **Gemini** ([gemini.py](src/member_insights_processor/core/llm/gemini.py)) - Gemini Pro, Flash models
- Configurable AI provider selection via config

### 4. Context Manager ([pipeline/context.py](src/member_insights_processor/pipeline/context.py))
- Token-budgeted context assembly per ENI group
- Loads existing insights from Supabase (JSON format)
- Renders system prompt templates with `{{variable}}` substitution
- Enforces token limits and manages context windows
- Four context variables: `current_structured_insight`, `eni_source_type_context`, `eni_source_subtype_context`, `new_data_to_process`

### 5. Supabase Writer ([io/writers/supabase.py](src/member_insights_processor/io/writers/supabase.py))
- PostgreSQL JSONB storage for structured insights
- Intelligent upsert logic with automatic merging
- Comprehensive retry logic and error handling
- Versioning with `is_latest` flag and incremented `version` field
- Consolidated ENI ID: `COMBINED-{contact_id}-ALL`

### 6. Airtable Writer ([io/writers/airtable.py](src/member_insights_processor/io/writers/airtable.py))
- Syncs structured insights to Airtable
- Contact lookup and linking to master table (`tblkKWKRCEwl6aGDc`)
- Creates note submission records
- **Requirement**: Contact must exist in Airtable master table before sync

### 7. Parallel Processing ([core/utils/](src/member_insights_processor/core/utils/))
- **Claims System** ([claims.py](src/member_insights_processor/core/utils/claims.py)) - File-based distributed locking to prevent duplicate processing
- **Run Summary** ([run_summary.py](src/member_insights_processor/core/utils/run_summary.py)) - Event-driven observability system
- ThreadPoolExecutor-based concurrent contact processing
- Configurable worker count via `--max-concurrent-contacts`

### 8. Processing Log Manager ([io/log_manager.py](src/member_insights_processor/io/log_manager.py))
- Tracks processed ENI IDs in BigQuery table `elvis.eni_processing_log`
- Batch marking of processed ENIs
- Warehouse-side filtering to exclude already processed records

## Context Files

Context files provide domain-specific information for different member types:

```markdown
# context/professional/consultant.md
# Professional Consultant Context

## Background & Characteristics
Professional consultants are experienced practitioners...

## Typical Engagement Patterns
- Knowledge sharing and thought leadership
- High-value networking events
- Strategic relationship building

## Recommendations
- Provide exclusive industry insights
- Facilitate client introductions
- Offer advanced certification programs
```

## System Prompts

System prompts define how the AI should analyze and respond:

```markdown
# config/system_prompts/member_summary.md
# Member Summary Generation

You are an AI assistant specialized in analyzing member data...

## Analysis Framework
1. Engagement Patterns
2. Professional Profile  
3. Learning & Development
4. Network & Community

## Output Format
### Member Overview
### Key Insights
### Recommendations
```

## Output Format

Generated markdown files include structured metadata and insights:

```markdown
---
contact_id: "CONTACT_123"
eni_id: "ENI_456"
generated_at: "2024-01-15T10:30:00"
eni_type: "professional"
eni_subtype: "consultant"
---

# Member Insights for CONTACT_123

## Member Overview
This member is a senior consultant with 8+ years of experience...

## Key Insights
- High engagement with industry content
- Strong networking activity
- Focus on thought leadership

## Recommendations
- Invite to speak at upcoming events
- Provide early access to research reports
- Facilitate introductions to potential clients
```

## Monitoring & Logging

The system provides comprehensive logging and monitoring:

- **Processing Logs**: Detailed logs of all operations
- **Error Handling**: Graceful error recovery and reporting
- **Progress Tracking**: Real-time progress updates for batch operations
- **Statistics**: Comprehensive processing statistics and system health

## Error Handling

The system includes robust error handling:

- **Connection Failures**: Automatic retry with exponential backoff
- **Rate Limiting**: Respects API rate limits with intelligent throttling
- **Data Validation**: Validates input data and configurations
- **Graceful Degradation**: Continues processing when individual records fail

## Performance Considerations

- **Batch Processing**: Efficient batch operations for multiple contacts
- **Caching**: Intelligent caching of configuration and context data
- **Memory Management**: Optimized for large datasets
- **Parallel Processing**: Supports concurrent operations where safe

## Security

- **Environment Variables**: Sensitive credentials stored as environment variables
- **File Permissions**: Proper file access controls
- **API Security**: Secure API key management
- **Data Privacy**: Respects member data privacy and GDPR compliance

## Troubleshooting

### Virtual Environment Issues

**Problem**: `python: command not found` or wrong Python version
```bash
# Solution: Make sure virtual environment is activated
source venv/bin/activate
which python  # Should show venv/bin/python
```

**Problem**: `ModuleNotFoundError` when running the application
```bash
# Solution: Install dependencies in virtual environment
source venv/bin/activate
pip install -r requirements.txt
```

### Environment Variables Issues

**Problem**: `Anthropic API key not provided` or similar API key errors
```bash
# Solution: Check your .env file exists and has correct format
ls -la .env  # Should show the file
cat .env     # Check contents (be careful not to expose keys publicly)

# Ensure no 'export' statements in .env file
# Correct:   ANTHROPIC_API_KEY="your-key"
# Incorrect: export ANTHROPIC_API_KEY="your-key"
```

**Problem**: `AIRTABLE_BASE_ID` or `AIRTABLE_TABLE_ID` missing warnings
```bash
# Solution: Add missing variables to .env file or ignore if not using Airtable
echo 'AIRTABLE_BASE_ID="appXXXXXXXXXXXXXX"' >> .env
echo 'AIRTABLE_TABLE_ID="tblXXXXXXXXXXXXXX"' >> .env
```

### Validation Issues

**Problem**: Validation shows warnings or failures
```bash
# Run validation to see specific issues
python src/main.py --validate

# Common solutions:
# 1. Check BigQuery credentials path in .env
# 2. Verify API keys are valid and have proper permissions
# 3. Confirm Supabase URL and service role key are correct
```

### Performance Issues

**Problem**: Processing is slow or timing out
```bash
# Solution: Process smaller batches
python src/main.py --limit 1  # Start with one contact
python src/main.py --limit 5  # Then try small batches
```

### File Permission Issues

**Problem**: Cannot write to output directory
```bash
# Solution: Check and fix permissions
chmod 755 output/
mkdir -p output/structured_insights
```

## Testing

```bash
# Run unit tests
pytest tests/

# Run with coverage
pytest tests/ --cov=src/

# Run BigQuery processing filters integration test (logs per combination)
python tests/test_processing_filters.py --contact-id CNT-HvA002554 --verbose

# Or use the runner script
python scripts/run_processing_filters_test.py CNT-HvA002554

# Run specific test module
pytest tests/test_bigquery_connector.py
```

## Context Manager and Token Budgeting (New)

The pipeline now uses a consolidated `ContextManager` to assemble the full context for each LLM call with token-aware batching.

- **Location**: `src/context_management/context_manager.py`
- **Responsibilities**:
  - Load config (`config/config.yaml`) and resolve context file paths per `eni_source_type` and `eni_source_subtype`
  - Load and render the system prompt template (`config/system_prompts/structured_insight.md`)
  - Fetch the latest existing structured insight from Supabase (if available)
  - Build the four context variables for the template:
    - `{{current_structured_insight}}` (JSON string; see below)
    - `{{eni_source_type_context}}`
    - `{{eni_source_subtype_context}}`
    - `{{new_data_to_process}}` (rows are truncated to fit the remaining token budget)
  - Estimate tokens and enforce budgets before adding new rows

### Context 1 Now Uses JSON

- The `{{current_structured_insight}}` variable is injected as a JSON object string with fields:
  - `personal`, `business`, `investing`, `3i`, `deals`, `introductions`
- If no prior summary exists, an all-empty JSON object is provided. This improves reliability for the LLM to append new content while preserving structure.

### Token Budget Settings

Configured under `processing` in `config/config.yaml`:

```yaml
processing:
  context_window_tokens: 200000           # Total tokens available for the prompt
  reserve_output_tokens: 8000             # Held back for model output
  max_new_data_tokens_per_group: 12000    # Max tokens for appended data per ENI group
```

- The system prompt is rendered with the first three variables to compute base token usage.
- Remaining tokens are allocated to `{{new_data_to_process}}` and rows are added until the budget is reached.

## Context Preview (New)

Use the preview to see exactly what would be sent to the LLM per ENI group, including the fully rendered system prompt and token stats.

### Run the Preview

```bash
# Activate venv first
source venv/bin/activate

# Run the preview test (writes a markdown report to logs/)
pytest tests/test_context_preview.py -q
```

- Output file: `logs/context_preview_<CONTACT_ID>_<TIMESTAMP>.md`
- The report contains:
  - A summary table:
    - `run_number | eni_source_type | eni_source_sub_type | tokens_system_plus_source_ctx | remaining_tokens | total_rows_in_group | rows_processed | total_tokens_rendered`
  - For each would-be LLM call:
    - The full rendered system prompt (with all variables substituted)
    - Token statistics and the number of rows actually included

### Notes

- The preview does not upsert to Supabase. It uses the latest available insight (or a default stub in tests) to simulate the context.
- If BigQuery is unavailable, the preview uses a small synthetic dataset and still renders the context and token stats.

## Per-Group Processing Mode (New)

The processor now executes one LLM call per ENI group:
- Group key: `(eni_source_type, eni_source_subtype)`
- For each group with unprocessed rows:
  - Query BigQuery via `load_contact_data_filtered(contact_id, type, subtype)`
  - Build a token-budgeted context with `ContextManager.build_context_variables(...)`
  - Call the LLM once for the group
  - Upsert to Supabase per group
  - Mark only that group’s ENIs as processed immediately

Benefits: tighter, relevant context and reduced prompt size per call. Note this increases the number of total LLM calls proportionally to the number of populated groups.

## Inline Citations Now Include `source_type`

System prompt (`config/system_prompts/structured_insight.md`) requires every bullet to include sub-bullets with citations in the format:

```
[logged_date,eni_id,source_type]
```

The appended context (`new_data_to_process`) now provides per-row lines like:

```
- {description}
  * [YYYY-MM-DD,ENI-...,airtable_notes]
```

This enables the model to produce correctly formatted citations.

## ContextManager Highlights

Location: `src/context_management/context_manager.py`
- Centralizes config access (AI provider, Airtable, Supabase), context path resolution, system prompt loading, token estimation, and validation
- Produces the four variables for the template:
  - `{{current_structured_insight}}` (fetched from Supabase if available)
  - `{{eni_source_type_context}}`
  - `{{eni_source_subtype_context}}` (empty when subtype is null)
  - `{{new_data_to_process}}` (token-limited; includes description + citation `[date,eni_id,source_type]` lines)
- Includes system prompt in token estimation and limits appended rows to fit remaining budget

## Context Preview (.md) Log

Run:

```bash
pytest -q tests/test_context_preview.py
```

This generates `logs/context_preview_{CONTACT_ID}_{TIMESTAMP}.md` with:
- A summary table of all would-be LLM calls (one per group)
- Fully rendered system prompt per call (with the appended group data)
- Token stats (base/system context, available for new data, rendered total)

## Debug LLM Tracing (New)

For production debugging and prompt analysis, the system can log detailed LLM traces when `debug.llm_trace.enabled` is set to `true` in `config/config.yaml`.

### Configuration

```yaml
debug:
  enable_debug_mode: true
  llm_trace:
    enabled: true
    output_dir: "logs/llm_traces"
    include_rendered_prompts: true
    include_token_stats: true
    include_response: true
    file_naming_pattern: "llm_trace_{contact_id}_{timestamp}.md"
```

### Usage

```bash
# Process with debug tracing enabled
python src/main.py --contact-id "CNT-ABC123"
```

### Output

Debug traces are written to `logs/llm_traces/llm_trace_{CONTACT_ID}_{TIMESTAMP}.md` and include:

- **Request sections**: Full rendered system prompt per ENI group (includes `structured_insight.md` template with all variables substituted)
- **Token Stats**: Detailed token breakdown including:
  - `existing_summary_tokens`: Tokens in current Supabase summary
  - `base_tokens`: System prompt + context tokens
  - `new_data_tokens_used`: Tokens for new data within budget
  - `rendered_full_tokens`: Total prompt tokens sent to LLM
- **Response sections**: Complete LLM output per group

### Key Features

- **Production Ready**: Runs during actual processing (not just preview)
- **Per-Group Detail**: One request/response pair per `(eni_source_type, eni_source_subtype)` group
- **Token metrics**: Rendered prompt tokens and output token estimates per group
- **Template Verification**: Confirms `{{variable}}` substitution in `structured_insight.md`

### Benefits

- Debug prompt composition issues
- Verify context variable injection
- Monitor token usage patterns
- Analyze LLM response quality
- Troubleshoot template rendering

## OpenAI Configuration Notes

- Env var fallback supported: `OPENAI_API_KEY` or `OPEN_AI_KEY`
- For modern models (gpt-5, o1, gpt-4.1, gpt-4o):
  - Use `

## Production Deployment

This application is production-ready and can be deployed to Google Cloud Platform using:

- **Cloud Run Jobs** (Recommended) - Scheduled or on-demand batch processing
- **Cloud Run** - API-based or triggered processing
- **Google Kubernetes Engine (GKE)** - Advanced orchestration

See **[DEPLOYMENT.md](./DEPLOYMENT.md)** for comprehensive deployment instructions including:
- Docker containerization and local testing
- Cloud Run and Cloud Run Jobs setup
- Secret management with Google Secret Manager
- Scheduling with Cloud Scheduler
- Resource sizing and cost optimization
- Monitoring and logging setup

### Quick Docker Build

```bash
# Build production image
docker build -t member-insights-processor:latest --target production .

# Test locally
docker run --rm --env-file .env member-insights-processor:latest python -m member_insights_processor.pipeline.runner --validate
```

## Recent Changes (October 2025)

### Project Restructuring
- **Package Structure**: Reorganized into clean `member_insights_processor` package hierarchy
- **Core Modules**: `core/` (business logic), `pipeline/` (orchestration), `io/` (I/O boundaries)
- **Runtime Artifacts**: Consolidated to `var/` directory (logs, outputs, claims)

### Production Features
- **Parallel Processing**: ThreadPoolExecutor-based concurrent processing with distributed locking
- **Claims System**: File-based claims prevent duplicate processing across workers
- **Run Summary**: Event-driven observability system for production runs
- **Prioritized Selection**: SQL-based contact selection prioritizing never-processed contacts

### Data Pipeline
- **Standalone Repository**: Extracted from monorepo with full git history preserved
- **Supabase Integration**: PostgreSQL JSONB storage with intelligent upsert logic
- **Consolidated ENI IDs**: `COMBINED-{contact_id}-ALL` for single record per contact
- **Versioning**: `is_latest` flag and incremented `version` field
- **Airtable Sync**: Decoupled post-processing that requires contacts in master table

### AI Processing
- **Context 1 JSON Format**: Existing insights provided as JSON (not markdown) for better LLM adherence
- **Token Budgeting**: Per-ENI-group token limits with dynamic row allocation
- **Debug Tracing**: Optional LLM trace logging for rendered prompts, token stats, and responses
- **Multi-Provider Support**: OpenAI (GPT-4, GPT-5, o1), Anthropic (Claude 3.5, 3.7), Gemini

### Developer Experience
- **Updated Documentation**: Comprehensive onboarding guide and updated examples
- **Docker Ready**: Production-optimized containerization
- **Environment Variables**: All credentials via env vars (no JSON file mounting)

## Contributing

This is proprietary software owned by 3i Members. For contribution guidelines and development setup, see [CONTRIBUTING.md](CONTRIBUTING.md).

Internal team members:
1. Create a feature branch (`git checkout -b feature/amazing-feature`)
2. Commit your changes (`git commit -m 'Add amazing feature'`)
3. Push to the branch (`git push origin feature/amazing-feature`)
4. Open a Pull Request

## License

Copyright © 2024-2025 3i Members. All rights reserved.

This is proprietary and confidential software. See [LICENSE](LICENSE) for details.

## Support

For issues, questions, or contributions, please open an issue on GitHub or contact the maintainers.