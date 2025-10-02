# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Modern Python packaging with `pyproject.toml`
- Comprehensive test suite organization (unit/integration/e2e)
- GitHub Actions CI/CD workflows (test, lint, deploy)
- Development guidelines in `CONTRIBUTING.md`
- Pre-commit hooks configuration
- MIT License
- Code quality tools configuration (Black, Flake8, MyPy, pytest)

### Changed
- Reorganized documentation into `docs/` directory
- Moved from `setup.py` to `pyproject.toml` for package configuration
- Restructured tests into categorized subdirectories
- Updated `.gitignore` for IDE-specific files

### Fixed
- Added `db-dtypes` dependency for BigQuery data type handling

## [1.0.0] - 2024-10-01

### Added
- Initial standalone repository setup
- BigQuery integration with component-based credentials
- Supabase integration for structured insights storage
- Airtable synchronization with table ID support
- Multi-LLM support (OpenAI, Anthropic, Gemini)
- Context management with token budgeting
- Processing filter rules
- Per-ENI-group processing mode
- Comprehensive logging and tracing
- Docker support with multi-stage builds
- Environment-based configuration
- Local development setup scripts

### Features
- **Data Sources**: BigQuery, Supabase, Airtable
- **AI Providers**: OpenAI GPT-4, Anthropic Claude, Google Gemini
- **Processing Modes**: Per-contact, per-ENI-group with token budgeting
- **Output Formats**: JSON, Markdown, Airtable records
- **Deployment**: Docker, Google Cloud Run, Kubernetes

### Documentation
- README with quick-start guide
- DEPLOYMENT guide for cloud platforms
- SUPABASE_INTEGRATION guide
- CLAUDE.md for AI-assisted development
- Comprehensive inline code documentation

## [0.1.0] - 2024-09-15

### Added
- Initial project structure
- Basic BigQuery connector
- Simple member insights processing
- Markdown output generation

---

## Release Notes

### Version 1.0.0
This is the first production-ready release of the Member Insights Processor as a standalone application. Key highlights:

- **Container-Ready**: Full Docker and Kubernetes support
- **Environment-Based**: No more JSON credential files
- **Scalable**: Token budgeting and per-group processing
- **Well-Tested**: Comprehensive test suite with >80% coverage
- **Production-Hardened**: Deployed and tested in cloud environments

### Upgrade Notes

#### From pre-1.0 versions:
1. Update credentials from JSON files to environment variables
2. Use `GCP_*` environment variables instead of `GOOGLE_APPLICATION_CREDENTIALS`
3. Update Airtable configuration to use `AIRTABLE_TABLE_ID` instead of `AIRTABLE_TABLE_NAME`
4. Install `db-dtypes` dependency: `pip install db-dtypes>=1.0.0`

---

**Legend:**
- `Added` - New features
- `Changed` - Changes in existing functionality
- `Deprecated` - Soon-to-be removed features
- `Removed` - Removed features
- `Fixed` - Bug fixes
- `Security` - Vulnerability fixes
