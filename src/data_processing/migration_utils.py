"""
Migration Utilities for Supabase Integration.

This module provides utilities to migrate existing JSON files to Supabase
and integrate with the existing processing pipeline.
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime

from .schema import (
    StructuredInsight,
    normalize_insight_data,
    validate_structured_insight_json
)
from .supabase_client import SupabaseInsightsClient, SupabaseOperationError
from .supabase_insights_processor import SupabaseInsightsProcessor, ProcessingState

logger = logging.getLogger(__name__)


class MigrationManager:
    """Manages migration of existing data to Supabase."""
    
    def __init__(self, 
                 supabase_client: SupabaseInsightsClient,
                 source_directory: str = "output/structured_insights",
                 backup_directory: Optional[str] = None):
        """
        Initialize migration manager.
        
        Args:
            supabase_client: Supabase client instance
            source_directory: Directory containing JSON files to migrate
            backup_directory: Optional directory to backup migrated files
        """
        self.supabase_client = supabase_client
        self.source_directory = Path(source_directory)
        self.backup_directory = Path(backup_directory) if backup_directory else None
        
        self.processor = SupabaseInsightsProcessor(supabase_client)
        
        # Migration state
        self.migrated_files: List[str] = []
        self.failed_files: List[Tuple[str, str]] = []  # (filename, error)
        self.skipped_files: List[str] = []
        
        logger.info(f"Initialized MigrationManager for {self.source_directory}")
    
    def discover_json_files(self) -> List[Path]:
        """Discover JSON files in the source directory."""
        if not self.source_directory.exists():
            logger.warning(f"Source directory does not exist: {self.source_directory}")
            return []
        
        json_files = list(self.source_directory.glob("*.json"))
        logger.info(f"Discovered {len(json_files)} JSON files in {self.source_directory}")
        return json_files
    
    def validate_json_file(self, file_path: Path) -> Tuple[bool, Optional[Dict[str, Any]], List[str]]:
        """
        Validate a JSON file for migration.
        
        Args:
            file_path: Path to JSON file
            
        Returns:
            Tuple of (is_valid, data, errors)
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            is_valid, errors = validate_structured_insight_json(data)
            return is_valid, data, errors
            
        except json.JSONDecodeError as e:
            return False, None, [f"Invalid JSON: {str(e)}"]
        except Exception as e:
            return False, None, [f"File read error: {str(e)}"]
    
    def migrate_single_file(self, file_path: Path, force_overwrite: bool = False) -> bool:
        """
        Migrate a single JSON file to Supabase.
        
        Args:
            file_path: Path to JSON file
            force_overwrite: Force overwrite existing records
            
        Returns:
            bool: Success status
        """
        logger.debug(f"Migrating file: {file_path}")
        
        # Validate file
        is_valid, data, errors = self.validate_json_file(file_path)
        if not is_valid:
            error_msg = f"Validation failed: {', '.join(errors)}"
            logger.error(f"Failed to validate {file_path}: {error_msg}")
            self.failed_files.append((str(file_path), error_msg))
            return False
        
        try:
            # Normalize data to structured insight
            insight = normalize_insight_data(data)
            
            # Check if record already exists
            existing = self.supabase_client.get_insight_by_contact_and_eni(
                insight.metadata.contact_id,
                insight.metadata.eni_id or "UNKNOWN"
            )
            
            if existing and not force_overwrite:
                logger.info(f"Record already exists for {insight.metadata.contact_id}, skipping")
                self.skipped_files.append(str(file_path))
                return True
            
            # Migrate to Supabase
            result_insight, was_created = self.supabase_client.upsert_insight(insight)
            
            action = "created" if was_created else "updated"
            logger.info(f"Successfully {action} insight for {insight.metadata.contact_id}")
            
            # Backup original file if requested
            if self.backup_directory:
                self._backup_file(file_path)
            
            self.migrated_files.append(str(file_path))
            return True
            
        except Exception as e:
            error_msg = f"Migration failed: {str(e)}"
            logger.error(f"Failed to migrate {file_path}: {error_msg}")
            self.failed_files.append((str(file_path), error_msg))
            return False
    
    def migrate_all_files(self, 
                         force_overwrite: bool = False,
                         batch_size: int = 10) -> ProcessingState:
        """
        Migrate all JSON files to Supabase.
        
        Args:
            force_overwrite: Force overwrite existing records
            batch_size: Number of files to process per batch
            
        Returns:
            ProcessingState: Migration results
        """
        files = self.discover_json_files()
        
        if not files:
            logger.warning("No JSON files found to migrate")
            return ProcessingState()
        
        logger.info(f"Starting migration of {len(files)} files")
        start_time = datetime.now()
        
        # Process files in batches
        total_batches = (len(files) + batch_size - 1) // batch_size
        
        for i in range(0, len(files), batch_size):
            batch = files[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            
            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} files)")
            
            for file_path in batch:
                self.migrate_single_file(file_path, force_overwrite)
        
        # Create processing state summary
        state = ProcessingState()
        state.start_time = start_time
        state.end_time = datetime.now()
        
        # Populate state with results
        for file_path in self.migrated_files:
            # Extract contact_id from filename (format: CNT-xxx_xxx.json)
            contact_id = self._extract_contact_id_from_filename(file_path)
            if contact_id:
                state.mark_processed(contact_id, True)  # Assume created for migration
        
        for file_path, error in self.failed_files:
            contact_id = self._extract_contact_id_from_filename(file_path)
            if contact_id:
                state.mark_failed(contact_id, error)
        
        logger.info(f"Migration completed: {state.get_summary()}")
        return state
    
    def _backup_file(self, file_path: Path) -> None:
        """Backup a file to the backup directory."""
        if not self.backup_directory:
            return
        
        try:
            self.backup_directory.mkdir(parents=True, exist_ok=True)
            backup_path = self.backup_directory / file_path.name
            
            # Add timestamp if file already exists
            if backup_path.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                name_parts = file_path.stem, timestamp, file_path.suffix
                backup_path = self.backup_directory / f"{name_parts[0]}_{name_parts[1]}{name_parts[2]}"
            
            import shutil
            shutil.copy2(file_path, backup_path)
            logger.debug(f"Backed up {file_path} to {backup_path}")
            
        except Exception as e:
            logger.warning(f"Failed to backup {file_path}: {str(e)}")
    
    def _extract_contact_id_from_filename(self, file_path: str) -> Optional[str]:
        """Extract contact_id from filename."""
        filename = Path(file_path).stem
        if filename.startswith("CNT-"):
            # Format is typically CNT-xxx_xxx or CNT-xxx_COMBINED-xxx
            parts = filename.split("_")
            if parts:
                return parts[0]
        return None
    
    def get_migration_summary(self) -> Dict[str, Any]:
        """Get comprehensive migration summary."""
        return {
            "total_discovered": len(self.discover_json_files()),
            "migrated": len(self.migrated_files),
            "failed": len(self.failed_files),
            "skipped": len(self.skipped_files),
            "success_rate": len(self.migrated_files) / max(1, len(self.migrated_files) + len(self.failed_files)),
            "migrated_files": self.migrated_files,
            "failed_files": self.failed_files,
            "skipped_files": self.skipped_files
        }


class LegacyDataConverter:
    """Converts legacy data formats to new structured format."""
    
    @staticmethod
    def convert_raw_content_to_structured(raw_content: str) -> Optional[Dict[str, Any]]:
        """
        Convert raw content string to structured insight format.
        
        This handles the case where insights contain raw_content with JSON.
        """
        if not raw_content:
            return None
        
        try:
            # Try to extract JSON from markdown code blocks
            import re
            json_match = re.search(r'```json\s*(.*?)\s*```', raw_content, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(1)
                return json.loads(json_str)
            
            # If no code block, try to parse the whole thing
            return json.loads(raw_content)
            
        except json.JSONDecodeError:
            logger.warning("Could not parse raw_content as JSON")
            return {"error": "Could not parse raw_content", "raw_content": raw_content}
    
    @staticmethod
    def extract_citations_from_content(content: str) -> List[Tuple[str, str]]:
        """Extract citations from markdown content."""
        if not content:
            return []
        
        import re
        # Pattern to match citations like [2024-01-15,ENI-123456] or [N/A,ENI-123456]
        citation_pattern = r'\[([^,\]]+),([^\]]+)\]'
        matches = re.findall(citation_pattern, content)
        
        return [(date_str.strip(), eni_id.strip()) for date_str, eni_id in matches]


def create_migration_manager(supabase_client: SupabaseInsightsClient, **kwargs) -> MigrationManager:
    """Create a migration manager with default settings."""
    return MigrationManager(supabase_client, **kwargs)


# CLI interface for migration
def run_migration_cli():
    """Run migration from command line."""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="Migrate structured insights to Supabase")
    parser.add_argument("--source-dir", default="output/structured_insights",
                       help="Source directory containing JSON files")
    parser.add_argument("--backup-dir", help="Backup directory for migrated files")
    parser.add_argument("--force", action="store_true", help="Force overwrite existing records")
    parser.add_argument("--batch-size", type=int, default=10, help="Batch size for processing")
    parser.add_argument("--dry-run", action="store_true", help="Dry run - don't actually migrate")
    
    args = parser.parse_args()
    
    try:
        # Initialize Supabase client
        client = SupabaseInsightsClient()
        
        # Check table exists
        if not client.create_table_if_not_exists():
            logger.error("Supabase table does not exist. Please run the schema creation script first.")
            sys.exit(1)
        
        # Create migration manager
        manager = MigrationManager(
            client, 
            source_directory=args.source_dir,
            backup_directory=args.backup_dir
        )
        
        if args.dry_run:
            # Just validate files
            files = manager.discover_json_files()
            valid_count = 0
            for file_path in files:
                is_valid, _, errors = manager.validate_json_file(file_path)
                if is_valid:
                    valid_count += 1
                else:
                    print(f"Invalid file {file_path}: {', '.join(errors)}")
            
            print(f"Dry run completed: {valid_count}/{len(files)} files are valid")
        else:
            # Run migration
            state = manager.migrate_all_files(
                force_overwrite=args.force,
                batch_size=args.batch_size
            )
            
            summary = manager.get_migration_summary()
            print(f"Migration completed:")
            print(f"  Migrated: {summary['migrated']}")
            print(f"  Failed: {summary['failed']}")
            print(f"  Skipped: {summary['skipped']}")
            print(f"  Success rate: {summary['success_rate']:.2%}")
    
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    run_migration_cli()


# Export main classes
__all__ = [
    'MigrationManager',
    'LegacyDataConverter',
    'create_migration_manager',
    'run_migration_cli'
] 