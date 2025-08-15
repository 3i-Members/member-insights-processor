"""
Markdown Writer Module

This module handles writing AI-generated summaries and insights
to markdown files with proper metadata headers.
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)


class MarkdownWriter:
    """Handles writing AI outputs to markdown files with metadata."""
    
    def __init__(self, output_directory: str = "output/member_summaries/"):
        """
        Initialize the markdown writer.
        
        Args:
            output_directory: Base directory for output files
        """
        self.output_directory = Path(output_directory)
        self._ensure_output_directory()
    
    def _ensure_output_directory(self) -> None:
        """Create output directory if it doesn't exist."""
        try:
            self.output_directory.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Output directory ensured: {self.output_directory}")
        except Exception as e:
            logger.error(f"Failed to create output directory {self.output_directory}: {str(e)}")
    
    def generate_filename(self, contact_id: str, eni_id: str) -> str:
        """
        Generate filename for the markdown file.
        
        Args:
            contact_id: The contact ID
            eni_id: The ENI ID
            
        Returns:
            str: Generated filename
        """
        # Sanitize the IDs to be filesystem-safe
        safe_contact_id = str(contact_id).replace('/', '_').replace('\\', '_')
        safe_eni_id = str(eni_id).replace('/', '_').replace('\\', '_')
        
        return f"{safe_contact_id}_{safe_eni_id}.md"
    
    def create_metadata_header(
        self,
        contact_id: str,
        eni_id: str,
        additional_metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create YAML front matter metadata header.
        
        Args:
            contact_id: The contact ID
            eni_id: The ENI ID
            additional_metadata: Optional additional metadata fields
            
        Returns:
            str: YAML front matter header
        """
        try:
            # Get current timestamp
            timestamp = datetime.now().isoformat()
            
            # Build metadata dictionary
            metadata = {
                'contact_id': str(contact_id),
                'eni_id': str(eni_id),
                'generated_at': timestamp
            }
            
            # Add any additional metadata
            if additional_metadata:
                metadata.update(additional_metadata)
            
            # Create YAML front matter
            header_lines = ['---']
            for key, value in metadata.items():
                # Handle different data types
                if isinstance(value, str):
                    # Escape quotes and handle multiline strings
                    if '\n' in value or '"' in value or "'" in value:
                        # Use block scalar for complex strings
                        header_lines.append(f'{key}: |')
                        for line in str(value).split('\n'):
                            header_lines.append(f'  {line}')
                    else:
                        header_lines.append(f'{key}: "{value}"')
                elif isinstance(value, (int, float, bool)):
                    header_lines.append(f'{key}: {value}')
                elif value is None:
                    header_lines.append(f'{key}: null')
                else:
                    # Convert to string and quote
                    header_lines.append(f'{key}: "{str(value)}"')
            
            header_lines.append('---')
            header_lines.append('')  # Empty line after front matter
            
            return '\n'.join(header_lines)
            
        except Exception as e:
            logger.error(f"Error creating metadata header: {str(e)}")
            # Return basic header as fallback
            return f"""---
contact_id: "{contact_id}"
eni_id: "{eni_id}"
generated_at: "{datetime.now().isoformat()}"
---

"""
    
    def write_summary(
        self,
        contact_id: str,
        eni_id: str,
        content: str,
        output_directory: Optional[str] = None,
        additional_metadata: Optional[Dict[str, Any]] = None,
        overwrite: bool = True
    ) -> Optional[str]:
        """
        Write AI-generated summary to a markdown file.
        
        Args:
            contact_id: The contact ID
            eni_id: The ENI ID
            content: The AI-generated content
            output_directory: Optional custom output directory
            additional_metadata: Optional additional metadata
            overwrite: Whether to overwrite existing files
            
        Returns:
            Optional[str]: Path to the created file, or None if failed
        """
        try:
            # Use custom output directory if provided
            target_dir = Path(output_directory) if output_directory else self.output_directory
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename
            filename = self.generate_filename(contact_id, eni_id)
            file_path = target_dir / filename
            
            # Check if file exists and overwrite is False
            if file_path.exists() and not overwrite:
                logger.warning(f"File already exists and overwrite=False: {file_path}")
                return None
            
            # Create metadata header
            metadata_header = self.create_metadata_header(
                contact_id=contact_id,
                eni_id=eni_id,
                additional_metadata=additional_metadata
            )
            
            # Combine metadata and content
            full_content = metadata_header + content
            
            # Write to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(full_content)
            
            logger.info(f"Successfully wrote markdown file: {file_path}")
            return str(file_path)
            
        except PermissionError:
            logger.error(f"Permission denied writing to {file_path}")
            return None
        except Exception as e:
            logger.error(f"Error writing markdown file: {str(e)}")
            return None
    
    def append_to_summary(
        self,
        contact_id: str,
        eni_id: str,
        additional_content: str,
        section_title: Optional[str] = None
    ) -> bool:
        """
        Append additional content to an existing summary file.
        
        Args:
            contact_id: The contact ID
            eni_id: The ENI ID
            additional_content: Content to append
            section_title: Optional section title for the appended content
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            filename = self.generate_filename(contact_id, eni_id)
            file_path = self.output_directory / filename
            
            if not file_path.exists():
                logger.error(f"Cannot append to non-existent file: {file_path}")
                return False
            
            # Prepare content to append
            content_to_append = "\n\n"
            if section_title:
                content_to_append += f"## {section_title}\n\n"
            content_to_append += additional_content
            
            # Append to file
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(content_to_append)
            
            logger.info(f"Successfully appended to markdown file: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error appending to markdown file: {str(e)}")
            return False
    
    def read_existing_summary(self, contact_id: str, eni_id: str) -> Optional[Dict[str, str]]:
        """
        Read an existing summary file and return metadata and content.
        
        Args:
            contact_id: The contact ID
            eni_id: The ENI ID
            
        Returns:
            Optional[Dict[str, str]]: Dictionary with 'metadata' and 'content' keys, or None
        """
        try:
            filename = self.generate_filename(contact_id, eni_id)
            file_path = self.output_directory / filename
            
            if not file_path.exists():
                logger.debug(f"Summary file does not exist: {file_path}")
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Split metadata and content
            if content.startswith('---\n'):
                parts = content.split('---\n', 2)
                if len(parts) >= 3:
                    metadata = parts[1]
                    main_content = parts[2]
                    return {
                        'metadata': metadata,
                        'content': main_content.strip()
                    }
            
            # If no metadata found, return entire content
            return {
                'metadata': '',
                'content': content.strip()
            }
            
        except Exception as e:
            logger.error(f"Error reading existing summary: {str(e)}")
            return None
    
    def list_summary_files(self) -> list:
        """
        List all summary files in the output directory.
        
        Returns:
            list: List of dictionaries with file information
        """
        try:
            files = []
            
            if not self.output_directory.exists():
                return files
            
            for file_path in self.output_directory.glob("*.md"):
                try:
                    stat = file_path.stat()
                    
                    # Try to extract contact_id and eni_id from filename
                    filename = file_path.stem  # Remove .md extension
                    parts = filename.split('_', 1)
                    
                    file_info = {
                        'file_path': str(file_path),
                        'filename': file_path.name,
                        'size_bytes': stat.st_size,
                        'modified_timestamp': stat.st_mtime,
                        'contact_id': parts[0] if len(parts) >= 1 else None,
                        'eni_id': parts[1] if len(parts) >= 2 else None
                    }
                    
                    files.append(file_info)
                    
                except Exception as e:
                    logger.warning(f"Error processing file {file_path}: {str(e)}")
            
            return sorted(files, key=lambda x: x['modified_timestamp'], reverse=True)
            
        except Exception as e:
            logger.error(f"Error listing summary files: {str(e)}")
            return []
    
    def delete_summary(self, contact_id: str, eni_id: str) -> bool:
        """
        Delete a summary file.
        
        Args:
            contact_id: The contact ID
            eni_id: The ENI ID
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            filename = self.generate_filename(contact_id, eni_id)
            file_path = self.output_directory / filename
            
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Successfully deleted summary file: {file_path}")
                return True
            else:
                logger.warning(f"Summary file does not exist: {file_path}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting summary file: {str(e)}")
            return False
    
    def validate_output_directory(self) -> Dict[str, Any]:
        """
        Validate the output directory and return a report.
        
        Returns:
            Dict[str, Any]: Validation report
        """
        report = {
            'valid': True,
            'issues': [],
            'statistics': {
                'total_files': 0,
                'total_size_bytes': 0,
                'directory_exists': False,
                'directory_writable': False
            }
        }
        
        try:
            # Check if directory exists
            if self.output_directory.exists():
                report['statistics']['directory_exists'] = True
                
                # Check if writable
                if os.access(self.output_directory, os.W_OK):
                    report['statistics']['directory_writable'] = True
                else:
                    report['issues'].append("Output directory is not writable")
                    report['valid'] = False
                
                # Count files and calculate total size
                md_files = list(self.output_directory.glob("*.md"))
                report['statistics']['total_files'] = len(md_files)
                
                total_size = sum(f.stat().st_size for f in md_files)
                report['statistics']['total_size_bytes'] = total_size
                
            else:
                report['issues'].append("Output directory does not exist")
                # Try to create it
                try:
                    self.output_directory.mkdir(parents=True, exist_ok=True)
                    report['statistics']['directory_exists'] = True
                    report['statistics']['directory_writable'] = True
                except Exception as e:
                    report['issues'].append(f"Cannot create output directory: {str(e)}")
                    report['valid'] = False
            
            return report
            
        except Exception as e:
            report['issues'].append(f"Unexpected error during validation: {str(e)}")
            report['valid'] = False
            return report


def create_markdown_writer(output_directory: Optional[str] = None) -> MarkdownWriter:
    """
    Factory function to create a MarkdownWriter instance.
    
    Args:
        output_directory: Optional custom output directory
        
    Returns:
        MarkdownWriter: Configured writer instance
    """
    if output_directory is None:
        output_directory = "output/member_summaries/"
    
    return MarkdownWriter(output_directory) 


class LLMTraceWriter:
    def __init__(self, output_dir: str):
        self._raw_output_dir = str(output_dir)
        self._use_gcs = self._raw_output_dir.startswith("gs://")
        self._gcs_client = None
        self._gcs_bucket = None
        self._gcs_bucket_name = None
        self._gcs_prefix = None
        if self._use_gcs:
            self._gcs_bucket_name, self._gcs_prefix = self._parse_gcs_uri(self._raw_output_dir)
        else:
            self.output_dir = Path(self._raw_output_dir)
            self.output_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, contact_id: str, naming_pattern: str) -> Path:
        import time
        ts = time.strftime("%Y%m%d_%H%M%S")
        filename = naming_pattern.replace("{contact_id}", contact_id).replace("{timestamp}", ts)
        if self._use_gcs:
            # Return a pseudo path string for GCS (gs://bucket/prefix/filename)
            prefix = self._gcs_prefix or ""
            if prefix and not prefix.endswith("/"):
                prefix = prefix + "/"
            return Path(f"gs://{self._gcs_bucket_name}/{prefix}{filename}")
        return self.output_dir / filename

    def _parse_gcs_uri(self, uri: str) -> Tuple[str, str]:
        # gs://bucket[/optional/prefix]
        without_scheme = uri[len("gs://"):]
        parts = without_scheme.split("/", 1)
        bucket = parts[0]
        prefix = parts[1] if len(parts) > 1 else ""
        return bucket, prefix

    def _ensure_gcs(self) -> None:
        if self._gcs_client is None:
            try:
                from google.cloud import storage  # Lazy import to avoid hard dependency when unused
            except Exception as e:
                raise RuntimeError(
                    "google-cloud-storage is required to write LLM traces to GCS."
                ) from e
            self._gcs_client = storage.Client()
            self._gcs_bucket = self._gcs_client.bucket(self._gcs_bucket_name)

    def _gcs_blob_name_from_path(self, path: Path) -> str:
        # path is like gs://bucket/prefix/file
        text = str(path)
        assert text.startswith("gs://"), "Expected gs:// path for GCS operations"
        without_scheme = text[len("gs://"):]
        parts = without_scheme.split("/", 1)
        return parts[1] if len(parts) > 1 else ""

    def append_section(
        self,
        file_path: Path,
        title: str,
        content: str,
    ) -> None:
        if self._use_gcs and str(file_path).startswith("gs://"):
            # Download existing, append, re-upload
            self._ensure_gcs()
            blob_name = self._gcs_blob_name_from_path(file_path)
            blob = self._gcs_bucket.blob(blob_name)
            existing = ""
            if blob.exists():
                existing = blob.download_as_text(encoding='utf-8')
            updated = existing + f"\n## {title}\n\n" + content + "\n"
            blob.upload_from_string(updated, content_type="text/markdown; charset=utf-8")
            return
        # Local filesystem
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(f"\n## {title}\n\n")
            f.write(content)
            f.write("\n")

    def start_trace(self, contact_id: str, naming_pattern: str) -> Path:
        path = self._resolve_path(contact_id, naming_pattern)
        if self._use_gcs and str(path).startswith("gs://"):
            # Create object with header content
            self._ensure_gcs()
            blob_name = self._gcs_blob_name_from_path(path)
            blob = self._gcs_bucket.blob(blob_name)
            blob.upload_from_string(f"LLM Trace - Contact {contact_id}\n\n", content_type="text/markdown; charset=utf-8")
            return path
        # Local filesystem
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f"LLM Trace - Contact {contact_id}\n\n")
        return path