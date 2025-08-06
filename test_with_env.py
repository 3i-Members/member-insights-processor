#!/usr/bin/env python3
"""
Test script that loads environment variables from .env file and tests Supabase upload.
"""

import os
import sys
from pathlib import Path

def load_env_file(env_path: str):
    """Load environment variables from .env file."""
    if not os.path.exists(env_path):
        print(f"❌ .env file not found at: {env_path}")
        return False
    
    print(f"📂 Loading environment variables from: {env_path}")
    
    try:
        with open(env_path, 'r') as f:
            lines = f.readlines()
        
        loaded_vars = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")  # Remove quotes if present
                os.environ[key] = value
                if 'SUPABASE' in key:
                    loaded_vars.append(key)
        
        print(f"✅ Loaded {len(loaded_vars)} Supabase environment variables:")
        for var in loaded_vars:
            # Mask sensitive values
            value = os.environ[var]
            if 'KEY' in var or 'TOKEN' in var:
                masked_value = value[:10] + '...' + value[-4:] if len(value) > 14 else '***'
                print(f"   {var}={masked_value}")
            else:
                print(f"   {var}={value}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error loading .env file: {e}")
        return False

def main():
    print("🚀 Supabase Upload Test with .env")
    print("=" * 50)
    
    # Try to load .env from parent directory
    env_path = Path(__file__).parent.parent / ".env"
    
    if not load_env_file(str(env_path)):
        print("\n❌ Could not load .env file. Please ensure it exists in the parent directory.")
        sys.exit(1)
    
    # Check if required variables are now set
    required_vars = ['SUPABASE_URL', 'SUPABASE_SERVICE_ROLE_KEY']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"\n❌ Missing required environment variables: {missing_vars}")
        print("Please ensure these are defined in your .env file:")
        for var in missing_vars:
            print(f"   {var}=your_value_here")
        sys.exit(1)
    
    print(f"\n✅ All required environment variables are set!")
    print("\n" + "=" * 50)
    
    # Now import and run the test module
    try:
        # Add the current directory to path for imports
        sys.path.insert(0, str(Path(__file__).parent))
        
        # Import the test functions
        from test_supabase_upload import test_table_structure, test_supabase_upload
        
        # Run table structure test first
        if not test_table_structure():
            print("\n❌ Table structure test failed. Please set up the database schema first.")
            print("\nTo create the table:")
            print("1. Go to your Supabase dashboard")
            print("2. Navigate to SQL Editor")
            print("3. Run the contents of config/supabase_schema.sql")
            sys.exit(1)
        
        # Run upload test
        if test_supabase_upload():
            print("\n✅ All tests passed! Supabase integration is working correctly.")
        else:
            print("\n❌ Upload test failed. Please check the logs above.")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Error running tests: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main() 