# Supabase Integration for Member Insights Processor

This document explains how to set up and use the Supabase integration for storing structured member insights.

## Overview

The Supabase integration provides:

- **NoSQL storage** for structured insights in PostgreSQL with JSONB support
- **Memory-efficient processing** with batch operations and caching
- **Decoupled Airtable sync** that pulls from Supabase instead of processing functions
- **Schema validation** and migration tools for existing data
- **Docker-optimized** memory management for containerized deployments

## Architecture

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│   BigQuery Data     │───▶│   AI Processing     │───▶│   Supabase Storage  │
│   (Source ENIs)     │    │   (Structured       │    │   (Insights DB)     │
└─────────────────────┘    │    Insights)        │    └─────────────────────┘
                           └─────────────────────┘              │
                                                                ▼
                           ┌─────────────────────┐    ┌─────────────────────┐
                           │   Airtable Sync     │◀───│   Supabase Client   │
                           │   (Decoupled)       │    │   (CRUD Operations) │
                           └─────────────────────┘    └─────────────────────┘
```

## Setup

### 1. Environment Variables

Set the following environment variables:

```bash
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="your-service-role-key"
```

You can also set these in your `.env` file:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
```

### 2. Database Schema

Create the table in your Supabase project by running the SQL schema:

```sql
-- Run this in your Supabase SQL editor
-- File: config/supabase_schema.sql
```

Or use the PostgreSQL command line:

```bash
psql -h db.your-project.supabase.co -U postgres -d postgres -f config/supabase_schema.sql
```

### 3. Dependencies

Install the additional dependencies:

```bash
pip install supabase pydantic jsonschema
```

### 4. Configuration

Update your `config/config.yaml` to enable Supabase features:

```yaml
# Enable Supabase storage
features:
  enable_supabase_storage: true
  enable_memory_optimization: true

# Supabase configuration  
supabase:
  table_name: "elvis__structured_insights"
  max_retries: 3
  timeout: 30
  batch_size: 10

# Processing configuration
processing:
  enable_supabase_storage: true
  supabase_upsert_batch_size: 10
  memory_management:
    clear_processed_items: true
    use_weak_references: true
    max_memory_items: 1000
```

## Quick Start

### 1. Validate Setup

```bash
python scripts/setup_supabase.py --action check
```

### 2. Migrate Existing Data

```bash
# Validate existing JSON files
python scripts/setup_supabase.py --action migrate --dry-run

# Migrate to Supabase
python scripts/setup_supabase.py --action migrate
```

### 3. Test Processing

```python
from src.data_processing.supabase_client import SupabaseInsightsClient
from src.data_processing.supabase_insights_processor import SupabaseInsightsProcessor

# Initialize clients
client = SupabaseInsightsClient()
processor = SupabaseInsightsProcessor(client)

# Get processing statistics
stats = processor.get_processing_statistics()
print(f"Total insights in database: {stats['total_insights_in_db']}")
```

## Usage

### Processing Pipeline Integration

The main processing pipeline now includes Supabase integration:

```python
from src.main import MemberInsightsProcessor

# Initialize processor (now with Supabase support)
processor = MemberInsightsProcessor("config/config.yaml")

# Process insights - they'll be stored in Supabase
processor.process_contact("CNT-example123")
```

### Direct Supabase Operations

```python
from src.data_processing.supabase_client import SupabaseInsightsClient
from src.data_processing.schema import StructuredInsight, InsightMetadata, StructuredInsightContent

client = SupabaseInsightsClient()

# Create new insight
metadata = InsightMetadata(contact_id="CNT-test123", eni_id="ENI-456")
content = StructuredInsightContent(personal="Test info")
insight = StructuredInsight(metadata=metadata, insights=content)

created_insight, was_created = client.upsert_insight(insight)

# Retrieve insights
existing_insight = client.get_insight_by_contact_id("CNT-test123")

# Search insights
search_results = client.search_insights("investment preferences")

# List recent insights
recent_insights = client.list_insights(limit=10, order_by='updated_at')
```

### Batch Processing

```python
from src.data_processing.supabase_insights_processor import SupabaseInsightsProcessor

processor = SupabaseInsightsProcessor(client, batch_size=20)

# Process multiple insights with memory management
insights_data = [
    {
        "contact_id": "CNT-123",
        "eni_id": "ENI-456", 
        "insights": {"personal": "Info 1"},
        "member_name": "Member 1"
    },
    # ... more insights
]

state = processor.batch_process_insights(insights_data)
print(f"Processed {state.get_summary()['total_processed']} insights")
```

### Airtable Sync (Decoupled)

```python
from src.output_management.supabase_airtable_writer import SupabaseAirtableSync
from src.output_management.structured_airtable_writer import StructuredInsightsAirtableWriter

# Initialize sync service
airtable_writer = StructuredInsightsAirtableWriter(config)
sync_service = SupabaseAirtableSync(client, airtable_writer)

# Sync specific contact
result = sync_service.sync_contact_to_airtable("CNT-test123")

# Sync recent insights
results = sync_service.sync_recent_insights(hours_back=24)

# Full sync
all_results = sync_service.sync_all_insights()
```

## Memory Management

The integration includes advanced memory management for Docker deployments:

### Memory Manager

```python
from src.data_processing.supabase_insights_processor import MemoryManager

# Configure memory management
memory_manager = MemoryManager(
    max_items=1000,
    use_weak_references=True
)

# Get memory statistics
stats = memory_manager.get_stats()
print(f"Cached items: {stats['cached_items']}")
```

### Batch Processing with Memory Optimization

```python
processor = SupabaseInsightsProcessor(
    client,
    memory_manager=memory_manager,
    enable_memory_optimization=True
)

# Process with automatic memory cleanup
state = processor.batch_process_insights(
    insights_data,
    clear_memory_after_batch=True
)
```

## Schema and Data Models

### StructuredInsight Model

```python
from src.data_processing.schema import StructuredInsight

insight = StructuredInsight(
    metadata=InsightMetadata(
        contact_id="CNT-123",
        eni_id="ENI-456",
        member_name="John Doe",
        eni_source_types=["airtable_notes", "recurroo"],
        record_count=5
    ),
    insights=StructuredInsightContent(
        personal="Personal information with citations",
        business="Business background", 
        investing="Investment preferences",
        three_i="3i network activities",
        deals="Deal experience and interests",
        introductions="Introduction preferences"
    )
)
```

### Database Schema

The `elvis__structured_insights` table includes:

- **Core identifiers**: contact_id, eni_id, member_name
- **ENI metadata**: source types, subtypes, processing info
- **Insight content**: Full JSONB and extracted text fields
- **Processing metadata**: version, status, timestamps
- **Performance indexes**: GIN index on JSONB, B-tree on common queries

## Migration and Data Validation

### Migration Manager

```python
from src.data_processing.migration_utils import MigrationManager

manager = MigrationManager(
    client,
    source_directory="output/structured_insights",
    backup_directory="backups/migration"
)

# Discover files
files = manager.discover_json_files()

# Validate files
for file_path in files:
    is_valid, data, errors = manager.validate_json_file(file_path)
    if not is_valid:
        print(f"Invalid: {file_path} - {errors}")

# Run migration
state = manager.migrate_all_files()
summary = manager.get_migration_summary()
```

### Schema Validation

```python
from src.data_processing.schema import validate_structured_insight_json

data = {...}  # Your insight data
is_valid, errors = validate_structured_insight_json(data)

if not is_valid:
    print(f"Validation errors: {errors}")
```

## Error Handling and Monitoring

### Connection Management

```python
# Automatic retry with exponential backoff
@retry_on_failure(max_retries=3, delay=1.0, backoff=2.0)
def operation():
    return client.create_insight(insight)

# Health checks
client._health_check()  # Returns True/False

# Connection recovery
client._ensure_connection()  # Reconnects if needed
```

### Processing State Tracking

```python
from src.data_processing.supabase_insights_processor import ProcessingState

state = ProcessingState()
state.mark_processed("CNT-123", was_created=True)
state.mark_failed("CNT-456", "Validation error")

summary = state.get_summary()
# Returns: {'total_processed': 1, 'created': 1, 'failed': 1, ...}
```

### Comprehensive Statistics

```python
# Get processing statistics
stats = processor.get_processing_statistics()

# Get sync statistics  
sync_stats = sync_service.get_sync_statistics()

# Get database counts
total_insights = client.get_insights_count()
completed_insights = client.get_insights_count(
    processing_status=ProcessingStatus.COMPLETED
)
```

## Performance Optimization

### Batch Operations

- Use `batch_upsert_insights()` for multiple insights
- Configure appropriate batch sizes (default: 10)
- Enable memory cleanup between batches

### Connection Pooling

```python
client = SupabaseInsightsClient(
    enable_connection_pooling=True,
    max_retries=3,
    timeout=30
)
```

### Query Optimization

- Use indexes for common queries
- Filter by processing_status for active insights
- Use pagination for large result sets

```python
# Efficient pagination
insights = client.list_insights(
    limit=50,
    offset=100, 
    processing_status=ProcessingStatus.COMPLETED,
    order_by='updated_at'
)
```

## Docker Deployment

### Environment Configuration

```dockerfile
# Dockerfile
ENV SUPABASE_URL=https://your-project.supabase.co
ENV SUPABASE_SERVICE_ROLE_KEY=your-key
ENV ENABLE_SUPABASE_STORAGE=true
ENV ENABLE_MEMORY_OPTIMIZATION=true
```

### Memory Limits

```yaml
# docker-compose.yml
services:
  insights-processor:
    image: insights-processor
    environment:
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_SERVICE_ROLE_KEY=${SUPABASE_SERVICE_ROLE_KEY}
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G
```

### Health Checks

```yaml
# docker-compose.yml
healthcheck:
  test: ["CMD", "python", "-c", "from src.data_processing.supabase_client import SupabaseInsightsClient; SupabaseInsightsClient()._health_check()"]
  interval: 30s
  timeout: 10s
  retries: 3
```

## Troubleshooting

### Common Issues

1. **Connection Errors**: Check environment variables and network connectivity
2. **Table Not Found**: Run the SQL schema file
3. **Permission Errors**: Verify service role key has proper permissions
4. **Memory Issues**: Enable memory optimization and reduce batch sizes
5. **Migration Failures**: Validate JSON files first with dry-run

### Debug Mode

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Enable detailed logging
client = SupabaseInsightsClient()
client._health_check()  # Check logs for connection details
```

### Performance Monitoring

```python
# Monitor processing performance
stats = processor.get_processing_statistics()
print(f"Memory usage: {stats['memory_stats']}")
print(f"Database status: {stats['supabase_table_exists']}")

# Monitor sync performance  
sync_stats = sync_service.get_sync_statistics()
print(f"Success rate: {sync_stats['overall_summary']['success_rate']:.2%}")
```

## Next Steps

1. **Set up monitoring** for database performance and sync operations
2. **Configure automated backups** for the Supabase database
3. **Implement data retention policies** for old insights
4. **Set up alerting** for processing failures
5. **Consider read replicas** for high-volume read operations

## Support

For issues and questions:

- Check the setup script: `python scripts/setup_supabase.py --action check`
- Review logs in `logs/processing.log`
- Validate configuration with the setup tools
- Test connection and schema with provided utilities 

## Upsert Semantics (Updated)

- One consolidated record per contact using `eni_id = COMBINED-{contact_id}-ALL`.
- On each ENI group iteration we:
  - Append unique entries to `eni_source_types` and `eni_source_subtypes` arrays
  - Increment `total_eni_ids` by the number of ENIs in the current group
  - Increment `record_count` by the number of rows processed in the current group
  - Keep `generated_at` from the first creation; `updated_at` is managed by trigger
  - Increment `version` on every update
- We no longer update `eni_source_type` and `eni_source_subtype` single-value columns. They remain for legacy compatibility.

### Rationale

- Reduces duplicate rows per contact and ensures Airtable sees a single, consolidated insight.
- Preserves a full audit of which source types/subtypes contributed using arrays.

### Migration Notes

- Existing rows with only single-value columns can be backfilled into arrays with a simple SQL migration if desired.

```sql
-- Example (adjust to your needs):
update elvis__structured_insights
set eni_source_types = case
  when eni_source_types is null then array[eni_source_type]
  else eni_source_types || array[eni_source_type]
end,
    eni_source_subtypes = case
  when eni_source_subtypes is null then array[eni_source_subtype]
  else eni_source_subtypes || array[eni_source_subtype]
end
where eni_source_type is not null or eni_source_subtype is not null;
``` 