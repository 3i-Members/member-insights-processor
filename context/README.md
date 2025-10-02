# Context Files

This directory contains context templates that provide domain-specific guidance to the LLM for processing different data sources.

## Structure

Context files are organized by data source type and subtype:

```
context/
├── README.md (this file)
├── Member Insights Summary.md       # General member insights guidance
├── airtable_affiliations/
│   └── default.md                   # Affiliations context
├── airtable_deals_sourced/
│   └── default.md                   # Deals sourced context
├── airtable_notes/
│   ├── default.md                   # General notes context
│   ├── intro_preferences.md         # Intro preferences context
│   └── investing_preferences.md     # Investing preferences context
├── member_requests/
│   ├── requested.md                 # Member requests context
│   ├── responded.md                 # Responded requests context
│   └── suggested.md                 # Suggested requests context
├── pipedrive_notes/
│   └── default.md                   # Pipedrive notes context
├── recurroo/
│   ├── asset_class.md              # Asset class preferences
│   ├── biography.md                # Member biography
│   ├── sector.md                   # Sector preferences
│   └── social.md                   # Social media links
└── whatsapp_messages/
    ├── _chat.md                    # General chat context
    ├── ai_ml.md                    # AI/ML interest group
    ├── real_estate.md              # Real estate group
    └── ... (50+ topic-specific contexts)
```

## How Context Files Work

### 1. Context Loading
The `ContextManager` loads context files based on the ENI (Entity Interaction) source type and subtype:

```python
# Example: Loading context for airtable_notes with investing_preferences subtype
context = context_manager.get_context(
    eni_source_type="airtable_notes",
    eni_source_subtype="investing_preferences"
)
```

### 2. Fallback Logic
If a specific subtype context doesn't exist, the system falls back to `default.md`:

```
airtable_notes/investing_preferences.md → airtable_notes/default.md → General guidance
```

### 3. Token Budgeting
Context files are subject to token limits defined in `config/config.yaml`:

- `reserve_output_tokens`: Reserved for LLM output
- `max_new_data_tokens_per_group`: Maximum tokens for new data
- Remaining tokens allocated to context files

### 4. Template Variables
Context files can use template variables that are replaced at runtime:

- `{{current_structured_insight}}` - Previous insights for this contact
- `{{eni_source_type_context}}` - Source type context
- `{{eni_source_subtype_context}}` - Source subtype context
- `{{new_data_to_process}}` - New data records to analyze

## Writing Context Files

### Best Practices

1. **Be Specific**: Provide clear guidance on what to extract from each data source
2. **Use Examples**: Include example outputs when possible
3. **Focus on Value**: Guide the LLM to extract actionable insights, not just summarize
4. **Keep It Concise**: Context files consume tokens; be efficient
5. **Domain Knowledge**: Include industry-specific terminology and context

### Template Structure

```markdown
# [Source Type] - [Subtype] Context

## Purpose
Brief description of what this data source contains and why it's valuable.

## Key Information to Extract
- Point 1: What to look for
- Point 2: What to extract
- Point 3: How to interpret

## Analysis Guidelines
- How to analyze this type of data
- What patterns to look for
- What insights are valuable

## Output Format
- How to structure the insights
- What fields to populate
- Examples if helpful

## Special Considerations
- Edge cases
- Data quality issues
- Important nuances
```

### Example: WhatsApp Group Context

```markdown
# WhatsApp Messages - Real Estate Group

## Purpose
Messages from the 3i Members Real Estate WhatsApp group indicate interest in real estate investing, development, and discussion.

## Key Information to Extract
- Types of real estate interests (residential, commercial, industrial)
- Geographic focus areas
- Investment vs. development vs. passive interest
- Specific questions or needs expressed

## Analysis Guidelines
- Active participants show stronger interest than occasional posters
- Questions indicate specific needs or knowledge gaps
- Responses to others' posts can reveal expertise level

## Output Format
Add insights to the `interests` and `expertise` fields:
- interests: ["real_estate_investing", "commercial_real_estate"]
- expertise: "Real estate investor with focus on commercial properties"
```

## WhatsApp Message Contexts

The `whatsapp_messages/` directory contains 50+ context files for different interest-based groups:

### Categories

**Geographic**: bay_area, boston, canada, chicago, dc_dmv, europe, florida, hamptons, israel_regional, los_angeles, nyc, puerto_rico, texas

**Interests**: ai_ml, art_art_investing, blockchain, estate_tax_planning, golf, health_hackers, philanthropy, real_estate, venture, wine, watches

**Lifestyle**: bikes_boats_planes_cars, gadgets_devices_gizmos, parenting, skiing_snowboarding, travel, home_vacation_swap

**Professional**: job_board, market_reactions, needs_leads, recommended_reading

**Special**: women_3i, israel_support

Each file provides specific guidance on interpreting participation in that group.

## Configuration

Context file locations are configured in `config/config.yaml`:

```yaml
context_paths:
  base_path: "context"
  member_insights_summary: "Member Insights Summary.md"
  eni_source_type_contexts:
    airtable_notes: "airtable_notes"
    whatsapp_messages: "whatsapp_messages"
    # ... etc
```

## Adding New Context Files

1. **Determine the structure**: Is it a new source type or subtype?
2. **Create the directory** (if new source type):
   ```bash
   mkdir -p context/new_source_type
   ```
3. **Create the context file**:
   ```bash
   touch context/new_source_type/default.md
   # or for subtype
   touch context/new_source_type/specific_subtype.md
   ```
4. **Update configuration** in `config/config.yaml`:
   ```yaml
   eni_source_type_contexts:
     new_source_type: "new_source_type"
   ```
5. **Test the context**:
   ```bash
   python tests/unit/test_context_preview.py
   ```

## Debugging Context Loading

Use the context preview test to see how contexts are assembled:

```bash
pytest tests/unit/test_context_preview.py -v
```

This generates a markdown file in `logs/` showing:
- Which context files were loaded
- Token counts for each component
- Final rendered prompt with all variables replaced

## Related Documentation

- [CLAUDE.md](../docs/CLAUDE.md) - Architecture and implementation details
- [config/config.yaml](../config/config.yaml) - Configuration settings
- [config/processing_filters.yaml](../config/processing_filters.yaml) - Processing rules
