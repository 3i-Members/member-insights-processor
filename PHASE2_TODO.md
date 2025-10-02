# Phase 2 - Remaining Work

**Status:** Structure created, imports need updating
**Date:** 2024-10-01

## ✅ Completed

1. Created new package structure:
   ```
   src/member_insights_processor/
   ├── core/llm/          (openai.py, anthropic.py, gemini.py)
   ├── core/utils/        (logging.py, tokens.py)
   ├── pipeline/          (context.py, filters.py, config.py, runner.py)
   └── io/
       ├── readers/       (bigquery.py, supabase.py, markdown.py)
       ├── writers/       (airtable.py, json.py, markdown.py, supabase.py, supabase_sync.py)
       ├── schema.py
       └── log_manager.py
   ```

2. Created all `__init__.py` files
3. Copied all files to new locations (originals still in old location)
4. Created MIGRATION_GUIDE.md with complete mapping

## ⏳ Remaining Work

### 1. Update Internal Imports

Need to update imports in all files under `src/member_insights_processor/`:

**Pattern to replace:**
```python
# OLD
from ai_processing.xxx import yyy
from context_management.xxx import yyy
from data_processing.xxx import yyy
from output_management.xxx import yyy
from utils.xxx import yyy

# NEW
from member_insights_processor.core.llm.xxx import yyy
from member_insights_processor.pipeline.xxx import yyy
from member_insights_processor.io.readers.xxx import yyy
from member_insights_processor.io.writers.xxx import yyy
from member_insights_processor.core.utils.xxx import yyy
```

**Files to update** (in order of dependencies):

1. **core/utils/** (no dependencies)
   - `logging.py` - No changes needed
   - `tokens.py` - No changes needed

2. **io/schema.py** (depends on utils)
   - Update: `from utils.xxx` → `from member_insights_processor.core.utils.xxx`

3. **io/readers/** (depend on schema, utils)
   - `bigquery.py` - Update imports
   - `supabase.py` - Update imports
   - `markdown.py` - Update imports

4. **io/writers/** (depend on readers, schema)
   - `airtable.py` - Update imports
   - `json.py` - Update imports
   - `markdown.py` - Update imports
   - `supabase.py` - Update imports
   - `supabase_sync.py` - Update imports

5. **core/llm/** (depend on utils)
   - `openai.py` - Update imports
   - `anthropic.py` - Update imports
   - `gemini.py` - Update imports

6. **pipeline/** (depend on everything)
   - `config.py` - Update imports
   - `context.py` - Update imports (COMPLEX - uses many modules)
   - `filters.py` - Update imports
   - `runner.py` - Update imports (MOST COMPLEX - main file)

### 2. Update pyproject.toml

```toml
[tool.setuptools.packages.find]
where = ["src"]
include = ["member_insights_processor*"]

[project.scripts]
mip = "member_insights_processor.pipeline.runner:main"
```

### 3. Remove Old Structure

After imports updated and tested:
```bash
rm -rf src/ai_processing/
rm -rf src/context_management/
rm -rf src/data_processing/
rm -rf src/output_management/
rm -rf src/utils/
rm src/main.py
rm src/__init__.py
```

### 4. Test Everything

```bash
# Test imports
PYTHONPATH=src python -c "from member_insights_processor.core.llm.openai import OpenAIClient"

# Test pipeline
PYTHONPATH=src python -m member_insights_processor.pipeline.runner --validate

# Test end-to-end
PYTHONPATH=src python -m member_insights_processor.pipeline.runner --limit 1
```

## Import Update Script Template

```bash
# For each file in src/member_insights_processor/
sed -i '' 's/from ai_processing\./from member_insights_processor.core.llm./g' FILE
sed -i '' 's/from context_management\./from member_insights_processor.pipeline./g' FILE
sed -i '' 's/from data_processing\.bigquery/from member_insights_processor.io.readers.bigquery/g' FILE
sed -i '' 's/from data_processing\.supabase/from member_insights_processor.io.readers.supabase/g' FILE
sed -i '' 's/from data_processing\.schema/from member_insights_processor.io.schema/g' FILE
sed -i '' 's/from data_processing\.log_manager/from member_insights_processor.io.log_manager/g' FILE
sed -i '' 's/from output_management\./from member_insights_processor.io.writers./g' FILE
sed -i '' 's/from utils\./from member_insights_processor.core.utils./g' FILE
```

## Manual Review Needed

1. **runner.py** (old main.py) - Complex imports, needs careful review
2. **context.py** (old context_manager.py) - Uses many modules
3. **Circular imports** - Check for any circular dependencies

## Next Session

1. Run systematic import updates
2. Test each module layer independently
3. Update pyproject.toml
4. Test full pipeline with `--limit 1`
5. Remove old structure
6. Commit Phase 2 completion
