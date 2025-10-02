# Phase 2 Migration Guide

**Date:** 2024-10-01
**Phase:** 2 - Structural Changes
**Status:** IN PROGRESS

## Overview

Reorganizing `src/` into a single top-level package with clear boundaries:
- **core/** - LLM logic (OpenAI default, Anthropic, Gemini)
- **pipeline/** - Orchestration (context, filters, runner)
- **io/** - All I/O boundaries (readers, writers, schema)

## Directory Structure Changes

### Before (Phase 1)
```
src/
├── ai_processing/              # 3 files
├── context_management/         # 5 files
├── data_processing/            # 7 files
├── output_management/          # 4 files
├── utils/                      # 2 files
└── main.py
```

### After (Phase 2)
```
src/member_insights_processor/
├── core/
│   ├── llm/                    # OpenAI (default), Anthropic, Gemini
│   │   ├── openai.py
│   │   ├── anthropic.py
│   │   └── gemini.py
│   └── utils/                  # Token utils, logging
│       ├── logging.py
│       └── tokens.py
├── pipeline/
│   ├── context.py              # Context assembly & token budgeting
│   ├── filters.py              # Processing filters
│   ├── config.py               # Config loader
│   └── runner.py               # Main pipeline orchestration (from main.py)
└── io/
    ├── readers/
    │   ├── bigquery.py
    │   ├── supabase.py
    │   └── markdown.py
    ├── writers/
    │   ├── airtable.py
    │   ├── supabase.py
    │   ├── json.py
    │   └── markdown.py
    ├── schema.py               # Pydantic models
    └── log_manager.py          # Processing log tracker
```

## File Mapping

### Core Module (LLM Logic)

| Old Path | New Path | Notes |
|----------|----------|-------|
| `ai_processing/openai_processor.py` | `core/llm/openai.py` | Default LLM client |
| `ai_processing/anthropic_processor.py` | `core/llm/anthropic.py` | Alternative client |
| `ai_processing/gemini_processor.py` | `core/llm/gemini.py` | Alternative client |
| `utils/enhanced_logger.py` | `core/utils/logging.py` | Renamed for clarity |
| `utils/token_utils.py` | `core/utils/tokens.py` | Renamed for clarity |

### Pipeline Module (Orchestration)

| Old Path | New Path | Notes |
|----------|----------|-------|
| `context_management/context_manager.py` | `pipeline/context.py` | Main context builder |
| `context_management/processing_filter.py` | `pipeline/filters.py` | Processing filters |
| `context_management/config_loader.py` | `pipeline/config.py` | Config loader |
| `context_management/markdown_reader.py` | `io/readers/markdown.py` | Moved to I/O |
| `main.py` → `MemberInsightsProcessor` class | `pipeline/runner.py` | Pipeline orchestration |

### I/O Module (Readers/Writers/Schema)

| Old Path | New Path | Notes |
|----------|----------|-------|
| `data_processing/bigquery_connector.py` | `io/readers/bigquery.py` | Rename: BigQueryReader |
| `data_processing/supabase_client.py` | `io/readers/supabase.py` | Rename: SupabaseReader |
| `context_management/markdown_reader.py` | `io/readers/markdown.py` | Context file reader |
| `output_management/airtable_writer.py` | `io/writers/airtable.py` | Keep: AirtableWriter |
| `output_management/supabase_airtable_sync.py` | `io/writers/supabase.py` | Supabase writer + sync |
| `output_management/json_writer.py` | `io/writers/json.py` | Keep: JSONWriter |
| `output_management/markdown_writer.py` | `io/writers/markdown.py` | Keep: MarkdownWriter |
| `data_processing/schema.py` | `io/schema.py` | Pydantic models |
| `data_processing/log_manager.py` | `io/log_manager.py` | Processing log tracker |
| `data_processing/supabase_insights_processor.py` | `io/writers/supabase.py` | Merge with supabase writer |

### Deprecated/Removed

| Old Path | Action | Reason |
|----------|--------|--------|
| `data_processing/migration_utils.py` | Keep for now | May need for backfills |

## Class Name Changes

### Core
- `OpenAIProcessor` → `OpenAIClient` (default)
- `AnthropicProcessor` → `AnthropicClient`
- `GeminiProcessor` → `GeminiClient`
- `create_enhanced_logger()` → Stays same, imported from `core.utils.logging`

### Pipeline
- `ContextManager` → `ContextBuilder`
- `ProcessingFilter` → `FilterEngine`
- `ConfigLoader` → Stays same

### I/O Readers
- `BigQueryConnector` → `BigQueryReader`
- `SupabaseInsightsClient` → `SupabaseReader`
- `MarkdownReader` → Stays same

### I/O Writers
- `StructuredInsightsAirtableWriter` → `AirtableWriter`
- `SupabaseInsightsProcessor` → Merged into `SupabaseWriter`
- `JSONWriter` → Stays same
- `MarkdownWriter` → Stays same

## Import Changes

### Before
```python
from ai_processing.openai_processor import create_openai_processor
from context_management.context_manager import ContextManager
from data_processing.bigquery_connector import create_bigquery_connector
from output_management.airtable_writer import create_structured_airtable_writer
```

### After
```python
from member_insights_processor.core.llm.openai import OpenAIClient
from member_insights_processor.pipeline.context import ContextBuilder
from member_insights_processor.io.readers.bigquery import BigQueryReader
from member_insights_processor.io.writers.airtable import AirtableWriter
```

## Breaking Changes

1. **Import paths** - All imports need updating
2. **Class names** - Some classes renamed for consistency
3. **Main entrypoint** - `src/main.py` becomes `pipeline/runner.py`
4. **Package structure** - Need to import from `member_insights_processor.*`

## Testing Checklist

After migration, test:
- [ ] Import all modules without errors
- [ ] BigQuery connection and data fetch
- [ ] Supabase connection and operations
- [ ] Airtable writer functionality
- [ ] LLM client initialization (OpenAI, Anthropic, Gemini)
- [ ] Context assembly and token budgeting
- [ ] Processing filters
- [ ] End-to-end pipeline run with `--limit 1`

## Debugging Guide

If imports fail:
1. Check `PYTHONPATH` includes `src/`
2. Verify all `__init__.py` files exist
3. Check class name changes (see table above)

If pipeline fails:
1. Check config paths still point to `var/logs/` and `var/output/`
2. Verify context files still load from `context/`
3. Check environment variables unchanged

## Rollback Plan

If Phase 2 causes issues:
```bash
git revert HEAD  # Revert to Phase 1 completion
```

Phase 1 (completed) provides stable checkpoint with `var/` structure.

---

**Next:** Phase 3 will add single CLI entrypoint (`mip` command)
