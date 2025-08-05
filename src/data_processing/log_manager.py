"""
Processing Log Manager Module

This module handles tracking of processed ENI IDs to prevent reprocessing
and maintain efficiency in the member insights pipeline.
"""

import json
import os
import fcntl
import time
from typing import Dict, List, Optional
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ProcessingLogManager:
    """Manages processing logs to track completed ENI IDs and prevent reprocessing."""
    
    def __init__(self, log_file_path: str = "logs/processed_records.json"):
        """
        Initialize the log manager.
        
        Args:
            log_file_path: Path to the JSON log file
        """
        self.log_file_path = Path(log_file_path)
        self._ensure_log_file_exists()
    
    def _ensure_log_file_exists(self) -> None:
        """Create log file and directory if they don't exist."""
        # Create directory if it doesn't exist
        self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create log file if it doesn't exist
        if not self.log_file_path.exists():
            self._write_log_file({})
            logger.info(f"Created new log file: {self.log_file_path}")
    
    def _read_log_file(self) -> Dict[str, List[str]]:
        """
        Read the log file with file locking for thread safety.
        
        Returns:
            Dict[str, List[str]]: Dictionary mapping contact_id to list of processed eni_ids
        """
        max_retries = 3
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            try:
                with open(self.log_file_path, 'r', encoding='utf-8') as f:
                    # Acquire shared lock for reading
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                    try:
                        content = f.read().strip()
                        if not content:
                            return {}
                        return json.loads(content)
                    finally:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            except (json.JSONDecodeError, FileNotFoundError) as e:
                logger.warning(f"Corrupted or missing log file, attempt {attempt + 1}/{max_retries}: {str(e)}")
                if attempt == max_retries - 1:
                    logger.error("Max retries reached, creating new log file")
                    self._write_log_file({})
                    return {}
                time.sleep(retry_delay)
            except Exception as e:
                logger.error(f"Unexpected error reading log file: {str(e)}")
                if attempt == max_retries - 1:
                    return {}
                time.sleep(retry_delay)
        
        return {}
    
    def _write_log_file(self, data: Dict[str, List[str]]) -> None:
        """
        Write data to log file with file locking for thread safety.
        
        Args:
            data: Dictionary to write to log file
        """
        max_retries = 3
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            try:
                # Write to temporary file first, then replace original
                temp_path = self.log_file_path.with_suffix('.tmp')
                
                with open(temp_path, 'w', encoding='utf-8') as f:
                    # Acquire exclusive lock for writing
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    try:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                        f.flush()
                        os.fsync(f.fileno())  # Force write to disk
                    finally:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                
                # Atomically replace the original file
                temp_path.replace(self.log_file_path)
                return
                
            except Exception as e:
                logger.warning(f"Error writing log file, attempt {attempt + 1}/{max_retries}: {str(e)}")
                if attempt == max_retries - 1:
                    logger.error("Failed to write log file after all retries")
                    raise
                time.sleep(retry_delay)
    
    def load_processed_records(self) -> Dict[str, List[str]]:
        """
        Load all processed records from the log file.
        
        Returns:
            Dict[str, List[str]]: Dictionary mapping contact_id to list of processed eni_ids
        """
        try:
            records = self._read_log_file()
            logger.debug(f"Loaded {len(records)} contact records from log file")
            return records
        except Exception as e:
            logger.error(f"Error loading processed records: {str(e)}")
            return {}
    
    def check_if_processed(self, contact_id: str, eni_id: str) -> bool:
        """
        Check if a specific ENI ID has been processed for a contact.
        
        Args:
            contact_id: The contact ID to check
            eni_id: The ENI ID to check
            
        Returns:
            bool: True if already processed, False otherwise
        """
        try:
            records = self._read_log_file()
            processed_enis = records.get(contact_id, [])
            is_processed = eni_id in processed_enis
            
            if is_processed:
                logger.debug(f"ENI {eni_id} already processed for contact {contact_id}")
            
            return is_processed
            
        except Exception as e:
            logger.error(f"Error checking if processed: {str(e)}")
            return False  # Default to not processed if error
    
    def mark_as_processed(self, contact_id: str, eni_id: str) -> bool:
        """
        Mark an ENI ID as processed for a contact.
        
        Args:
            contact_id: The contact ID
            eni_id: The ENI ID to mark as processed
            
        Returns:
            bool: True if successfully marked, False otherwise
        """
        try:
            records = self._read_log_file()
            
            # Initialize contact record if it doesn't exist
            if contact_id not in records:
                records[contact_id] = []
            
            # Add ENI ID if not already present
            if eni_id not in records[contact_id]:
                records[contact_id].append(eni_id)
                self._write_log_file(records)
                logger.info(f"Marked ENI {eni_id} as processed for contact {contact_id}")
                return True
            else:
                logger.debug(f"ENI {eni_id} already marked as processed for contact {contact_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error marking as processed: {str(e)}")
            return False
    
    def get_processed_eni_ids(self, contact_id: str) -> List[str]:
        """
        Get list of processed ENI IDs for a specific contact.
        
        Args:
            contact_id: The contact ID to get processed ENI IDs for
            
        Returns:
            List[str]: List of processed ENI IDs for the contact
        """
        try:
            records = self._read_log_file()
            processed_enis = records.get(contact_id, [])
            logger.debug(f"Found {len(processed_enis)} processed ENI IDs for contact {contact_id}")
            return processed_enis
            
        except Exception as e:
            logger.error(f"Error getting processed ENI IDs: {str(e)}")
            return []
    
    def mark_multiple_as_processed(self, contact_id: str, eni_ids: List[str]) -> bool:
        """
        Mark multiple ENI IDs as processed for a contact in a single operation.
        
        Args:
            contact_id: The contact ID
            eni_ids: List of ENI IDs to mark as processed
            
        Returns:
            bool: True if successfully marked, False otherwise
        """
        try:
            records = self._read_log_file()
            
            # Initialize contact record if it doesn't exist
            if contact_id not in records:
                records[contact_id] = []
            
            # Add new ENI IDs
            existing_enis = set(records[contact_id])
            new_enis = [eni_id for eni_id in eni_ids if eni_id not in existing_enis]
            
            if new_enis:
                records[contact_id].extend(new_enis)
                self._write_log_file(records)
                logger.info(f"Marked {len(new_enis)} new ENI IDs as processed for contact {contact_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error marking multiple as processed: {str(e)}")
            return False
    
    def get_processing_stats(self) -> Dict[str, int]:
        """
        Get processing statistics from the log file.
        
        Returns:
            Dict[str, int]: Statistics including total contacts and total processed ENI IDs
        """
        try:
            records = self._read_log_file()
            
            total_contacts = len(records)
            total_eni_ids = sum(len(eni_ids) for eni_ids in records.values())
            
            stats = {
                'total_contacts': total_contacts,
                'total_processed_eni_ids': total_eni_ids
            }
            
            # Add per-contact breakdown
            contact_stats = {contact_id: len(eni_ids) for contact_id, eni_ids in records.items()}
            stats['contact_breakdown'] = contact_stats
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting processing stats: {str(e)}")
            return {'total_contacts': 0, 'total_processed_eni_ids': 0, 'contact_breakdown': {}}
    
    def clear_contact_records(self, contact_id: str) -> bool:
        """
        Clear all processed ENI IDs for a specific contact.
        
        Args:
            contact_id: The contact ID to clear records for
            
        Returns:
            bool: True if successfully cleared, False otherwise
        """
        try:
            records = self._read_log_file()
            
            if contact_id in records:
                del records[contact_id]
                self._write_log_file(records)
                logger.info(f"Cleared all processed records for contact {contact_id}")
                return True
            else:
                logger.debug(f"No records found for contact {contact_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error clearing contact records: {str(e)}")
            return False
    
    def clear_all_records(self) -> bool:
        """
        Clear all processed records.
        
        Returns:
            bool: True if successfully cleared, False otherwise
        """
        try:
            self._write_log_file({})
            logger.info("Cleared all processed records")
            return True
        except Exception as e:
            logger.error(f"Error clearing all records: {str(e)}")
            return False


# Factory function for easy instantiation
def create_log_manager(log_file_path: Optional[str] = None) -> ProcessingLogManager:
    """
    Create a ProcessingLogManager instance.
    
    Args:
        log_file_path: Optional custom path for log file
        
    Returns:
        ProcessingLogManager: Configured log manager instance
    """
    if log_file_path is None:
        log_file_path = "logs/processed_records.json"
    
    return ProcessingLogManager(log_file_path) 