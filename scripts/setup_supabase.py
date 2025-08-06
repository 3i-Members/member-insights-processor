#!/usr/bin/env python3
"""
Supabase Setup and Migration Script.

This script helps set up the Supabase integration for the member insights processor,
including table creation, schema validation, and data migration.
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from typing import Dict, Any

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data_processing.supabase_client import SupabaseInsightsClient, SupabaseConnectionError
from data_processing.migration_utils import MigrationManager, create_migration_manager
from data_processing.schema import validate_structured_insight_json
from context_management.config_loader import ConfigLoader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_environment() -> Dict[str, Any]:
    """Check if required environment variables are set."""
    required_vars = ['SUPABASE_URL', 'SUPABASE_SERVICE_ROLE_KEY']
    
    status = {
        'all_set': True,
        'missing_vars': [],
        'values': {}
    }
    
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            status['all_set'] = False
            status['missing_vars'].append(var)
        else:
            # Mask the key for logging
            if 'KEY' in var:
                masked_value = value[:10] + '...' + value[-4:] if len(value) > 14 else '***'
                status['values'][var] = masked_value
            else:
                status['values'][var] = value
    
    return status


def test_supabase_connection() -> bool:
    """Test connection to Supabase."""
    try:
        client = SupabaseInsightsClient()
        logger.info("✓ Successfully connected to Supabase")
        return True
    except SupabaseConnectionError as e:
        logger.error(f"✗ Failed to connect to Supabase: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"✗ Unexpected error connecting to Supabase: {str(e)}")
        return False


def check_table_exists() -> bool:
    """Check if the structured insights table exists."""
    try:
        client = SupabaseInsightsClient()
        exists = client.create_table_if_not_exists()
        if exists:
            logger.info("✓ Table 'elvis__structured_insights' exists and is accessible")
        else:
            logger.error("✗ Table 'elvis__structured_insights' does not exist")
        return exists
    except Exception as e:
        logger.error(f"✗ Error checking table existence: {str(e)}")
        return False


def run_schema_validation() -> bool:
    """Run schema validation tests."""
    logger.info("Running schema validation tests...")
    
    # Test data samples
    test_samples = [
        # New format
        {
            "metadata": {
                "contact_id": "CNT-test123",
                "eni_id": "ENI-test456",
                "member_name": "Test Member"
            },
            "insights": {
                "personal": "Test personal info",
                "business": "Test business info"
            }
        },
        # Legacy format
        {
            "metadata": {
                "contact_id": "CNT-legacy123",
                "eni_id": "COMBINED-test",
                "generated_at": "2024-01-01T12:00:00",
                "record_count": 5
            },
            "insights": {
                "raw_content": '{"personal": "Legacy personal info"}'
            }
        }
    ]
    
    all_valid = True
    for i, sample in enumerate(test_samples, 1):
        is_valid, errors = validate_structured_insight_json(sample)
        if is_valid:
            logger.info(f"✓ Test sample {i} passed validation")
        else:
            logger.error(f"✗ Test sample {i} failed validation: {', '.join(errors)}")
            all_valid = False
    
    return all_valid


def run_migration(source_dir: str, dry_run: bool = False, force: bool = False) -> bool:
    """Run data migration from JSON files to Supabase."""
    logger.info(f"Running migration from {source_dir} (dry_run={dry_run})")
    
    try:
        client = SupabaseInsightsClient()
        manager = create_migration_manager(
            client,
            source_directory=source_dir,
            backup_directory="backups/migration" if not dry_run else None
        )
        
        if dry_run:
            # Just validate files
            files = manager.discover_json_files()
            if not files:
                logger.warning("No JSON files found to validate")
                return True
            
            valid_count = 0
            for file_path in files:
                is_valid, _, errors = manager.validate_json_file(file_path)
                if is_valid:
                    valid_count += 1
                else:
                    logger.warning(f"Invalid file {file_path}: {', '.join(errors)}")
            
            logger.info(f"Dry run completed: {valid_count}/{len(files)} files are valid")
            return valid_count == len(files)
        
        else:
            # Run actual migration
            state = manager.migrate_all_files(
                force_overwrite=force,
                batch_size=10
            )
            
            summary = manager.get_migration_summary()
            logger.info(f"Migration completed:")
            logger.info(f"  Migrated: {summary['migrated']}")
            logger.info(f"  Failed: {summary['failed']}")
            logger.info(f"  Skipped: {summary['skipped']}")
            logger.info(f"  Success rate: {summary['success_rate']:.2%}")
            
            return summary['failed'] == 0
    
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        return False


def setup_config() -> bool:
    """Set up or validate configuration."""
    config_path = Path("config/config.yaml")
    
    try:
        if config_path.exists():
            # Validate existing config
            config_loader = ConfigLoader(str(config_path))
            config = config_loader.load_config()
            
            # Check for Supabase section
            if 'supabase' in config:
                logger.info("✓ Configuration file has Supabase section")
                return True
            else:
                logger.warning("✗ Configuration file missing Supabase section")
                return False
        else:
            logger.warning("✗ Configuration file not found")
            return False
    
    except Exception as e:
        logger.error(f"✗ Error validating configuration: {str(e)}")
        return False


def main():
    """Main setup script."""
    parser = argparse.ArgumentParser(
        description="Set up Supabase integration for member insights processor"
    )
    
    parser.add_argument(
        "--action",
        choices=['check', 'validate', 'migrate', 'setup-all'],
        default='check',
        help="Action to perform"
    )
    
    parser.add_argument(
        "--source-dir",
        default="output/structured_insights",
        help="Source directory for migration"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run migration in dry-run mode"
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force overwrite existing records during migration"
    )
    
    args = parser.parse_args()
    
    logger.info("🚀 Starting Supabase setup...")
    
    # Always check environment first
    env_status = check_environment()
    if not env_status['all_set']:
        logger.error("❌ Missing required environment variables:")
        for var in env_status['missing_vars']:
            logger.error(f"  - {var}")
        logger.error("\nPlease set these environment variables and try again.")
        sys.exit(1)
    
    logger.info("✓ Environment variables are set:")
    for var, value in env_status['values'].items():
        logger.info(f"  - {var}: {value}")
    
    if args.action == 'check':
        logger.info("\n📋 Running connectivity checks...")
        
        success = True
        
        # Test connection
        if not test_supabase_connection():
            success = False
        
        # Check table
        if not check_table_exists():
            success = False
            logger.error("\n💡 To create the table, run the SQL schema file:")
            logger.error("   psql -h <host> -U <user> -d <database> -f config/supabase_schema.sql")
        
        # Check config
        if not setup_config():
            success = False
        
        if success:
            logger.info("\n✅ All checks passed! Supabase integration is ready.")
        else:
            logger.error("\n❌ Some checks failed. Please address the issues above.")
            sys.exit(1)
    
    elif args.action == 'validate':
        logger.info("\n🔍 Running schema validation...")
        if run_schema_validation():
            logger.info("✅ Schema validation passed!")
        else:
            logger.error("❌ Schema validation failed!")
            sys.exit(1)
    
    elif args.action == 'migrate':
        logger.info(f"\n📦 Running migration from {args.source_dir}...")
        
        # First check that table exists
        if not check_table_exists():
            logger.error("Cannot migrate without table. Please create the table first.")
            sys.exit(1)
        
        if run_migration(args.source_dir, args.dry_run, args.force):
            if args.dry_run:
                logger.info("✅ Migration validation passed!")
            else:
                logger.info("✅ Migration completed successfully!")
        else:
            logger.error("❌ Migration failed!")
            sys.exit(1)
    
    elif args.action == 'setup-all':
        logger.info("\n🔧 Running complete setup...")
        
        success = True
        
        # Check connection
        if not test_supabase_connection():
            success = False
        
        # Check/create table
        if not check_table_exists():
            logger.error("Table not found. Please create it manually using the SQL schema.")
            success = False
        
        # Validate schema
        if not run_schema_validation():
            success = False
        
        # Run migration validation
        if success and Path(args.source_dir).exists():
            logger.info("Running migration validation...")
            if not run_migration(args.source_dir, dry_run=True):
                logger.warning("Migration validation had issues, but continuing...")
        
        if success:
            logger.info("\n🎉 Setup completed successfully!")
            logger.info("\nNext steps:")
            logger.info("1. Run migrations: python scripts/setup_supabase.py --action migrate")
            logger.info("2. Test processing with Supabase integration")
            logger.info("3. Set up Airtable sync if needed")
        else:
            logger.error("\n❌ Setup failed. Please address the issues above.")
            sys.exit(1)


if __name__ == "__main__":
    main() 