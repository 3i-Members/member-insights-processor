# Documentation

This directory contains comprehensive documentation for the Member Insights Processor.

## Documentation Structure

### Getting Started
- [Main README](../README.md) - Quick start guide and overview
- [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment guide for Google Cloud, Docker, and Kubernetes

### Technical Documentation
- [CLAUDE.md](CLAUDE.md) - Comprehensive guide for Claude Code instances working on this codebase
- [SUPABASE_INTEGRATION.md](SUPABASE_INTEGRATION.md) - Supabase integration details and schema

### Contributing
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Development guidelines and contribution process
- [CHANGELOG.md](../CHANGELOG.md) - Version history and changes

## Quick Links

- **Architecture Overview**: See [CLAUDE.md](CLAUDE.md#architecture-overview)
- **Environment Setup**: See [Main README](../README.md#setup)
- **API Configuration**: See [CLAUDE.md](CLAUDE.md#environment-variables)
- **Testing Guide**: See [CONTRIBUTING.md](../CONTRIBUTING.md#testing)
- **Deployment Steps**: See [DEPLOYMENT.md](DEPLOYMENT.md)

## Additional Resources

### Configuration
- `config/config.yaml` - Main configuration file
- `config/processing_filters.yaml` - Processing filter rules
- `config/system_prompts/` - LLM system prompts
- `.env.example` - Environment variable template

### Context Files
- `context/` - Data source context templates (see [context/README.md](../context/README.md))

### Tests
- `tests/` - Test suite (see [tests/README.md](../tests/README.md))
