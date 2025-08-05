"""
Main Processing Pipeline

This module orchestrates the complete member insights processing workflow,
integrating all components for end-to-end data processing and AI insights generation.
"""

import os
import logging
import pandas as pd
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

# Import all components
from data_processing.bigquery_connector import create_bigquery_connector
from data_processing.log_manager import create_log_manager
from context_management.config_loader import create_config_loader
from context_management.markdown_reader import create_markdown_reader
from context_management.processing_filter import create_processing_filter
from ai_processing.gemini_processor import create_gemini_processor
from ai_processing.openai_processor import create_openai_processor
from ai_processing.anthropic_processor import AnthropicProcessor
from output_management.markdown_writer import create_markdown_writer
from output_management.airtable_writer import create_airtable_writer
from output_management.enhanced_airtable_writer import create_enhanced_airtable_writer
from output_management.json_writer import create_json_writer
from output_management.structured_airtable_writer import create_structured_airtable_writer
from utils.enhanced_logger import create_enhanced_logger

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/processing.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class MemberInsightsProcessor:
    """Main processor that orchestrates the complete member insights workflow."""
    
    def __init__(self, config_file_path: str = "config/config.yaml", filter_file_path: Optional[str] = None):
        """
        Initialize the member insights processor.
        
        Args:
            config_file_path: Path to the configuration file
            filter_file_path: Optional path to processing filter file (overrides default)
        """
        self.config_file_path = config_file_path
        self.filter_file_path = filter_file_path
        self.config_loader = None
        self.bigquery_connector = None
        self.log_manager = None
        self.markdown_reader = None
        self.processing_filter = None
        self.ai_processor = None  # Will be either Gemini or OpenAI
        self.markdown_writer = None
        self.airtable_writer = None
        self.json_writer = None
        self.structured_airtable_writer = None
        self.enhanced_logger = None
        
        self._initialize_components()
    
    def _initialize_components(self) -> None:
        """Initialize all processing components."""
        try:
            # Load configuration
            self.config_loader = create_config_loader(self.config_file_path)
            logger.info("Configuration loaded successfully")
            
            # Initialize enhanced logging system
            logging_config = self.config_loader.config_data.get('logging', {})
            self.enhanced_logger = create_enhanced_logger(logging_config)
            self.enhanced_logger.logger.info("Enhanced logging system initialized")
            
            # Initialize BigQuery connector
            self.bigquery_connector = create_bigquery_connector(self.config_loader.config_data)
            
            # Initialize log manager
            self.log_manager = create_log_manager()
            
            # Initialize markdown reader
            self.markdown_reader = create_markdown_reader()
            
            # Initialize processing filter
            filter_file = self.filter_file_path or self.config_loader.get_default_filter_file()
            if filter_file:
                self.processing_filter = create_processing_filter(filter_file)
                logger.info(f"Processing filter loaded from: {filter_file}")
            else:
                logger.warning("No processing filter configured - all records will be processed")
            
            # Initialize AI processor (OpenAI, Gemini, or Anthropic based on configuration)
            ai_provider = self.config_loader.get_ai_provider()
            
            if ai_provider.lower() == 'openai':
                openai_config = self.config_loader.get_openai_config()
                self.ai_processor = create_openai_processor(config=openai_config)
                logger.info("Initialized OpenAI processor")
            elif ai_provider.lower() == 'anthropic':
                anthropic_config = self.config_loader.get_anthropic_config()
                self.ai_processor = AnthropicProcessor(
                    model_name=anthropic_config.get('model_name', 'claude-3-5-sonnet-20241022'),
                    generation_config=anthropic_config.get('generation_config', {})
                )
                logger.info("Initialized Anthropic processor")
            else:
                gemini_config = self.config_loader.get_gemini_config()
                self.ai_processor = create_gemini_processor(config=gemini_config)
                logger.info("Initialized Gemini processor")
            
            # Initialize markdown writer
            self.markdown_writer = create_markdown_writer()
            
            # Initialize enhanced Airtable writer (optional)
            airtable_config = self.config_loader.get_airtable_config()
            if airtable_config:
                self.airtable_writer = create_enhanced_airtable_writer()
            else:
                # Try to initialize with environment variables
                self.airtable_writer = create_enhanced_airtable_writer()
            
            # Initialize JSON writer for structured insights
            self.json_writer = create_json_writer()
            
            # Initialize structured Airtable writer (optional)
            if airtable_config:
                self.structured_airtable_writer = create_structured_airtable_writer(
                    config=airtable_config
                )
            
            logger.info("All components initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize components: {str(e)}")
            raise
    
    def validate_setup(self) -> Dict[str, Any]:
        """
        Validate the complete setup and return a report.
        
        Returns:
            Dict[str, Any]: Validation report
        """
        report = {
            'valid': True,
            'component_status': {},
            'issues': [],
            'warnings': []
        }
        
        try:
            # Validate configuration
            config_validation = self.config_loader.validate_configuration()
            report['component_status']['config'] = config_validation
            if not config_validation['valid']:
                report['valid'] = False
                report['issues'].extend(config_validation['issues'])
            
            # Validate BigQuery connection
            if self.bigquery_connector:
                bq_connected = self.bigquery_connector.connect()
                report['component_status']['bigquery'] = {
                    'connected': bq_connected
                }
                if not bq_connected:
                    report['issues'].append("BigQuery connection failed")
                    report['valid'] = False
            else:
                report['issues'].append("BigQuery connector not initialized")
                report['valid'] = False
            
            # Validate Gemini processor
            if self.ai_processor: # Changed from self.gemini_processor to self.ai_processor
                gemini_info = self.ai_processor.get_model_info() # Changed from self.gemini_processor to self.ai_processor
                report['component_status']['gemini'] = gemini_info
                if not gemini_info.get('connection_test', False):
                    report['warnings'].append("Gemini API connection test failed")
            else:
                report['issues'].append("Gemini processor not initialized")
                report['valid'] = False
            
            # Validate context structure
            if self.markdown_reader:
                context_validation = self.markdown_reader.validate_context_structure()
                report['component_status']['context'] = context_validation
                if not context_validation['valid']:
                    report['warnings'].extend(context_validation['issues'])
            
            # Validate output directory
            if self.markdown_writer:
                output_validation = self.markdown_writer.validate_output_directory()
                report['component_status']['output'] = output_validation
                if not output_validation['valid']:
                    report['issues'].extend(output_validation['issues'])
            
            # Validate Airtable (if configured)
            if self.airtable_writer:
                airtable_info = self.airtable_writer.get_table_info()
                report['component_status']['airtable'] = airtable_info
                if not airtable_info.get('connection_test', False):
                    report['warnings'].append("Airtable connection test failed")
            
            logger.info(f"Setup validation complete: {len(report['issues'])} issues, {len(report['warnings'])} warnings")
            return report
            
        except Exception as e:
            report['valid'] = False
            report['issues'].append(f"Validation error: {str(e)}")
            return report
    
    def process_contact(
        self,
        contact_id: str,
        system_prompt_key: str = "structured_insight",
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Process a single contact's data.
        
        Args:
            contact_id: The contact ID to process
            system_prompt_key: System prompt key to use (only structured_insight supported)
            dry_run: If True, don't save results or update logs
            
        Returns:
            Dict[str, Any]: Processing results
        """
        result = {
            'contact_id': contact_id,
            'success': False,
            'processed_eni_ids': [],
            'skipped_eni_ids': [],
            'errors': [],
            'files_created': [],
            'airtable_records': []
        }
        
        try:
            # Ensure BigQuery connection is established
            if not self.bigquery_connector.connect():
                result['errors'].append("Failed to connect to BigQuery")
                return result
            
            # Get processed ENI IDs for this contact
            processed_eni_ids = self.log_manager.get_processed_eni_ids(contact_id)
            
            # Load contact data from BigQuery
            contact_data = self.bigquery_connector.load_contact_data(
                contact_id=contact_id,
                processed_eni_ids=processed_eni_ids
            )
            
            if contact_data.empty:
                logger.info(f"No unprocessed data found for contact {contact_id}")
                result['success'] = True
                return result
            
            # Verify required columns exist
            if 'eni_source_type' not in contact_data.columns:
                result['errors'].append("Required column 'eni_source_type' not found in data")
                return result
            
            # Handle cases where eni_source_subtype might be null, empty, or NaN
            # Convert various null representations to 'null' string for consistent processing
            contact_data['eni_source_subtype'] = contact_data['eni_source_subtype'].fillna('null')
            
            # Also handle empty strings and other null-like values
            mask = (contact_data['eni_source_subtype'].astype(str).str.strip() == '') | \
                   (contact_data['eni_source_subtype'].astype(str).str.lower().isin(['none', 'nan', 'nat']))
            contact_data.loc[mask, 'eni_source_subtype'] = 'null'
            
            original_record_count = len(contact_data)
            
            # Apply processing filter if configured
            if self.processing_filter:
                filtered_data, filter_stats = self.processing_filter.filter_dataframe(contact_data)
                
                if filter_stats['skipped_count'] > 0:
                    logger.info(f"Processing filter: {filter_stats['filtered_count']}/{filter_stats['original_count']} "
                              f"records included for contact {contact_id} ({filter_stats['filter_efficiency']:.1f}%)")
                
                contact_data = filtered_data
                result['filter_stats'] = filter_stats
                
                if contact_data.empty:
                    logger.info(f"All records filtered out for contact {contact_id}")
                    result['success'] = True
                    return result
            else:
                logger.debug(f"No processing filter applied - processing all {original_record_count} records")
            
            # Only process structured insights (removed member summary functionality)
            result_data = self._process_combined_structured_insight(
                contact_id, contact_data, system_prompt_key, dry_run
            )
            result.update(result_data)
            
            return result
            
        except Exception as e:
            result['errors'].append(f"Unexpected error processing contact {contact_id}: {str(e)}")
            logger.error(f"Error processing contact {contact_id}: {str(e)}")
            return result
    
    def _process_combined_structured_insight(
        self,
        contact_id: str,
        contact_data: pd.DataFrame,
        system_prompt_key: str,
        dry_run: bool
    ) -> Dict[str, Any]:
        """
        Process all ENI groups for a contact into a single comprehensive structured insight.
        
        Args:
            contact_id: The contact ID to process
            contact_data: All filtered contact data for this contact
            system_prompt_key: System prompt key (should be "structured_insight")
            dry_run: If True, don't save results or update logs
            
        Returns:
            Dict[str, Any]: Processing results
        """
        result = {
            'processed_eni_ids': [],
            'errors': [],
            'files_created': [],
            'airtable_records': []
        }
        
        try:
            # Enhanced logging for combined processing start
            if self.enhanced_logger:
                self.enhanced_logger.log_contact_processing_start(contact_id, len(contact_data), len(contact_data))
            
            # Initialize empty member summary structure
            member_summary = {
                "personal": "",
                "business": "",
                "investing": "",
                "3i": "",
                "deals": "This Member **Has Experience** and Is Comfortable Diligencing These Asset Classes & Sectors\n\nThis Member **Is Interested In Exploring** These Asset Classes, Sectors, and Strategies\n\nThis Member **Wants to Avoid** These Asset Classes, Sectors, and Strategies\n",
                "introductions": "**Looking to meet:**\n\n**Avoid introductions to:**\n"
            }
            
            # Group data by ENI source type and subtype
            grouped_data = contact_data.groupby(['eni_source_type', 'eni_source_subtype'])
            
            # Build comprehensive context from all ENI groups
            all_contexts = []
            all_member_data = []
            total_eni_ids = []
            
            for (eni_source_type, eni_source_subtype), group_data in grouped_data:
                try:
                    logger.info(f"Collecting context for {eni_source_type}/{eni_source_subtype} for contact {contact_id}")
                    
                    # Load context for this ENI source type/subtype
                    context_file_paths = self.config_loader.get_context_file_paths(eni_source_type, eni_source_subtype)
                    
                    context_parts = []
                    
                    # Load default context first
                    if context_file_paths['default']:
                        default_content = self.markdown_reader.read_markdown_file(context_file_paths['default'])
                        if default_content:
                            context_parts.append(f"=== DEFAULT CONTEXT FOR {eni_source_type.upper()} ===\n{default_content}")
                    
                    # Load subtype-specific context if available
                    if context_file_paths['subtype']:
                        subtype_content = self.markdown_reader.read_markdown_file(context_file_paths['subtype'])
                        if subtype_content:
                            context_parts.append(f"=== SUBTYPE CONTEXT FOR {eni_source_type.upper()}/{eni_source_subtype.upper()} ===\n{subtype_content}")
                    
                    # Add context with data type label
                    if context_parts:
                        group_context = f"=== ENI GROUP: {eni_source_type}/{eni_source_subtype} ({len(group_data)} records) ===\n"
                        group_context += "\n\n".join(context_parts)
                        all_contexts.append(group_context)
                    
                    # Add member data for this group
                    group_member_data = f"=== DATA FOR {eni_source_type.upper()}/{eni_source_subtype.upper()} ===\n"
                    for _, row in group_data.iterrows():
                        if pd.notna(row.get('description')):
                            group_member_data += f"- {row['description']}\n"
                    all_member_data.append(group_member_data)
                    
                    # Collect ENI IDs
                    eni_ids_in_group = group_data['eni_id'].tolist()
                    total_eni_ids.extend(eni_ids_in_group)
                    
                except Exception as e:
                    error_msg = f"Error collecting context for {eni_source_type}/{eni_source_subtype}: {str(e)}"
                    result['errors'].append(error_msg)
                    logger.error(error_msg)
                    continue
            
            # Combine all contexts and data
            comprehensive_context = "\n\n".join(all_contexts)
            comprehensive_member_data = "\n\n".join(all_member_data)
            
            # Build final prompt for AI processing
            final_prompt_context = f"""
EXISTING MEMBER SUMMARY (to be updated):
{member_summary}

COMPREHENSIVE CONTEXT FROM ALL ENI GROUPS:
{comprehensive_context}

ALL MEMBER DATA TO ANALYZE:
{comprehensive_member_data}
"""
            
            # Enhanced logging for AI call
            if self.enhanced_logger:
                self.enhanced_logger.log_ai_call_start(
                    self.ai_processor.model_name if hasattr(self.ai_processor, 'model_name') else 'AI',
                    "combined_structured_insight",
                    "all_eni_groups",
                    len(total_eni_ids)
                )
            
            # Process with AI
            start_time = time.time()
            insights = self.ai_processor.process_single_contact(
                contact_data=contact_data,
                system_prompt_key=system_prompt_key,
                context_content=final_prompt_context,
                config_loader=self.config_loader
            )
            ai_duration = time.time() - start_time
            
            # Enhanced logging for AI call end
            if self.enhanced_logger:
                self.enhanced_logger.log_ai_call_end(
                    self.ai_processor.model_name if hasattr(self.ai_processor, 'model_name') else 'AI',
                    "combined_structured_insight",
                    "all_eni_groups",
                    bool(insights),
                    ai_duration,
                    len(insights) if insights else 0
                )
            
            if not insights:
                result['errors'].append(f"Failed to generate insights for contact {contact_id}")
                return result
            
            # Generate single combined ENI ID for the comprehensive insight
            combined_eni_id = f"COMBINED-{contact_id}-{len(total_eni_ids)}ENI"
            
            if not dry_run:
                # Write to JSON file (structured insights always use JSON)
                json_file = self.json_writer.write_structured_insight(
                    contact_id=contact_id,
                    eni_id=combined_eni_id,
                    content=insights,
                    additional_metadata={
                        'eni_source_types': list(set(contact_data['eni_source_type'].tolist())),
                        'eni_source_subtypes': list(set(contact_data['eni_source_subtype'].tolist())),
                        'system_prompt_key': system_prompt_key,
                        'context_files': 'combined_all_eni_groups',
                        'record_count': len(contact_data),
                        'total_eni_ids': len(total_eni_ids)
                    }
                )
                
                if json_file:
                    result['files_created'].append(json_file)
                    if self.enhanced_logger:
                        self.enhanced_logger.log_file_creation(json_file, "structured_insight")
                
                # Sync to structured Airtable if configured
                if self.structured_airtable_writer:
                    try:
                        # Parse the insights to extract JSON (handle markdown code blocks)
                        structured_json = None
                        if insights:
                            import json
                            import re
                            
                            # Try to extract JSON from markdown code blocks
                            json_match = re.search(r'```json\s*(.*?)\s*```', insights, re.DOTALL)
                            if json_match:
                                try:
                                    structured_json = json.loads(json_match.group(1))
                                except json.JSONDecodeError:
                                    # If that fails, try to parse the whole thing as JSON
                                    try:
                                        structured_json = json.loads(insights)
                                    except json.JSONDecodeError:
                                        structured_json = {"raw_content": insights}
                            else:
                                # Try to parse the whole thing as JSON
                                try:
                                    structured_json = json.loads(insights)
                                except json.JSONDecodeError:
                                    structured_json = {"raw_content": insights}
                        
                        if structured_json:
                            airtable_result = self.structured_airtable_writer.create_note_submission_record(
                                contact_id=contact_id,
                                structured_json=structured_json
                            )
                            if airtable_result:
                                result['airtable_records'].append(airtable_result)
                                if self.enhanced_logger:
                                    self.enhanced_logger.log_airtable_sync(contact_id, True, "structured_insight")
                        else:
                            result['errors'].append("Failed to parse JSON from AI insights for Airtable sync")
                    except Exception as e:
                        result['errors'].append(f"Error in structured Airtable sync: {str(e)}")
                        if self.enhanced_logger:
                            self.enhanced_logger.log_airtable_sync(contact_id, False, "structured_insight")
                
                # Mark all ENI IDs as processed
                self.log_manager.mark_multiple_as_processed(contact_id, total_eni_ids)
                result['processed_eni_ids'].extend(total_eni_ids)
            
            logger.info(f"Successfully processed combined structured insight for contact {contact_id} with {len(total_eni_ids)} ENI IDs")
            
            # Enhanced logging for contact processing end
            if self.enhanced_logger:
                final_result = {
                    'success': len(result['errors']) == 0,
                    'processed_eni_ids': result['processed_eni_ids'],
                    'files_created': result['files_created'],
                    'airtable_records': result['airtable_records'],
                    'errors': result['errors']
                }
                self.enhanced_logger.log_contact_processing_end(contact_id, final_result)
            
            return result
            
        except Exception as e:
            error_msg = f"Error in combined structured insight processing: {str(e)}"
            result['errors'].append(error_msg)
            logger.error(error_msg)
            if self.enhanced_logger:
                self.enhanced_logger.log_contact_processing_end(contact_id, {'success': False, 'errors': [error_msg]})
            return result
    
    def process_multiple_contacts(
        self,
        contact_ids: List[str],
        system_prompt_key: str = "structured_insight",
        dry_run: bool = False,
        max_contacts: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Process multiple contacts.
        
        Args:
            contact_ids: List of specific contact IDs to process (if None, processes all)
            limit: Maximum number of contacts to process
            system_prompt_key: System prompt key to use
            dry_run: If True, don't save results or update logs
            
        Returns:
            Dict[str, Any]: Processing summary
        """
        summary = {
            'total_contacts': 0,
            'successful_contacts': 0,
            'failed_contacts': 0,
            'total_processed_eni_ids': 0,
            'total_files_created': 0,
            'total_airtable_records': 0,
            'contact_results': {},
            'errors': [],
            'start_time': datetime.now().isoformat(),
            'end_time': None
        }
        
        try:
            # Ensure BigQuery connection is established
            if not self.bigquery_connector.connect():
                summary['errors'].append("Failed to connect to BigQuery")
                summary['end_time'] = datetime.now().isoformat()
                return summary
            
            # Get contact IDs to process
            if contact_ids is None:
                contact_ids = self.bigquery_connector.get_unique_contact_ids(limit=limit)
            elif limit:
                contact_ids = contact_ids[:limit]
            
            summary['total_contacts'] = len(contact_ids)
            logger.info(f"Starting processing of {len(contact_ids)} contacts")
            
            # Process each contact
            for i, contact_id in enumerate(contact_ids, 1):
                try:
                    logger.info(f"Processing contact {i}/{len(contact_ids)}: {contact_id}")
                    
                    result = self.process_contact(
                        contact_id=contact_id,
                        system_prompt_key=system_prompt_key,
                        dry_run=dry_run
                    )
                    
                    summary['contact_results'][contact_id] = result
                    
                    if result['success']:
                        summary['successful_contacts'] += 1
                        summary['total_processed_eni_ids'] += len(result['processed_eni_ids'])
                        summary['total_files_created'] += len(result['files_created'])
                        summary['total_airtable_records'] += len(result['airtable_records'])
                    else:
                        summary['failed_contacts'] += 1
                        summary['errors'].extend(result['errors'])
                    
                    # Log progress every 10 contacts
                    if i % 10 == 0 or i == len(contact_ids):
                        logger.info(f"Progress: {i}/{len(contact_ids)} contacts processed")
                    
                except Exception as e:
                    error_msg = f"Unexpected error processing contact {contact_id}: {str(e)}"
                    summary['errors'].append(error_msg)
                    summary['failed_contacts'] += 1
                    logger.error(error_msg)
            
            summary['end_time'] = datetime.now().isoformat()
            
            # Generate final report
            logger.info(f"""
Processing Complete:
- Total Contacts: {summary['total_contacts']}
- Successful: {summary['successful_contacts']}
- Failed: {summary['failed_contacts']}
- Total ENI IDs Processed: {summary['total_processed_eni_ids']}
- Files Created: {summary['total_files_created']}
- Airtable Records: {summary['total_airtable_records']}
- Errors: {len(summary['errors'])}
""")
            
            return summary
            
        except Exception as e:
            summary['errors'].append(f"Unexpected error in batch processing: {str(e)}")
            summary['end_time'] = datetime.now().isoformat()
            logger.error(f"Error in batch processing: {str(e)}")
            return summary
    
    def get_processing_statistics(self) -> Dict[str, Any]:
        """
        Get processing statistics and system status.
        
        Returns:
            Dict[str, Any]: Statistics and status information
        """
        try:
            stats = {
                'log_statistics': self.log_manager.get_processing_stats(),
                'output_files': len(self.markdown_writer.list_summary_files()),
                'available_eni_types': self.config_loader.get_available_eni_types(),
                'available_prompts': list(self.config_loader.get_all_system_prompts().keys()),
                'system_status': self.validate_setup()
            }
            
            # Add BigQuery statistics if available
            if self.bigquery_connector and self.bigquery_connector.connect():
                try:
                    eni_types_df = self.bigquery_connector.get_eni_source_types_and_subtypes()
                    stats['bigquery_eni_types'] = len(eni_types_df)
                    stats['total_unique_contacts'] = len(self.bigquery_connector.get_unique_contact_ids())
                except Exception as e:
                    stats['bigquery_error'] = str(e)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting processing statistics: {str(e)}")
            return {'error': str(e)}
    
    def clear_processed_logs(self, contact_id: Optional[str] = None) -> bool:
        """
        Clear processed logs for a specific contact or all contacts.
        
        Args:
            contact_id: Specific contact ID to clear (if None, clears all)
            
        Returns:
            bool: True if successful
        """
        try:
            if contact_id:
                return self.log_manager.clear_contact_records(contact_id)
            else:
                return self.log_manager.clear_all_records()
        except Exception as e:
            logger.error(f"Error clearing processed logs: {str(e)}")
            return False


def main():
    """Main entry point for the processing pipeline."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Member Insights Processor")
    parser.add_argument("--config", default="config/config.yaml", help="Configuration file path")
    parser.add_argument("--filter", help="Processing filter file path (overrides default from config)")
    parser.add_argument("--contact-id", help="Process specific contact ID")
    parser.add_argument("--limit", type=int, help="Limit number of contacts to process")
    parser.add_argument("--system-prompt", default="structured_insight", help="System prompt key to use (only structured_insight supported)")
    parser.add_argument("--dry-run", action="store_true", help="Run without saving results")
    parser.add_argument("--validate", action="store_true", help="Only validate setup")
    parser.add_argument("--stats", action="store_true", help="Show processing statistics")
    parser.add_argument("--clear-logs", nargs='?', const='all', help="Clear processed logs (optionally specify contact ID, e.g., --clear-logs CNT-123456)")
    parser.add_argument("--airtable-test", action="store_true", help="Test Airtable connection")
    parser.add_argument("--airtable-batch-sync", action="store_true", help="Use enhanced batch sync to Airtable")
    parser.add_argument("--structured-airtable-test", action="store_true", help="Test structured insights Airtable connection")
    parser.add_argument("--structured-batch-sync", action="store_true", help="Sync existing JSON insights to structured Airtable")
    parser.add_argument("--show-filter", action="store_true", help="Show current processing filter configuration")
    
    args = parser.parse_args()
    
    try:
        # Initialize processor
        processor = MemberInsightsProcessor(args.config, args.filter)
        
        if args.validate:
            # Validate setup
            validation = processor.validate_setup()
            print("Setup Validation:")
            print(f"Valid: {validation['valid']}")
            if validation['issues']:
                print("Issues:")
                for issue in validation['issues']:
                    print(f"  - {issue}")
            if validation['warnings']:
                print("Warnings:")
                for warning in validation['warnings']:
                    print(f"  - {warning}")
            return
        
        if args.stats:
            # Show statistics
            stats = processor.get_processing_statistics()
            print("Processing Statistics:")
            for key, value in stats.items():
                print(f"{key}: {value}")
            return
        
        if args.clear_logs:
            # Clear logs
            contact_id = None if args.clear_logs == 'all' else args.clear_logs
            success = processor.clear_processed_logs(contact_id)
            if contact_id:
                print(f"Clear logs for {contact_id}: {'Success' if success else 'Failed'}")
            else:
                print(f"Clear all logs: {'Success' if success else 'Failed'}")
            return
        
        if args.show_filter:
            # Show processing filter configuration
            if processor.processing_filter:
                filter_summary = processor.processing_filter.get_filter_summary()
                print("Processing Filter Configuration:")
                print(f"  Filter: {filter_summary['filter_info'].get('name', 'Unknown')}")
                print(f"  Description: {filter_summary['filter_info'].get('description', 'No description')}")
                print(f"  ENI Types Configured: {filter_summary['total_eni_types']}")
                print("\nProcessing Rules:")
                for eni_type, rule_desc in filter_summary['processing_rules_summary'].items():
                    print(f"  {eni_type}: {rule_desc}")
                print(f"\nSettings: {filter_summary['settings']}")
            else:
                print("No processing filter configured")
            return
        
        if args.airtable_test:
            # Test Airtable connection
            print("Testing Airtable Connection:")
            airtable_info = processor.airtable_writer.get_table_info()
            for key, value in airtable_info.items():
                print(f"  {key}: {value}")
            return
        
        if args.structured_airtable_test:
            # Test structured insights Airtable connection
            print("Testing Structured Insights Airtable Connection:")
            if processor.structured_airtable_writer:
                connection_info = processor.structured_airtable_writer.test_connection()
                for key, value in connection_info.items():
                    print(f"  {key}: {value}")
            else:
                print("  Structured Airtable writer not initialized")
            return
        
        if args.structured_batch_sync:
            # Sync existing JSON insights to structured Airtable
            print("Syncing existing JSON insights to Structured Airtable:")
            if processor.structured_airtable_writer and processor.json_writer:
                insights_data = processor.json_writer.batch_extract_for_airtable()
                if insights_data:
                    sync_results = processor.structured_airtable_writer.sync_structured_insights_batch(
                        insights_data, show_progress=True
                    )
                    print(f"Sync Results:")
                    print(f"  Total records: {sync_results['total_records']}")
                    print(f"  Successful: {sync_results['successful']}")
                    print(f"  Failed: {sync_results['failed']}")
                    if sync_results['errors']:
                        print(f"  Errors: {len(sync_results['errors'])}")
                        for error in sync_results['errors'][:3]:  # Show first 3 errors
                            print(f"    - {error}")
                else:
                    print("  No JSON insights found to sync")
            else:
                print("  Structured Airtable writer or JSON writer not initialized")
            return
        
        # Process contacts
        if args.contact_id:
            # Process single contact
            result = processor.process_contact(
                contact_id=args.contact_id,
                system_prompt_key=args.system_prompt,
                dry_run=args.dry_run
            )
            print(f"Processing result for {args.contact_id}:")
            print(f"Success: {result['success']}")
            print(f"Processed ENI IDs: {len(result['processed_eni_ids'])}")
            print(f"Errors: {len(result['errors'])}")
        else:
            # Process multiple contacts
            result = processor.process_multiple_contacts(
                limit=args.limit,
                system_prompt_key=args.system_prompt,
                dry_run=args.dry_run
            )
            print("Batch processing completed:")
            print(f"Total contacts: {result['total_contacts']}")
            print(f"Successful: {result['successful_contacts']}")
            print(f"Failed: {result['failed_contacts']}")
            print(f"Total ENI IDs processed: {result['total_processed_eni_ids']}")
            
            # Enhanced Airtable batch sync if requested
            if args.airtable_batch_sync and processor.airtable_writer.connected:
                print("\nPerforming enhanced Airtable batch sync...")
                sync_result = processor.airtable_writer.sync_member_insights_from_processor_results(
                    result, show_progress=True
                )
                print(f"Airtable Sync Results:")
                print(f"  Total records: {sync_result.total_records}")
                print(f"  Successful: {sync_result.successful}")
                print(f"  Failed: {sync_result.failed}")
                print(f"  Processing time: {sync_result.processing_time:.2f} seconds")
                
                if sync_result.errors:
                    print(f"  Errors: {len(sync_result.errors)}")
                    for error in sync_result.errors[:3]:  # Show first 3 errors
                        print(f"    - {error}")
                
                # Export report
                report_path = processor.airtable_writer.export_sync_report(sync_result)
                print(f"  Report saved: {report_path}")
            elif args.airtable_batch_sync:
                print("\nAirtable batch sync requested but not connected to Airtable")
    
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        print(f"Error: {str(e)}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main()) 