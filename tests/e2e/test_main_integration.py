#!/usr/bin/env python3
"""
Test script for main pipeline integration with Supabase.
Tests processing a single contact with the updated main pipeline.
"""

import os
import sys
import logging
from pathlib import Path


# Load environment variables from .env
def load_env_file():
    env_path = Path(__file__).parent.parent / ".env"
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip().strip('"').strip("'")


# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_main_pipeline_with_supabase(contact_id: str):
    """Test the main pipeline with Supabase integration for a specific contact."""

    print(f"🚀 Testing Main Pipeline with Supabase Integration")
    print(f"Contact ID: {contact_id}")
    print("=" * 60)

    try:
        # Load environment variables
        load_env_file()

        # Import and initialize the main processor
        from main import MemberInsightsProcessor

        print("📝 Initializing Member Insights Processor...")
        processor = MemberInsightsProcessor()

        # Validate setup
        print("🔍 Validating processor setup...")
        validation = processor.validate_setup()

        if not validation["valid"]:
            print("❌ Setup validation failed:")
            for issue in validation["issues"]:
                print(f"  - {issue}")
            return False

        print("✅ Setup validation passed")

        # Check if Supabase components are initialized
        if processor.supabase_client and processor.supabase_processor:
            print("✅ Supabase components initialized")
        else:
            print("⚠️  Supabase components not initialized")

        # Process the specific contact
        print(f"\n📤 Processing contact: {contact_id}")
        print("-" * 40)

        result = processor.process_contact(
            contact_id=contact_id,
            system_prompt_key="structured_insight",
            dry_run=False,  # Actually save the results
        )

        # Display results
        print(f"\n📊 Processing Results:")
        print(f"✅ Success: {result.get('success', False)}")
        print(f"📁 Files Created: {len(result.get('files_created', []))}")
        print(f"🗃️  Processed ENI IDs: {len(result.get('processed_eni_ids', []))}")
        print(f"❌ Errors: {len(result.get('errors', []))}")

        if result.get("supabase_record_id"):
            print(f"💾 Supabase Record ID: {result['supabase_record_id']}")

        if result.get("files_created"):
            print(f"\n📁 Created Files:")
            for file_path in result["files_created"]:
                print(f"  - {file_path}")

        if result.get("errors"):
            print(f"\n❌ Errors:")
            for error in result["errors"]:
                print(f"  - {error}")

        # Test querying the result from Supabase
        if processor.supabase_client and result.get("success"):
            print(f"\n🔍 Verifying Supabase Storage...")
            try:
                queried_insight = processor.supabase_client.get_latest_insight_by_contact_id(
                    contact_id, generator="structured_insight"
                )
                if queried_insight:
                    print(f"✅ Found latest insight in Supabase")
                    print(f"   Database ID: {queried_insight.id}")
                    print(f"   Generated At: {queried_insight.metadata.generated_at}")
                    print(f"   ENI Source Types: {queried_insight.metadata.eni_source_types}")
                    print(f"   Version: {queried_insight.metadata.version}")
                    print(f"   Is Latest: {queried_insight.is_latest}")

                    # Access insights from the JSON structure
                    insights_content = queried_insight.insights
                    if isinstance(insights_content, dict):
                        personal = insights_content.get("personal", "")
                        business = insights_content.get("business", "")
                    else:
                        personal = getattr(insights_content, "personal", "") or ""
                        business = getattr(insights_content, "business", "") or ""

                    if personal:
                        print(f"   Personal Section: {len(personal)} characters")
                    if business:
                        print(f"   Business Section: {len(business)} characters")
                else:
                    print("❌ No latest insight found in Supabase")
            except Exception as e:
                print(f"❌ Error querying Supabase: {e}")

        print(f"\n🎯 Test completed for {contact_id}")
        return result.get("success", False)

    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    # Test with the specific contact IDs provided
    test_contact_ids = ["CNT-zd6007893", "CNT-SIB007487"]

    print("🧪 Testing Main Pipeline Integration with Supabase")
    print("=" * 60)

    for contact_id in test_contact_ids:
        print(f"\n\n{'='*20} TESTING {contact_id} {'='*20}")

        success = test_main_pipeline_with_supabase(contact_id)

        if success:
            print(f"✅ {contact_id}: PASSED")
        else:
            print(f"❌ {contact_id}: FAILED")

        # Only test one contact for now to avoid processing too much
        print(f"\n⏸️  Testing stopped after {contact_id} (as requested)")
        break

    print(f"\n🏁 Integration testing completed!")


if __name__ == "__main__":
    main()
