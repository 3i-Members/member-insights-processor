#!/usr/bin/env python3
"""
Test script for Supabase-powered Airtable sync.
Tests pulling data from Supabase and syncing to Airtable for a specific contact.
"""

import os
import sys
import logging
from pathlib import Path

# Load environment variables from .env
def load_env_file():
    env_path = Path(__file__).parent.parent / ".env"
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip().strip('"').strip("'")

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_airtable_sync_from_supabase(contact_id: str):
    """Test syncing a specific contact from Supabase to Airtable."""
    
    print(f"🚀 Testing Airtable Sync from Supabase")
    print(f"Contact ID: {contact_id}")
    print("=" * 60)
    
    try:
        # Load environment variables
        load_env_file()
        
        # Import required components
        from data_processing.supabase_client import SupabaseInsightsClient
        from output_management.supabase_airtable_writer import SupabaseAirtableSync
        from output_management.structured_airtable_writer import create_structured_airtable_writer
        from context_management.config_loader import create_config_loader
        
        print("📝 Initializing components...")
        
        # Initialize configuration
        config_loader = create_config_loader("config/config.yaml")
        airtable_config = config_loader.get_airtable_config()
        
        # Initialize Supabase client
        supabase_client = SupabaseInsightsClient()
        print("✅ Supabase client initialized")
        
        # Initialize Airtable writer
        if airtable_config:
            airtable_writer = create_structured_airtable_writer(config=airtable_config)
        else:
            # Use environment variables
            airtable_writer = create_structured_airtable_writer(config={})
        print("✅ Airtable writer initialized")
        
        # Initialize Supabase-Airtable sync service
        sync_service = SupabaseAirtableSync(supabase_client, airtable_writer)
        print("✅ Sync service initialized")
        
        # First, verify the structured insight exists in Supabase
        print(f"\n🔍 Checking Supabase for contact {contact_id}...")
        insight = supabase_client.get_latest_insight_by_contact_id(contact_id, generator='structured_insight')
        
        if not insight:
            print(f"❌ No latest structured insight found in Supabase for {contact_id}")
            print("You need to process this contact first with the main pipeline.")
            return False
        
        print(f"✅ Found latest insight in Supabase:")
        print(f"   Database ID: {insight.id}")
        print(f"   ENI ID: {insight.metadata.eni_id}")
        print(f"   Generated At: {insight.metadata.generated_at}")
        print(f"   ENI Source Types: {insight.metadata.eni_source_types}")
        print(f"   Version: {insight.metadata.version}")
        print(f"   Is Latest: {insight.is_latest}")
        
        # Access insights from the JSON structure instead of individual fields
        insights_content = insight.insights
        if isinstance(insights_content, dict):
            personal = insights_content.get('personal', '')
            business = insights_content.get('business', '')
            investing = insights_content.get('investing', '')
        else:
            # If insights is a StructuredInsightContent object
            personal = getattr(insights_content, 'personal', '') or ''
            business = getattr(insights_content, 'business', '') or ''
            investing = getattr(insights_content, 'investing', '') or ''
        
        if personal:
            print(f"   Personal section: {len(personal)} characters")
        if business:
            print(f"   Business section: {len(business)} characters")
        if investing:
            print(f"   Investing section: {len(investing)} characters")
        
        # Now test the sync to Airtable
        print(f"\n📤 Syncing to Airtable...")
        sync_result = sync_service.sync_contact_to_airtable(
            contact_id=contact_id,
            force_update=True  # Force update for testing
        )
        
        # Display sync results
        print(f"\n📊 Sync Results:")
        print(f"✅ Success: {sync_result.success}")
        print(f"📝 Action: {sync_result.action}")
        print(f"🗃️  Contact ID: {sync_result.contact_id}")
        
        if sync_result.airtable_record_id:
            print(f"📋 Airtable Record ID: {sync_result.airtable_record_id}")
        
        if sync_result.error_message:
            print(f"❌ Error: {sync_result.error_message}")
        
        # Test batch sync (just for this one contact)
        print(f"\n🔄 Testing batch sync...")
        batch_results = sync_service.sync_specific_contacts([contact_id])
        
        print(f"Batch Results:")
        print(f"  Total processed: {len(batch_results)}")
        
        for result in batch_results:
            print(f"  {result.contact_id}: {result.action} ({'✅' if result.success else '❌'})")
            if result.error_message:
                print(f"    Error: {result.error_message}")
        
        print(f"\n🎯 Airtable sync test completed for {contact_id}")
        return sync_result.success
        
    except Exception as e:
        print(f"❌ Error during sync testing: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    # Test with the contact ID that we know has data in Supabase
    contact_id = "CNT-zd6007893"  # This was requested in the original ask
    
    print("🧪 Testing Supabase-Powered Airtable Sync")
    print("=" * 60)
    
    success = test_airtable_sync_from_supabase(contact_id)
    
    if success:
        print(f"\n✅ {contact_id}: SYNC SUCCESSFUL")
    else:
        print(f"\n❌ {contact_id}: SYNC FAILED")
        
        # If first contact failed, try the second one we know has data
        print(f"\nTrying backup contact: CNT-SIB007487")
        backup_success = test_airtable_sync_from_supabase("CNT-SIB007487")
        
        if backup_success:
            print(f"\n✅ CNT-SIB007487: SYNC SUCCESSFUL")
        else:
            print(f"\n❌ CNT-SIB007487: SYNC FAILED")
    
    print(f"\n🏁 Airtable sync testing completed!")


if __name__ == "__main__":
    main() 