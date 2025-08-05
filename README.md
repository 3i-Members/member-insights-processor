# Member Insights Processor

An AI-powered system that processes member data from BigQuery, generates insights using Google's Gemini Pro, and syncs results to Airtable. The system intelligently processes member data based on ENI types, applies contextual understanding from markdown files, and maintains processing logs for efficiency.

## Features

- 🔍 **Intelligent Data Processing**: Loads member data from BigQuery with smart filtering to avoid reprocessing
- 🤖 **AI-Powered Insights**: Uses Google Gemini Pro to generate comprehensive member summaries and insights
- 📁 **Contextual Analysis**: Applies domain-specific context based on ENI types and subtypes
- 📝 **Markdown Output**: Saves AI-generated insights as structured markdown files with metadata
- 🔄 **Airtable Integration**: Automatically syncs results to Airtable for easy access and management
- 📊 **Processing Logs**: Maintains detailed logs to prevent duplicate processing and track progress
- ⚙️ **Configurable Pipeline**: Flexible configuration system for different ENI mappings and prompts

## Architecture

```
member-insights-processor/
├── src/
│   ├── data_processing/          # BigQuery integration and log management
│   ├── context_management/       # Configuration and markdown reading
│   ├── ai_processing/           # Gemini Pro integration
│   ├── output_management/       # Markdown and Airtable writing
│   └── main.py                  # Main processing pipeline
├── config/                      # Configuration files
├── context/                     # ENI-specific context files
├── output/                      # Generated markdown summaries
├── logs/                        # Processing logs
└── tests/                       # Unit tests
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
   
   # Gemini API key
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

### 3. Gemini Processor
- Integrates with Google Gemini Pro API
- Processes member data with AI insights
- Supports custom system prompts and context

### 4. Markdown Writer
- Creates structured markdown files
- Includes YAML front matter metadata
- Organizes output by contact and ENI ID

### 5. Airtable Writer
- Syncs data to Airtable automatically
- Handles create/update logic
- Supports custom field mappings

### 6. Log Manager
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