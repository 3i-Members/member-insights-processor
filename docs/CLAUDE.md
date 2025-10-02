# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Member Insights Processor is a production-ready Python-based AI pipeline that:
1. Loads member data from BigQuery with SQL-first filtering to avoid reprocessing
2. Generates structured insights using Claude/Gemini/OpenAI
3. Stores results in Supabase (PostgreSQL JSONB) with intelligent upsert logic
4. Optionally syncs to Airtable in a decoupled post-processing step
5. Supports parallel processing with distributed locking for high-throughput production runs

The system processes data in **per-ENI-group mode**: one LLM call per `(eni_source_type, eni_source_subtype)` combination with token-budgeted context.

## Package Structure

**Important**: The codebase was restructured into a clean package hierarchy. All code lives under `src/member_insights_processor/`:

- `core/` - Business logic (LLM providers, utilities)
- `pipeline/` - Orchestration (runner, config, context, filters)
- `io/` - I/O boundaries (readers, writers)

Always use fully qualified imports: `from member_insights_processor.pipeline.config import ConfigLoader`

## Common Commands

### Development
```bash
# Always activate virtual environment and set PYTHONPATH first
source venv/bin/activate
export PYTHONPATH=src

# Install dependencies
pip install -r requirements.txt

# Validate setup (checks env vars, connections, config)
python -m member_insights_processor.pipeline.runner --validate

# Process single contact (recommended for testing)
python -m member_insights_processor.pipeline.runner --contact-id CNT-ABC123

# Process with parallel workers (production)
python -m member_insights_processor.pipeline.runner --limit 100 --parallel --max-concurrent-contacts 5

# Dry run (no database writes)
python -m member_insights_processor.pipeline.runner --limit 5 --dry-run

# View processing filter rules
python -m member_insights_processor.pipeline.runner --show-filter
```

### Testing
```bash
# Set PYTHONPATH
export PYTHONPATH=src

# Run basic validation test
python -m member_insights_processor.pipeline.runner --validate

# Test with single contact
python -m member_insights_processor.pipeline.runner --contact-id CNT-ABC123 --limit 1

# Test parallel processing with small batch
python -m member_insights_processor.pipeline.runner --limit 10 --parallel --max-concurrent-contacts 3
```

### Supabase Operations
```bash
# Validate Supabase connection
python scripts/setup_supabase.py --validate

# Migrate existing JSON files to Supabase
python scripts/setup_supabase.py --migrate --dry-run
python scripts/setup_supabase.py --migrate
```

### Airtable Sync (Decoupled)
```bash
# Sync latest insights from Supabase to Airtable
PYTHONPATH="src" python scripts/airtable_sync_insights.py --limit 1000 --force
```

### Docker
```bash
# Build production image
docker build -t member-insights-processor:latest --target production .

# Test locally
docker run --rm --env-file .env member-insights-processor:latest python src/main.py --validate
```

## Architecture

### Core Processing Flow

1. **Entry Point**: [src/main.py](src/main.py) - `MemberInsightsProcessor` orchestrates the pipeline
2. **Per-Group Iteration**: For each contact, query combinations from [config/processing_filters.yaml](config/processing_filters.yaml)
3. **SQL-First Filtering**: [BigQueryConnector](src/data_processing/bigquery_connector.py) LEFT JOINs to `elvis.eni_processing_log` to exclude processed ENIs
4. **Context Assembly**: [ContextManager](src/context_management/context_manager.py) builds token-budgeted prompts per group
5. **AI Processing**: One LLM call per `(eni_source_type, eni_source_subtype)` group
6. **Supabase Upsert**: Results stored with `eni_id = COMBINED-{contact_id}-ALL`
7. **Processing Log**: Batch-mark ENIs as processed in BigQuery
8. **Airtable Sync** (Optional): Post-processing script pulls from Supabase

### Key Components

- **BigQueryConnector** ([src/data_processing/bigquery_connector.py](src/data_processing/bigquery_connector.py))
  - Builds queries per ENI group with LEFT JOIN filtering
  - Manages `elvis.eni_processing_log` table (marks processed ENIs)
  - Always processes `eni_source_subtype IS NULL` first, then explicit subtypes

- **ContextManager** ([src/context_management/context_manager.py](src/context_management/context_manager.py))
  - Centralizes config access and context file resolution
  - Loads system prompt templates (supports `{{variable}}` substitution)
  - Fetches existing structured insight from Supabase (JSON format)
  - Enforces token budgets: reserves output tokens, limits `{{new_data_to_process}}`
  - Four context variables:
    - `{{current_structured_insight}}` - JSON string from Supabase
    - `{{eni_source_type_context}}` - Markdown from [context/](context/) directory
    - `{{eni_source_subtype_context}}` - Markdown from [context/](context/) directory
    - `{{new_data_to_process}}` - Token-limited rows with inline citations `[date,eni_id,source_type]`

- **SupabaseInsightsClient** ([src/data_processing/supabase_client.py](src/data_processing/supabase_client.py))
  - PostgreSQL JSONB storage with retry logic
  - Intelligent upsert: merges new data into existing insights
  - Consolidated record per contact: `eni_id = COMBINED-{contact_id}-ALL`
  - Versioning: `is_latest` flag, incremented `version` field

- **SupabaseInsightsProcessor** ([src/data_processing/supabase_insights_processor.py](src/data_processing/supabase_insights_processor.py))
  - Memory-efficient batch processing
  - Loads existing insights before processing new data
  - Handles JSON parsing (preferred) and markdown fallback

- **AI Processors**
  - [AnthropicProcessor](src/ai_processing/anthropic_processor.py) - Claude integration
  - [GeminiProcessor](src/ai_processing/gemini_processor.py) - Gemini Pro integration
  - [OpenAIProcessor](src/ai_processing/openai_processor.py) - OpenAI GPT integration
  - Selected via `processing.ai_provider` in [config.yaml](config/config.yaml)

### Configuration Files

- **[config/config.yaml](config/config.yaml)** - Main configuration
  - BigQuery: project, dataset, table names
  - Supabase: connection settings, batch sizes
  - AI providers: model names, generation settings, rate limits
  - ENI mappings: maps types/subtypes to context files
  - System prompts: references to prompt templates
  - Token budgeting: `context_window_tokens`, `reserve_output_tokens`, `max_new_data_tokens_per_group`
  - Debug settings: LLM trace logging (writes rendered prompts, tokens, responses)

- **[config/processing_filters.yaml](config/processing_filters.yaml)** - Processing rules
  - Defines which ENI types and subtypes to process
  - NULL subtypes always processed first for each type
  - Example: `airtable_notes` → processes `NULL` + `investing_preferences` + `intro_preferences`

- **[config/system_prompts/structured_insight.md](config/system_prompts/structured_insight.md)** - Primary prompt template
  - Uses `{{variable}}` substitution
  - Requires inline citations: `[logged_date,eni_id,source_type]`

### Per-Group Processing Mode

The system executes **one LLM call per ENI group**:
1. Query BigQuery for unprocessed rows matching `(eni_source_type, eni_source_subtype)`
2. Build token-budgeted context with `ContextManager.build_context_variables(...)`
3. Call LLM once for the group
4. Upsert to Supabase (consolidated under `COMBINED-{contact_id}-ALL`)
5. Mark only that group's ENIs as processed in BigQuery

Benefits: tighter context per call, reduced prompt size, better relevance. Trade-off: more LLM calls per contact.

### Context 1: JSON Format

`{{current_structured_insight}}` is now provided as JSON (not markdown) with fields:
- `personal`, `business`, `investing`, `3i`, `deals`, `introductions`

If no prior summary exists, an all-empty JSON object is provided. Improves LLM adherence to structure.

### Token Budgeting

Settings in [config/config.yaml](config/config.yaml) under `processing`:
```yaml
context_window_tokens: 400000           # Total tokens available for prompt
reserve_output_tokens: 8000             # Held back for model output
max_new_data_tokens_per_group: 12000    # Max tokens for appended data per ENI group
```

Process:
1. Render system prompt with first three context variables
2. Estimate base token usage (system prompt + existing summary + context files)
3. Allocate remaining tokens to `{{new_data_to_process}}`
4. Add rows until budget exhausted

### Debug LLM Tracing

When `debug.llm_trace.enabled: true` in [config.yaml](config/config.yaml):
- Writes `logs/llm_traces/llm_trace_{contact_id}_{timestamp}.md` during processing
- Includes: fully rendered system prompt per group, token stats, LLM response
- Token breakdown: `existing_summary_tokens`, `base_tokens`, `new_data_tokens_used`, `rendered_full_tokens`
- Production-ready: runs during actual processing, not just preview

### Processing Log (BigQuery)

Table: `i-sales-analytics.elvis.eni_processing_log`

Prevents reprocessing by:
1. LEFT JOIN to processing log in BigQuery queries
2. Filter: `epl.eni_id IS NULL` (only unprocessed rows)
3. After successful processing, batch-insert ENI IDs to log

### Airtable Sync (Decoupled)

Script: [scripts/airtable_sync_insights.py](scripts/airtable_sync_insights.py)

- Runs independently from main processing
- Queries Supabase: `WHERE is_latest = true AND generator='structured_insight'`
- Creates note submission in Airtable per contact
- Consolidated ENI ID: `COMBINED-{contact_id}-ALL`

## Environment Variables

All configuration is via environment variables (no JSON file mounting required). This simplifies container deployment.

### Setup

```bash
# Extract Google Cloud credentials from service account JSON
python scripts/extract_service_account.py /path/to/service-account.json --output .env

# Or manually add to .env:
GCP_PROJECT_ID="your-project-id"
GCP_PRIVATE_KEY_ID="your-private-key-id"
GCP_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
GCP_CLIENT_EMAIL="your-sa@project.iam.gserviceaccount.com"
GCP_CLIENT_ID="123456789"

# AI Provider (choose one)
OPENAI_API_KEY="your-openai-api-key"
# ANTHROPIC_API_KEY="your-anthropic-api-key"
# GEMINI_API_KEY="your-gemini-api-key"

# Supabase (required)
SUPABASE_URL="https://your-project.supabase.co"
SUPABASE_SERVICE_ROLE_KEY="your-service-role-key"

# Airtable (optional - only for sync)
AIRTABLE_API_KEY="your-airtable-api-key"
AIRTABLE_BASE_ID="your-base-id"
AIRTABLE_TABLE_ID="tblXXXXXXXXXXXXXX"  # Use table ID (from URL), not table name
```

See [.env.example](.env.example) for detailed guidance.

## Important Implementation Notes

### Adding New ENI Types

1. Add context file(s) to [context/](context/) directory
2. Update `eni_mappings` in [config/config.yaml](config/config.yaml)
3. Add to `eni_processing_rules` in [config/processing_filters.yaml](config/processing_filters.yaml)
4. Test with single contact: `python src/main.py --contact-id CNT-XYZ --limit 1`

### Modifying System Prompts

1. Edit template in [config/system_prompts/](config/system_prompts/)
2. Use `{{variable}}` for substitution (four supported variables)
3. Preview context: `pytest -q tests/test_context_preview.py`
4. Review output in `logs/context_preview_{contact_id}_{timestamp}.md`

### Debugging Processing Issues

1. Enable debug mode in [config.yaml](config/config.yaml): `debug.enable_debug_mode: true`
2. Enable LLM trace: `debug.llm_trace.enabled: true`
3. Process single contact: `python src/main.py --contact-id CNT-ABC123 --limit 1`
4. Review trace: `logs/llm_traces/llm_trace_CNT-ABC123_{timestamp}.md`
5. Check token stats and rendered prompts

### Token Loss Handling

- Per-contact log line: `[TOKEN-LOSS] Summary for <contact_id>: events={n} | groups_skipped={m} | records_skipped={k}`
- Single-contact console output includes same summary
- Token-loss retry is disabled for versioned insights (outputs accepted and versioned)

### Testing Strategy

- **Component tests** ([tests/test_components.py](tests/test_components.py)): No external dependencies
- **Integration tests** ([tests/test_with_env.py](tests/test_with_env.py)): Require BigQuery, Supabase
- **Context preview** ([tests/test_context_preview.py](tests/test_context_preview.py)): Token budgeting validation
- **Processing filters** ([tests/test_processing_filters.py](tests/test_processing_filters.py)): Real BigQuery data

### Database Schema

Supabase table: `elvis__structured_insights`
- Primary key: `id` (auto-increment)
- `contact_id`: Member identifier
- `eni_id`: Consolidated as `COMBINED-{contact_id}-ALL`
- `generator`: Always `'structured_insight'`
- `structured_insight`: JSONB with sections
- `eni_source_types`: Array of processed types
- `eni_source_subtypes`: Array of processed subtypes
- `total_eni_ids`: Counter
- `record_count`: Counter
- `version`: Incremented on updates
- `is_latest`: Boolean flag (only one `true` per contact)

See [config/supabase_schema.sql](config/supabase_schema.sql) for full schema.

## Deployment

Docker-ready with production-optimized image. See README for:
- Cloud Run Jobs (recommended)
- Cloud Run
- Google Kubernetes Engine (GKE)
- Secret management with Google Secret Manager

## Recent Changes (October 2025)

- Extracted as standalone repository with full git history
- Production deployment configurations (Docker, Cloud Run, GKE)
- Supabase-driven consolidated upserts per contact
- Context 1 now JSON (not markdown) for structure compliance
- Token-budgeted per-group processing mode
- Debug LLM tracing for rendered prompts and token stats
- Robust insight parsing (JSON preferred, markdown fallback)
