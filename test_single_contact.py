#!/usr/bin/env python3
"""
Test script for a single contact with Supabase integration.
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

def main():
    """Test single contact processing."""
    
    # Load environment variables
    load_env_file()
    
    # Import and test
    from main import MemberInsightsProcessor
    
    contact_id = "CNT-SIB007487"  # Try the second contact ID
    
    print(f"🚀 Testing single contact: {contact_id}")
    print("=" * 50)
    
    try:
        processor = MemberInsightsProcessor()
        
        print("✅ Processor initialized")
        
        # Check Supabase status
        if processor.supabase_client:
            print("✅ Supabase client available")
        else:
            print("❌ Supabase client not available")
        
        # Process the contact
        result = processor.process_contact(
            contact_id=contact_id,
            system_prompt_key="structured_insight",
            dry_run=False
        )
        
        print(f"\n📊 Results:")
        print(f"Success: {result.get('success', False)}")
        print(f"Processed ENI IDs: {len(result.get('processed_eni_ids', []))}")
        print(f"Errors: {len(result.get('errors', []))}")
        print(f"Files created: {len(result.get('files_created', []))}")
        
        if result.get('supabase_record_id'):
            print(f"Supabase Record ID: {result['supabase_record_id']}")
            print(f"Supabase Action: {result.get('supabase_action', 'unknown')}")
        
        if result.get('errors'):
            print("\nErrors:")
            for error in result['errors']:
                print(f"  - {error}")
        
        return result.get('success', False)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    print(f"\n{'✅ SUCCESS' if success else '❌ FAILED'}") 