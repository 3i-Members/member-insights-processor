# Member Insights Processor

An AI-powered system that processes member data from BigQuery, generates insights using Claude/Gemini/OpenAI, and stores structured insights in Supabase for scalable, memory-efficient processing. The system features intelligent upsert logic, decoupled Airtable syncing, and Docker-optimized performance.

## Features

- 🔍 **Intelligent Data Processing**: Loads member data from BigQuery with smart filtering to avoid reprocessing
- 🤖 **Multi-AI Support**: Uses Claude, Gemini Pro, or OpenAI to generate comprehensive member insights
- 📁 **Contextual Analysis**: Applies domain-specific context based on ENI types and subtypes
- 💾 **Supabase Storage**: Scalable PostgreSQL JSONB storage for structured insights with intelligent upsert logic
- 🔄 **Decoupled Airtable Sync**: Independent Airtable syncing that pulls from Supabase on-demand
- 📊 **Memory Optimization**: Docker-optimized with efficient memory management for large datasets
- 🔀 **Smart Merging**: Automatically merges new data with existing insights using advanced processing logic
- ⚙️ **Configurable Pipeline**: Flexible configuration system for different ENI mappings and prompts

## Architecture

```
member-insights-processor/
├── src/
│   ├── data_processing/          # BigQuery, Supabase integration and log management
│   │   ├── supabase_client.py    # Supabase database operations
│   │   ├── supabase_insights_processor.py  # Core Supabase processing logic
│   │   └── schema.py             # Pydantic data models and validation
│   ├── context_management/       # Configuration and markdown reading
│   ├── ai_processing/           # Claude, Gemini Pro, OpenAI integration
│   ├── output_management/       # Markdown, JSON, and Airtable writing
│   │   └── supabase_airtable_writer.py  # Decoupled Airtable sync from Supabase
│   └── main.py                  # Main processing pipeline
├── config/                      # Configuration files
│   └── supabase_schema.sql      # Database schema for Supabase
├── context/                     # ENI-specific context files
├── output/                      # Generated summaries and insights
├── logs/                        # Processing logs
├── scripts/                     # Setup and migration utilities
├── tests/                       # Comprehensive test suite
├── SUPABASE_INTEGRATION.md      # Detailed Supabase setup guide
└── README.md                    # This file
```

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd member-insights-processor
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   # Google Cloud credentials for BigQuery
   export GOOGLE_APPLICATION_CREDENTIALS="path/to/your/bigquery-credentials.json"
   
   # AI API keys (choose your preferred provider)
   export ANTHROPIC_API_KEY="your-anthropic-api-key"    # For Claude
   export GOOGLE_API_KEY="your-google-api-key"          # For Gemini
   export OPENAI_API_KEY="your-openai-api-key"          # For OpenAI
   
   # Supabase configuration
   export SUPABASE_URL="your-supabase-project-url"
   export SUPABASE_SERVICE_ROLE_KEY="your-service-role-key"
   
   # Airtable configuration (optional)
   export AIRTABLE_API_KEY="your-airtable-api-key"
   export AIRTABLE_BASE_ID="your-base-id"
   
   # Legacy Gemini setup
   export GEMINI_API_KEY="your-gemini-api-key"
   
   # Airtable credentials (optional)
   export AIRTABLE_API_KEY="your-airtable-api-key"
   export AIRTABLE_BASE_ID="your-base-id"
   export AIRTABLE_TABLE_NAME="your-table-name"
   ```

4. **Configure the system**
   ```bash
   # Edit the configuration file
   cp config/config.yaml.example config/config.yaml
   # Update with your specific settings
   ```

## Quick Start

### 1. Validate Setup
```bash
python src/main.py --validate
```

### 2. Process a Single Contact
```bash
python src/main.py --contact-id "CONTACT_123"
```

### 3. Process Multiple Contacts
```bash
# Process first 10 contacts
python src/main.py --limit 10

# Dry run (don't save results)
python src/main.py --limit 5 --dry-run
```

### 4. Check Processing Statistics
```bash
python src/main.py --stats
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
4. **Sync to Airtable** independently using decoupled service

### 🎯 **Decoupled Airtable Sync**

Test the new Airtable sync that pulls from Supabase:

```bash
# Test Supabase-powered Airtable sync for specific contact
python test_airtable_sync.py

# This will:
# 1. Pull structured insight from Supabase
# 2. Sync to Airtable on-demand
# 3. Only process specified contact IDs (no database flooding)
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
  table_name: "eni__vectorizer_all"

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
# Basic processing
python src/main.py

# Process specific contact with custom prompt
python src/main.py --contact-id "CONTACT_123" --system-prompt "insight_generation"

# Batch processing with limit
python src/main.py --limit 50

# Dry run for testing
python src/main.py --contact-id "CONTACT_123" --dry-run

# Clear processing logs
python src/main.py --clear-logs
```

### Programmatic Usage

```python
from src.main import MemberInsightsProcessor

# Initialize processor
processor = MemberInsightsProcessor("config/config.yaml")

# Validate setup
validation = processor.validate_setup()
if validation['valid']:
    print("System ready!")

# Process a single contact
result = processor.process_contact("CONTACT_123")
print(f"Success: {result['success']}")
print(f"Files created: {result['files_created']}")

# Get statistics
stats = processor.get_processing_statistics()
print(f"Total processed contacts: {stats['log_statistics']['total_contacts']}")
```

## Components

### 1. BigQuery Connector
- Connects to Google BigQuery
- Loads contact data with filtering
- Prevents reprocessing of already handled records

### 2. Configuration Loader
- Manages YAML configuration files
- Maps ENI types to context files
- Handles system prompt configurations

### 3. Multi-AI Processor
- Supports Claude (Anthropic), Gemini Pro, and OpenAI
- Processes member data with AI insights
- Configurable AI provider selection

### 4. Supabase Client
- **NEW**: PostgreSQL JSONB storage for structured insights
- Intelligent upsert logic with automatic merging
- Comprehensive CRUD operations with retry logic

### 5. Supabase Insights Processor
- **NEW**: Memory-efficient processing pipeline
- Loads existing insights before processing new data
- Batch processing with configurable memory management

### 6. Decoupled Airtable Writer
- **UPDATED**: Pulls data from Supabase independently
- Contact-specific syncing (no database flooding)
- Supports both legacy and Supabase-powered workflows

### 7. Schema & Validation
- **NEW**: Pydantic v2 data models with comprehensive validation
- Type-safe insight processing with automatic serialization
- Migration utilities for existing data

### 8. Log Manager
- Tracks processed ENI IDs
- Prevents duplicate processing
- Thread-safe file operations

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

## Testing

```bash
# Run unit tests
pytest tests/

# Run with coverage
pytest tests/ --cov=src/

# Run specific test module
pytest tests/test_bigquery_connector.py
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue in the repository
- Check the documentation in the `docs/` directory
- Review the example configurations and context files

## Changelog

### v1.0.0
- Initial release with complete pipeline
- BigQuery integration
- Gemini Pro AI processing
- Airtable sync functionality
- Comprehensive logging and monitoring 