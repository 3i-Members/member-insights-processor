#!/usr/bin/env python3
"""
Test script to upload a structured insight to Supabase and verify it works.
"""

import os
import sys
import json
import logging
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from data_processing.supabase_client import SupabaseInsightsClient
from data_processing.schema import (
    StructuredInsight,
    normalize_insight_data,
    validate_structured_insight_json,
)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def load_json_file(file_path: str) -> dict:
    """Load and parse the JSON file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"Successfully loaded JSON file: {file_path}")
        return data
    except Exception as e:
        logger.error(f"Failed to load JSON file {file_path}: {e}")
        raise


def test_supabase_upload():
    """Test uploading the JSON file to Supabase."""

    # Check environment variables
    required_vars = ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"]
    missing_vars = []

    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        logger.error(f"Missing environment variables: {missing_vars}")
        logger.info("Please set the following environment variables:")
        for var in missing_vars:
            logger.info(f"export {var}=your_{var.lower()}")
        return False

    try:
        # Initialize Supabase client
        logger.info("Initializing Supabase client...")
        client = SupabaseInsightsClient()

        # Test connection
        logger.info("Testing Supabase connection...")
        if not client.health_check():
            logger.error("Supabase health check failed")
            return False
        logger.info("✓ Supabase connection successful")

        # Load the JSON file
        json_file_path = "output/structured_insights/CNT-c9M007641_COMBINED-CNT-c9M007641-9ENI.json"
        logger.info(f"Loading JSON file: {json_file_path}")

        if not os.path.exists(json_file_path):
            logger.error(f"JSON file not found: {json_file_path}")
            return False

        raw_data = load_json_file(json_file_path)

        # Validate and normalize the data
        logger.info("Validating and normalizing data...")
        if not validate_structured_insight_json(raw_data):
            logger.error("JSON validation failed")
            return False

        # Convert to StructuredInsight object
        insight = normalize_insight_data(raw_data)
        logger.info(f"✓ Data normalized successfully")
        logger.info(f"Contact ID: {insight.metadata.contact_id}")
        logger.info(f"ENI ID: {insight.metadata.eni_id}")
        logger.info(f"Member Name: {insight.metadata.member_name}")

        # Check if record already exists
        logger.info("Checking if record already exists...")
        existing = client.get_insight_by_contact_and_eni(
            insight.metadata.contact_id, insight.metadata.eni_id or "UNKNOWN"
        )

        if existing:
            logger.info(f"Record already exists with ID: {existing.id}")
            logger.info("Updating existing record...")
            updated_insight = client.update_insight(insight)
            logger.info(f"✓ Record updated successfully with ID: {updated_insight.id}")
            result_insight = updated_insight
            action = "updated"
        else:
            logger.info("Creating new record...")
            created_insight = client.create_insight(insight)
            logger.info(f"✓ Record created successfully with ID: {created_insight.id}")
            result_insight = created_insight
            action = "created"

        # Verify the upload by querying it back
        logger.info("Verifying upload by querying the record...")
        queried_insight = client.get_insight(result_insight.id)

        if queried_insight:
            logger.info(f"✓ Record verification successful")
            logger.info(f"Queried Contact ID: {queried_insight.metadata.contact_id}")
            logger.info(f"Queried ENI ID: {queried_insight.metadata.eni_id}")
            logger.info(f"Queried Generated At: {queried_insight.metadata.generated_at}")

            # Check specific insight sections
            if queried_insight.personal:
                logger.info(f"Personal section length: {len(queried_insight.personal)} characters")
            if queried_insight.business:
                logger.info(f"Business section length: {len(queried_insight.business)} characters")
            if queried_insight.investing:
                logger.info(
                    f"Investing section length: {len(queried_insight.investing)} characters"
                )

            logger.info(f"🎉 Upload and verification completed! Record {action} successfully.")
            return True
        else:
            logger.error("Failed to query back the uploaded record")
            return False

    except Exception as e:
        logger.error(f"Upload test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_table_structure():
    """Test that the table structure matches our expectations."""
    try:
        logger.info("Testing table structure...")
        client = SupabaseInsightsClient()

        # Use the client's built-in health check and test a simple query
        if not client.health_check():
            logger.error("❌ Supabase health check failed")
            return False

        # Try to get table info (this will help us see if the table exists)
        client_conn = client._ensure_connection()
        result = client_conn.table("elvis__structured_insights").select("id").limit(1).execute()
        logger.info("✓ Table 'elvis__structured_insights' exists and is accessible")

        if result.data:
            logger.info(f"Table contains {len(result.data)} sample record(s)")
        else:
            logger.info("Table is empty (ready for new records)")

        return True

    except Exception as e:
        logger.error(f"Table structure test failed: {e}")
        if 'relation "elvis__structured_insights" does not exist' in str(e):
            logger.error(
                "❌ The table 'elvis__structured_insights' does not exist in your Supabase database"
            )
            logger.info("You need to run the SQL schema first:")
            logger.info("1. Go to your Supabase dashboard")
            logger.info("2. Navigate to SQL Editor")
            logger.info("3. Run the contents of config/supabase_schema.sql")
        return False


if __name__ == "__main__":
    print("🚀 Supabase Upload Test")
    print("=" * 50)

    # Test table structure first
    if not test_table_structure():
        print("\n❌ Table structure test failed. Please set up the database schema first.")
        sys.exit(1)

    # Test upload
    if test_supabase_upload():
        print("\n✅ All tests passed! Supabase integration is working correctly.")
    else:
        print("\n❌ Upload test failed. Please check the logs above.")
        sys.exit(1)
