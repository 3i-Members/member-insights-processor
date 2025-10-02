"""
Anthropic Processor Module

This module handles AI processing using Anthropic's Claude API, formatting member data, 
loading system prompts, and generating insights.
"""

import os
import logging
import time
import json
from typing import Dict, List, Optional, Any
import pandas as pd
import anthropic

logger = logging.getLogger(__name__)


class AnthropicProcessor:
    """Handles AI processing using Anthropic's Claude API."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "claude-3-5-sonnet-20241022", generation_config: Optional[Dict] = None):
        """
        Initialize the Anthropic processor.
        
        Args:
            api_key: Anthropic API key (optional, will use environment variable if not provided)
            model_name: Claude model name to use
            generation_config: Generation configuration parameters
        """
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        self.model_name = model_name
        self.generation_config = generation_config or {}
        self.client = None
        self._configure_anthropic()

    def _configure_anthropic(self) -> None:
        """Configure the Anthropic client."""
        try:
            if not self.api_key:
                raise ValueError("Anthropic API key not provided and ANTHROPIC_API_KEY environment variable not set")
            
            self.client = anthropic.Anthropic(api_key=self.api_key)
            
            logger.info(f"Successfully configured Anthropic model: {self.model_name}")
            if self.generation_config:
                logger.info(f"Generation config: {self.generation_config}")
            
        except Exception as e:
            logger.error(f"Failed to configure Anthropic: {str(e)}")
            raise

    def format_contact_data(self, contact_data: pd.DataFrame) -> str:
        """
        Format contact data for AI processing.
        
        Args:
            contact_data: DataFrame containing contact information
            
        Returns:
            str: Formatted contact data string
        """
        if contact_data.empty:
            return "No contact data provided."
        
        formatted_sections = []
        
        # Group by ENI source type for better organization
        grouped = contact_data.groupby(['eni_source_type', 'eni_source_subtype'])
        
        for (source_type, source_subtype), group in grouped:
            section_header = f"=== {source_type.upper()}"
            if source_subtype and source_subtype != 'null':
                section_header += f" / {source_subtype.upper()}"
            section_header += " ==="
            
            formatted_sections.append(section_header)
            
            for _, row in group.iterrows():
                entry_parts = []
                
                # Add ENI ID and date info
                eni_id = row.get('eni_id', 'Unknown')
                logged_date = row.get('logged_date', 'Unknown')
                entry_parts.append(f"ENI ID: {eni_id}")
                entry_parts.append(f"Date: {logged_date}")
                
                # Add member info if available
                member_name = row.get('member_name')
                if member_name and pd.notna(member_name):
                    entry_parts.append(f"Member: {member_name}")
                
                # Add the main content
                eni_content = row.get('eni_content', 'No content available')
                if pd.notna(eni_content):
                    entry_parts.append(f"Content: {eni_content}")
                
                formatted_sections.append("\n".join(entry_parts))
                formatted_sections.append("")  # Empty line for separation
            
            formatted_sections.append("")  # Extra space between sections
        
        return "\n".join(formatted_sections)

    def process_single_contact(
        self,
        contact_data: pd.DataFrame,
        system_prompt_key: str,
        context_content: str,
        config_loader
    ) -> Optional[str]:
        """
        Process a single contact's data using Anthropic Claude.
        
        Args:
            contact_data: DataFrame containing contact information
            system_prompt_key: Key to identify which system prompt to use
            context_content: Additional context for the prompt
            config_loader: Configuration loader instance
            
        Returns:
            Optional[str]: Generated insights or None if processing failed
        """
        try:
            logger.debug("Generating insights with Anthropic Claude (attempt 1)")
            
            # Load system prompt
            system_prompt_path = config_loader.get_system_prompt_path(system_prompt_key)
            if not system_prompt_path or not os.path.exists(system_prompt_path):
                logger.error(f"System prompt file not found: {system_prompt_path}")
                return None
            
            with open(system_prompt_path, 'r', encoding='utf-8') as f:
                system_prompt = f.read().strip()
            
            # Format contact data
            formatted_data = self.format_contact_data(contact_data)
            
            # Build the complete prompt
            full_prompt = f"{system_prompt}\n\n"
            
            if context_content:
                full_prompt += f"=== CONTEXT ===\n{context_content}\n\n"
            
            full_prompt += f"=== MEMBER DATA ===\n{formatted_data}\n\n"
            full_prompt += "Please analyze the above data and provide insights following the specified format."
            
            # Prepare generation parameters
            generation_params = {
                "model": self.model_name,
                "max_tokens": self.generation_config.get('max_tokens', 8192),
                "temperature": self.generation_config.get('temperature', 0.7),
                "messages": [
                    {
                        "role": "user",
                        "content": full_prompt
                    }
                ]
            }
            
            # Add additional generation config if provided
            if 'top_p' in self.generation_config:
                generation_params['top_p'] = self.generation_config['top_p']
            
            # Make API call
            response = self.client.messages.create(**generation_params)
            
            if response.content and len(response.content) > 0:
                generated_text = response.content[0].text
                logger.debug("Successfully generated insights with Anthropic Claude")
                return generated_text
            else:
                logger.warning("Anthropic Claude returned empty response")
                return None
                
        except Exception as e:
            logger.error(f"Error generating insights with Anthropic Claude: {str(e)}")
            return None

    def process_multiple_contacts(
        self,
        contacts_data: List[pd.DataFrame],
        system_prompt_key: str,
        context_content: str,
        config_loader
    ) -> List[Optional[str]]:
        """
        Process multiple contacts' data.
        
        Args:
            contacts_data: List of DataFrames containing contact information
            system_prompt_key: Key to identify which system prompt to use
            context_content: Additional context for the prompt
            config_loader: Configuration loader instance
            
        Returns:
            List[Optional[str]]: List of generated insights (None for failed processing)
        """
        results = []
        
        for i, contact_data in enumerate(contacts_data):
            logger.info(f"Processing contact {i+1}/{len(contacts_data)} with Anthropic Claude")
            
            result = self.process_single_contact(
                contact_data=contact_data,
                system_prompt_key=system_prompt_key,
                context_content=context_content,
                config_loader=config_loader
            )
            
            results.append(result)
            
            # Rate limiting - small delay between requests
            if i < len(contacts_data) - 1:
                time.sleep(1)
        
        return results

    def test_connection(self) -> bool:
        """
        Test the Anthropic API connection.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Simple test message
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=10,
                messages=[
                    {
                        "role": "user",
                        "content": "Say 'Hello'"
                    }
                ]
            )
            
            if response.content and len(response.content) > 0:
                logger.info("Anthropic Claude API connection test successful")
                return True
            else:
                logger.error("Anthropic Claude API connection test failed: Empty response")
                return False
                
        except Exception as e:
            logger.error(f"Anthropic Claude API connection test failed: {str(e)}")
            return False

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the current model configuration.
        
        Returns:
            Dict[str, Any]: Model information
        """
        return {
            "provider": "anthropic",
            "model_name": self.model_name,
            "generation_config": self.generation_config,
            "api_configured": self.client is not None
        } 