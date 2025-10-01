"""Setup configuration for member-insights-processor."""

from setuptools import setup, find_packages
from pathlib import Path

# Read the contents of README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name="member-insights-processor",
    version="1.0.0",
    description="AI-powered member insights processor with BigQuery, Supabase, and multi-LLM support",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="3i Members",
    author_email="tech@3imembers.com",
    url="https://github.com/3i-Members/member-insights-processor",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.11",
    install_requires=[
        # Core Dependencies
        "pandas>=2.0.0",
        "numpy>=1.24.0",
        "python-dateutil>=2.8.2",
        # Google Cloud & BigQuery
        "google-cloud-bigquery>=3.10.0",
        "google-cloud-storage>=2.16.0",
        "google-auth>=2.17.0",
        "google-auth-oauthlib>=1.0.0",
        "google-auth-httplib2>=0.1.0",
        # AI Processing
        "google-generativeai>=0.3.0",
        "openai>=1.0.0",
        "anthropic>=0.18.0",
        # Database Integration
        "supabase>=2.0.0",
        "postgrest>=0.10.6",
        "websockets>=13.0",
        # Airtable Integration
        "pyairtable>=2.1.0",
        # Configuration & Data Formats
        "PyYAML>=6.0",
        "python-dotenv>=1.0.0",
        # File Processing & I/O
        "pathlib2>=2.3.7",
        "chardet>=5.1.0",
        # Logging & Monitoring
        "colorlog>=6.7.0",
        # Performance
        "psutil>=5.9.0",
        "tqdm>=4.65.0",
        # Data Validation
        "pydantic>=2.0.0",
        "jsonschema>=4.17.0",
        # Security
        "cryptography>=41.0.0",
        "requests>=2.31.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.5.0",
        ],
        "docs": [
            "sphinx>=7.1.0",
            "sphinx-rtd-theme>=1.3.0",
        ],
        "jupyter": [
            "jupyter>=1.0.0",
            "ipykernel>=6.25.0",
            "matplotlib>=3.7.0",
            "seaborn>=0.12.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "member-insights=src.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
    keywords="ai llm bigquery supabase insights processing",
    project_urls={
        "Bug Reports": "https://github.com/3i-Members/member-insights-processor/issues",
        "Source": "https://github.com/3i-Members/member-insights-processor",
    },
)
