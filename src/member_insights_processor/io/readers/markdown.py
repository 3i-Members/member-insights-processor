"""
Markdown Reader Module

This module handles reading markdown files from the context directory
structure to provide contextual information for AI processing.
"""

import os
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class MarkdownReader:
    """Handles reading markdown files from structured context directories."""
    
    def __init__(self, base_context_dir: str = "context"):
        """
        Initialize the markdown reader.
        
        Args:
            base_context_dir: Base directory for context files
        """
        self.base_context_dir = Path(base_context_dir)
    
    def read_markdown_file(self, file_path: str) -> Optional[str]:
        """
        Read a markdown file and return its content.
        
        Args:
            file_path: Path to the markdown file (relative to project root)
            
        Returns:
            Optional[str]: Content of the markdown file, or None if file not found
        """
        try:
            full_path = Path(file_path)
            
            # Ensure the file exists
            if not full_path.exists():
                logger.warning(f"Markdown file not found: {file_path}")
                return None
            
            # Ensure it's a markdown file
            if not full_path.suffix.lower() in ['.md', '.markdown']:
                logger.warning(f"File is not a markdown file: {file_path}")
                return None
            
            # Read the file content
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            logger.info(f"Successfully read markdown file: {file_path} ({len(content)} characters)")
            return content
            
        except FileNotFoundError:
            logger.error(f"Markdown file not found: {file_path}")
            return None
        except UnicodeDecodeError as e:
            logger.error(f"Unicode decode error reading {file_path}: {str(e)}")
            return None
        except PermissionError:
            logger.error(f"Permission denied reading {file_path}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error reading markdown file {file_path}: {str(e)}")
            return None
    
    def read_context_file(self, eni_type: str, eni_subtype: str) -> Optional[str]:
        """
        Read a context markdown file based on ENI type and subtype.
        
        Args:
            eni_type: The ENI type (directory name)
            eni_subtype: The ENI subtype (filename without extension)
            
        Returns:
            Optional[str]: Content of the context file, or None if not found
        """
        try:
            # Construct the file path
            file_path = self.base_context_dir / eni_type / f"{eni_subtype}.md"
            
            logger.debug(f"Reading context file for {eni_type}/{eni_subtype}: {file_path}")
            
            return self.read_markdown_file(str(file_path))
            
        except Exception as e:
            logger.error(f"Error reading context file for {eni_type}/{eni_subtype}: {str(e)}")
            return None
    
    def list_available_context_files(self) -> dict:
        """
        List all available context files in the directory structure.
        
        Returns:
            dict: Dictionary mapping eni_type to list of available subtypes
        """
        try:
            available_files = {}
            
            if not self.base_context_dir.exists():
                logger.warning(f"Context directory does not exist: {self.base_context_dir}")
                return available_files
            
            # Iterate through ENI type directories
            for eni_type_dir in self.base_context_dir.iterdir():
                if eni_type_dir.is_dir():
                    eni_type = eni_type_dir.name
                    available_files[eni_type] = []
                    
                    # Find all markdown files in the ENI type directory
                    for file_path in eni_type_dir.glob("*.md"):
                        eni_subtype = file_path.stem  # filename without extension
                        available_files[eni_type].append(eni_subtype)
                    
                    # Sort subtypes for consistency
                    available_files[eni_type].sort()
            
            logger.info(f"Found context files for {len(available_files)} ENI types")
            return available_files
            
        except Exception as e:
            logger.error(f"Error listing available context files: {str(e)}")
            return {}
    
    def validate_context_structure(self) -> dict:
        """
        Validate the context directory structure and report any issues.
        
        Returns:
            dict: Validation report with issues and statistics
        """
        report = {
            'valid': True,
            'issues': [],
            'statistics': {
                'total_eni_types': 0,
                'total_context_files': 0,
                'empty_files': [],
                'large_files': []
            }
        }
        
        try:
            if not self.base_context_dir.exists():
                report['valid'] = False
                report['issues'].append(f"Context directory does not exist: {self.base_context_dir}")
                return report
            
            total_files = 0
            
            for eni_type_dir in self.base_context_dir.iterdir():
                if eni_type_dir.is_dir():
                    report['statistics']['total_eni_types'] += 1
                    
                    # Check for markdown files in this directory
                    md_files = list(eni_type_dir.glob("*.md"))
                    total_files += len(md_files)
                    
                    if not md_files:
                        report['issues'].append(f"No markdown files found in {eni_type_dir}")
                    
                    # Check each markdown file
                    for md_file in md_files:
                        try:
                            file_size = md_file.stat().st_size
                            
                            # Check for empty files
                            if file_size == 0:
                                report['statistics']['empty_files'].append(str(md_file))
                            
                            # Check for very large files (>100KB)
                            elif file_size > 100 * 1024:
                                report['statistics']['large_files'].append({
                                    'file': str(md_file),
                                    'size_kb': round(file_size / 1024, 2)
                                })
                            
                            # Try to read the file to check for encoding issues
                            with open(md_file, 'r', encoding='utf-8') as f:
                                f.read()
                                
                        except UnicodeDecodeError:
                            report['issues'].append(f"Unicode decode error in {md_file}")
                        except Exception as e:
                            report['issues'].append(f"Error reading {md_file}: {str(e)}")
            
            report['statistics']['total_context_files'] = total_files
            
            if report['issues']:
                report['valid'] = False
            
            logger.info(f"Context validation complete: {len(report['issues'])} issues found")
            return report
            
        except Exception as e:
            report['valid'] = False
            report['issues'].append(f"Unexpected error during validation: {str(e)}")
            return report
    
    def get_file_info(self, file_path: str) -> dict:
        """
        Get information about a markdown file.
        
        Args:
            file_path: Path to the markdown file
            
        Returns:
            dict: File information including size, modification time, etc.
        """
        try:
            path = Path(file_path)
            
            if not path.exists():
                return {'exists': False}
            
            stat = path.stat()
            
            info = {
                'exists': True,
                'size_bytes': stat.st_size,
                'size_kb': round(stat.st_size / 1024, 2),
                'modified_timestamp': stat.st_mtime,
                'is_readable': os.access(path, os.R_OK),
                'extension': path.suffix.lower()
            }
            
            # Try to get line count and character count
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    info['character_count'] = len(content)
                    info['line_count'] = len(content.splitlines())
                    info['is_empty'] = len(content.strip()) == 0
            except Exception:
                info['character_count'] = None
                info['line_count'] = None
                info['is_empty'] = None
            
            return info
            
        except Exception as e:
            logger.error(f"Error getting file info for {file_path}: {str(e)}")
            return {'exists': False, 'error': str(e)}


def create_markdown_reader(base_context_dir: Optional[str] = None) -> MarkdownReader:
    """
    Factory function to create a MarkdownReader instance.
    
    Args:
        base_context_dir: Optional custom base context directory
        
    Returns:
        MarkdownReader: Configured markdown reader instance
    """
    if base_context_dir is None:
        base_context_dir = "context"
    
    return MarkdownReader(base_context_dir) 