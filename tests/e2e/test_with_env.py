#!/usr/bin/env python3
"""
Test script to validate the Member Insights Processor with real environment variables
"""

import sys
import os
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from data_processing.bigquery_connector import create_bigquery_connector
from context_management.config_loader import create_config_loader
from ai_processing.gemini_processor import create_gemini_processor


def test_environment_variables():
    """Test that environment variables are properly set"""
    print("🔍 Testing Environment Variables...")

    env_vars = [
        "PROJECT_ID",
        "GOOGLE_CLOUD_PROJECT_ID",
        "BQ_DATASET",
        "GEMINI_API_KEY",
        "GOOGLE_CREDENTIALS_PATH",
        "GOOGLE_APPLICATION_CREDENTIALS",
    ]

    found_vars = {}
    for var in env_vars:
        value = os.getenv(var)
        found_vars[var] = value is not None
        if value:
            print(f"   ✅ {var}: {'*' * min(10, len(value))}... (length: {len(value)})")
        else:
            print(f"   ❌ {var}: Not set")

    # Check for required combinations
    has_project_id = found_vars["PROJECT_ID"] or found_vars["GOOGLE_CLOUD_PROJECT_ID"]
    has_bq_dataset = found_vars["BQ_DATASET"]
    has_credentials = (
        found_vars["GOOGLE_CREDENTIALS_PATH"] or found_vars["GOOGLE_APPLICATION_CREDENTIALS"]
    )
    has_gemini = found_vars["GEMINI_API_KEY"]

    print(f"\n   📊 Summary:")
    print(f"   {'✅' if has_project_id else '❌'} Project ID available")
    print(f"   {'✅' if has_bq_dataset else '❌'} BigQuery dataset available")
    print(f"   {'✅' if has_credentials else '❌'} Google credentials available")
    print(f"   {'✅' if has_gemini else '❌'} Gemini API key available")

    return has_project_id and has_bq_dataset and has_credentials


def test_bigquery_connection():
    """Test BigQuery connection with environment variables"""
    print("\n🗃️  Testing BigQuery Connection...")

    try:
        # Create connector using environment variables
        connector = create_bigquery_connector()

        print(f"   📋 Project ID: {connector.project_id}")
        print(f"   📋 Dataset: {connector.dataset_id}")
        print(f"   📋 Table: {connector.table_name}")

        # Test connection
        if connector.connect():
            print("   ✅ BigQuery connection successful!")

            # Test basic query
            try:
                contact_ids = connector.get_unique_contact_ids(limit=5)
                print(f"   ✅ Retrieved {len(contact_ids)} sample contact IDs")
                if contact_ids:
                    print(f"   📋 Sample contact IDs: {contact_ids[:3]}")

                # Test ENI source types
                eni_types_df = connector.get_eni_source_types_and_subtypes()
                print(f"   ✅ Found {len(eni_types_df)} ENI source type/subtype combinations")

                if not eni_types_df.empty:
                    print("   📋 Sample ENI source types:")
                    for _, row in eni_types_df.head(5).iterrows():
                        print(
                            f"      - {row['eni_source_type']}/{row['eni_source_subtype']}: {row['count']} records"
                        )

                return True

            except Exception as e:
                print(f"   ❌ Error testing BigQuery queries: {str(e)}")
                return False
        else:
            print("   ❌ BigQuery connection failed")
            return False

    except Exception as e:
        print(f"   ❌ Error creating BigQuery connector: {str(e)}")
        return False


def test_gemini_connection():
    """Test Gemini 2.5 Flash API connection with configuration"""
    print("\n🤖 Testing Gemini 2.5 Flash AI Connection...")

    try:
        # Load configuration and create processor with config
        config_loader = create_config_loader("config/config.yaml")
        gemini_config = config_loader.get_gemini_config()

        print(f"   📋 Configured model: {gemini_config.get('model_name', 'Default')}")
        if gemini_config.get("generation_config"):
            print(f"   ⚙️  Generation settings: {gemini_config['generation_config']}")

        gemini_processor = create_gemini_processor(config=gemini_config)

        if gemini_processor:
            model_info = gemini_processor.get_model_info()
            print(f"   📋 Active Model: {model_info.get('model_name', 'Unknown')}")
            print(f"   📋 API configured: {model_info.get('api_configured', False)}")
            print(f"   📋 Model initialized: {model_info.get('model_initialized', False)}")

            if model_info.get("connection_test", False):
                print("   ✅ Gemini 2.5 Flash API connection successful!")
                return True
            else:
                print("   ❌ Gemini API connection test failed")
                return False
        else:
            print("   ❌ Failed to create Gemini processor")
            return False

    except Exception as e:
        print(f"   ❌ Error testing Gemini connection: {str(e)}")
        return False


def test_contact_data_load(contact_id: str = "CNT-7if002332"):
    """Test loading data for a specific contact"""
    print(f"\n📊 Testing Contact Data Load for {contact_id}...")

    try:
        connector = create_bigquery_connector()

        if not connector.connect():
            print("   ❌ Cannot connect to BigQuery")
            return False

        # Load contact data
        contact_data = connector.load_contact_data(contact_id)

        if contact_data.empty:
            print(f"   ⚠️  No data found for contact {contact_id}")
            return False

        print(f"   ✅ Loaded {len(contact_data)} records for {contact_id}")
        print(f"   📋 Columns: {list(contact_data.columns)}")

        # Show sample data
        if not contact_data.empty:
            first_record = contact_data.iloc[0]
            print(f"   📋 Sample record:")
            print(f"      - ENI Source Type: {first_record.get('eni_source_type', 'N/A')}")
            print(f"      - ENI Source Subtype: {first_record.get('eni_source_subtype', 'N/A')}")
            print(f"      - Member Name: {first_record.get('member_name', 'N/A')}")
            print(f"      - Description Length: {len(str(first_record.get('description', '')))}")

            # Group by source type/subtype
            groups = contact_data.groupby(["eni_source_type", "eni_source_subtype"]).size()
            print(f"   📋 Data breakdown:")
            for (source_type, source_subtype), count in groups.items():
                print(f"      - {source_type}/{source_subtype}: {count} records")

        return True

    except Exception as e:
        print(f"   ❌ Error loading contact data: {str(e)}")
        return False


def main():
    """Run all tests"""
    print("🚀 Member Insights Processor - Environment & Connection Testing\n")

    # Test environment variables
    env_ok = test_environment_variables()

    if not env_ok:
        print("\n❌ Environment variables not properly configured. Please set:")
        print("   - PROJECT_ID or GOOGLE_CLOUD_PROJECT_ID")
        print("   - BQ_DATASET")
        print("   - GOOGLE_CREDENTIALS_PATH or GOOGLE_APPLICATION_CREDENTIALS")
        print("   - GEMINI_API_KEY")
        return 1

    # Test BigQuery connection
    bq_ok = test_bigquery_connection()

    # Test Gemini connection
    gemini_ok = test_gemini_connection()

    # Test contact data loading
    contact_ok = test_contact_data_load("CNT-7if002332")

    # Summary
    print(f"\n📋 Test Summary:")
    print(f"   {'✅' if env_ok else '❌'} Environment variables")
    print(f"   {'✅' if bq_ok else '❌'} BigQuery connection")
    print(f"   {'✅' if gemini_ok else '❌'} Gemini API connection")
    print(f"   {'✅' if contact_ok else '❌'} Contact data loading")

    if all([env_ok, bq_ok, contact_ok]):
        print(f"\n🎉 All core systems working! Ready to process contact CNT-7if002332")
        if gemini_ok:
            print("🤖 AI processing also available!")
        else:
            print("⚠️  AI processing unavailable (set GEMINI_API_KEY)")
        return 0
    else:
        print(f"\n❌ Some systems not working. Check configuration.")
        return 1


if __name__ == "__main__":
    # Change to the correct directory for running tests
    test_dir = Path(__file__).parent.parent
    os.chdir(test_dir)

    exit(main())
