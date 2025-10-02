# Contributing to Member Insights Processor

Thank you for your interest in contributing! This guide will help you get started.

## Table of Contents

- [Development Setup](#development-setup)
- [Code Standards](#code-standards)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Project Structure](#project-structure)

## Development Setup

### Prerequisites

- Python 3.11 or higher
- Git
- Access to required services (BigQuery, Supabase, Airtable)

### Local Environment Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/3i-Members/member-insights-processor.git
   cd member-insights-processor
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   # Production dependencies
   pip install -r requirements.txt

   # Development dependencies
   pip install -e ".[dev]"
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

5. **Install pre-commit hooks**
   ```bash
   pre-commit install
   ```

6. **Validate setup**
   ```bash
   python src/main.py --validate
   ```

## Code Standards

### Style Guidelines

We follow Python best practices and use automated tools to maintain code quality:

- **Code Formatting**: [Black](https://black.readthedocs.io/) (line length: 100)
- **Linting**: [Flake8](https://flake8.pycqa.org/)
- **Type Checking**: [MyPy](https://mypy.readthedocs.io/)
- **Import Sorting**: [isort](https://pycqa.github.io/isort/)

### Running Code Quality Tools

```bash
# Format code
black src/ tests/

# Check linting
flake8 src/ tests/

# Type checking
mypy src/

# Run all checks (via pre-commit)
pre-commit run --all-files
```

### Code Style Conventions

1. **Naming Conventions**
   - Classes: `PascalCase` (e.g., `MemberInsightsProcessor`)
   - Functions/Methods: `snake_case` (e.g., `process_member_data`)
   - Constants: `UPPER_SNAKE_CASE` (e.g., `MAX_TOKENS`)
   - Private methods: `_leading_underscore` (e.g., `_validate_config`)

2. **Docstrings**
   - Use Google-style docstrings for all public functions and classes
   - Example:
     ```python
     def process_contact(contact_id: str, limit: int = 100) -> Dict[str, Any]:
         """Process a single contact and generate insights.

         Args:
             contact_id: The contact identifier
             limit: Maximum number of records to process

         Returns:
             Dictionary containing processing results and metadata

         Raises:
             ValueError: If contact_id is invalid
         """
     ```

3. **Type Hints**
   - Use type hints for all function parameters and return values
   - Import types from `typing` module when needed

4. **Logging**
   - Use the project's enhanced logger
   - Log levels: DEBUG for detailed flow, INFO for key operations, WARNING for issues, ERROR for failures
   - Example:
     ```python
     from src.utils.enhanced_logger import get_logger
     logger = get_logger(__name__)

     logger.info(f"Processing contact {contact_id}")
     logger.error(f"Failed to connect to BigQuery: {error}")
     ```

## Testing

### Test Structure

Tests are organized by type:
- `tests/unit/` - Unit tests for individual functions/classes
- `tests/integration/` - Integration tests for component interactions
- `tests/e2e/` - End-to-end tests for full pipeline

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_context_manager.py

# Run with coverage
pytest --cov=src --cov-report=html

# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Skip slow tests
pytest -m "not slow"
```

### Writing Tests

1. **Test File Naming**: `test_<module_name>.py`
2. **Test Function Naming**: `test_<function_being_tested>_<scenario>()`
3. **Use Markers**: Mark tests appropriately
   ```python
   import pytest

   @pytest.mark.unit
   def test_token_estimation_valid_input():
       """Test token estimation with valid input."""
       pass

   @pytest.mark.integration
   def test_bigquery_connection():
       """Test BigQuery connection with real credentials."""
       pass
   ```

4. **Fixtures**: Use fixtures for common setup
   ```python
   @pytest.fixture
   def sample_config():
       """Provide sample configuration for tests."""
       return {"max_tokens": 1000, "model": "gpt-4"}
   ```

### Test Coverage

- Aim for >80% code coverage
- All new features must include tests
- Bug fixes should include regression tests

## Submitting Changes

### Branch Naming

Use descriptive branch names:
- `feature/add-new-llm-provider` - New features
- `fix/bigquery-connection-error` - Bug fixes
- `docs/update-deployment-guide` - Documentation
- `refactor/simplify-context-manager` - Code refactoring

### Commit Messages

Follow conventional commits format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `refactor`: Code refactoring
- `test`: Adding/updating tests
- `chore`: Maintenance tasks
- `perf`: Performance improvements

**Examples:**
```
feat(ai): add support for Claude 3.5 Sonnet

- Implement Anthropic API integration
- Add token counting for Claude models
- Update configuration schema

Closes #123
```

```
fix(bigquery): resolve connection timeout issue

The BigQuery connector was timing out on large queries.
Increased timeout from 30s to 120s and added retry logic.

Fixes #456
```

### Pull Request Process

1. **Before submitting:**
   - Run all tests: `pytest`
   - Run code quality checks: `pre-commit run --all-files`
   - Update documentation if needed
   - Add entry to `CHANGELOG.md`

2. **PR Description:**
   - Clearly describe the changes and motivation
   - Reference related issues
   - Include screenshots for UI changes
   - List any breaking changes

3. **Review Process:**
   - Address reviewer feedback
   - Keep commits clean and logical
   - Squash minor fix commits before merging

4. **Merging:**
   - PRs require at least one approval
   - All CI checks must pass
   - Merge using "Squash and merge" for feature branches

## Project Structure

```
member-insights-processor/
├── src/                          # Source code
│   ├── ai_processing/           # LLM integrations
│   ├── context_management/      # Context and configuration
│   ├── data_processing/         # Data connectors and schemas
│   ├── output_management/       # Output writers
│   └── utils/                   # Utility functions
├── tests/                       # Test suite
│   ├── unit/                    # Unit tests
│   ├── integration/             # Integration tests
│   └── e2e/                     # End-to-end tests
├── config/                      # Configuration files
├── context/                     # Context templates
├── docs/                        # Documentation
├── scripts/                     # Utility scripts
└── .github/workflows/           # CI/CD workflows
```

### Key Files

- `src/main.py` - Main entry point
- `src/context_management/context_manager.py` - Context assembly logic
- `src/ai_processing/` - LLM provider implementations
- `config/config.yaml` - Main configuration
- `pyproject.toml` - Project metadata and tool configuration

## Getting Help

- **Documentation**: Check [docs/](docs/) directory
- **Issues**: Search [existing issues](https://github.com/3i-Members/member-insights-processor/issues)
- **Questions**: Open a new issue with the "question" label

## Code of Conduct

This project follows a code of conduct. By participating, you agree to:
- Be respectful and inclusive
- Accept constructive criticism
- Focus on what's best for the project
- Show empathy towards other contributors

Thank you for contributing! 🎉
