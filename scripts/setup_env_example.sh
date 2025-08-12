#!/bin/bash
# Example script to set up environment variables for Member Insights Processor
# Copy this file to setup_env.sh and customize with your actual values

echo "🔧 Setting up Member Insights Processor environment variables..."

# Google Cloud / BigQuery Configuration
export PROJECT_ID="i-sales-analytics"                    # Your Google Cloud Project ID
export BQ_DATASET="3i_analytics"                         # Your BigQuery dataset
export GOOGLE_CLOUD_PROJECT_ID="i-sales-analytics"       # Alternative project ID variable

# Google Credentials
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service-account-key.json"
# OR
export GOOGLE_CREDENTIALS_PATH="/path/to/your/service-account-key.json"

# AI API Keys
export GEMINI_API_KEY="your-gemini-api-key-here"         # Get from https://aistudio.google.com/app/apikey

# Optional: Airtable Integration
export AIRTABLE_API_KEY="your-airtable-api-key"
export AIRTABLE_BASE_ID="your-airtable-base-id" 
export AIRTABLE_TABLE_NAME="Member Insights"

echo "✅ Environment variables set!"
echo "📋 Current values:"
echo "   PROJECT_ID: ${PROJECT_ID}"
echo "   BQ_DATASET: ${BQ_DATASET}" 
echo "   GOOGLE_CREDENTIALS: ${GOOGLE_APPLICATION_CREDENTIALS:-${GOOGLE_CREDENTIALS_PATH}}"
echo "   GEMINI_API_KEY: ${GEMINI_API_KEY:0:10}..." # Show only first 10 chars

echo ""
echo "💡 To use this script:"
echo "   1. Copy to setup_env.sh: cp setup_env_example.sh setup_env.sh"
echo "   2. Edit setup_env.sh with your actual values"
echo "   3. Run: source setup_env.sh"
echo "   4. Test: python test_with_env.py" 