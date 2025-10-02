#!/usr/bin/env python3
"""
Simplified test script to upload structured insight to Supabase.
"""

import os
import sys
import json
import logging
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))


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


# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    print("🚀 Simple Supabase Upload Test")
    print("=" * 40)

    # Load environment variables
    load_env_file()

    try:
        from data_processing.supabase_client import SupabaseInsightsClient
        from data_processing.schema import normalize_insight_data, validate_structured_insight_json

        # Load the JSON file
        json_file = "output/structured_insights/CNT-c9M007641_COMBINED-CNT-c9M007641-9ENI.json"
        print(f"📁 Loading JSON file: {json_file}")

        with open(json_file, "r") as f:
            raw_data = json.load(f)

        print(f"✅ JSON loaded successfully")
        print(f"   Contact ID: {raw_data['metadata']['contact_id']}")
        print(f"   ENI ID: {raw_data['metadata']['eni_id']}")

        # Validate and normalize
        print("🔍 Validating data structure...")
        if not validate_structured_insight_json(raw_data):
            print("❌ JSON validation failed")
            return False

        insight = normalize_insight_data(raw_data)
        print("✅ Data validation passed")

        # Initialize Supabase client
        print("🔗 Connecting to Supabase...")
        client = SupabaseInsightsClient()
        print("✅ Supabase client initialized")

        # Try to upload
        print("📤 Uploading insight to Supabase...")

        # Check if record exists first
        existing = client.get_insight_by_contact_and_eni(
            insight.metadata.contact_id, insight.metadata.eni_id or "UNKNOWN"
        )

        if existing:
            print(f"📝 Record already exists, updating...")
            insight.id = existing.id
            result = client.update_insight(insight)
            action = "updated"
        else:
            print(f"📝 Creating new record...")
            result = client.create_insight(insight)
            action = "created"

        print(f"🎉 Success! Record {action}")
        print(f"   Database ID: {result.id}")
        print(f"   Contact ID: {result.metadata.contact_id}")
        print(f"   ENI ID: {result.metadata.eni_id}")
        print(f"   Generated At: {result.metadata.generated_at}")

        # Verify by querying back using contact_id and eni_id
        print("🔍 Verifying upload...")
        queried = client.get_insight_by_contact_and_eni(
            result.metadata.contact_id, result.metadata.eni_id or "UNKNOWN"
        )
        if queried:
            print("✅ Verification successful!")
            if queried.personal:
                print(f"   Personal section: {len(queried.personal)} chars")
            if queried.business:
                print(f"   Business section: {len(queried.business)} chars")
            if queried.investing:
                print(f"   Investing section: {len(queried.investing)} chars")
            print(f"   Database ID matches: {queried.id == result.id}")
        else:
            print("❌ Verification failed")
            return False

        print("\n🎯 Upload test completed successfully!")
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
