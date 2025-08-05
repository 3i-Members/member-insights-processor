"""
Gemini Pro Processor Module

This module handles AI processing using Google's Gemini Pro model
with system prompts and context information.
"""

import os
import json
import time
import pandas as pd
import google.generativeai as genai
from typing import Dict, List, Optional, Generator, Tuple, Any
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class GeminiProcessor:
    """Handles AI processing using Gemini Pro with system prompts and context."""
    
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash", generation_config: Optional[Dict] = None):
        """
        Initialize the Gemini processor.
        
        Args:
            api_key: Google AI API key (if None, will try to get from environment)
            model_name: Name of the Gemini model to use
            generation_config: Optional generation configuration parameters
        """
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        self.model_name = model_name
        self.generation_config = generation_config or {}
        self.model = None
        self._configure_gemini()
    
    def _configure_gemini(self) -> None:
        """Configure Gemini API with the provided API key."""
        try:
            if not self.api_key:
                raise ValueError("Gemini API key not provided and GEMINI_API_KEY environment variable not set")
            
            genai.configure(api_key=self.api_key)
            
            # Create generation config if provided
            gen_config = None
            if self.generation_config:
                gen_config = genai.GenerationConfig(**self.generation_config)
            
            self.model = genai.GenerativeModel(
                model_name=self.model_name,
                generation_config=gen_config
            )
            
            logger.info(f"Successfully configured Gemini model: {self.model_name}")
            if self.generation_config:
                logger.info(f"Generation config: {self.generation_config}")
            
        except Exception as e:
            logger.error(f"Failed to configure Gemini: {str(e)}")
            self.model = None
    
    def test_connection(self) -> bool:
        """
        Test the connection to Gemini API.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            if not self.model:
                return False
            
            # Try a simple generation to test the connection
            response = self.model.generate_content("Test connection")
            
            if response and response.text:
                logger.info("Gemini API connection test successful")
                return True
            else:
                logger.warning("Gemini API connection test failed: No response")
                return False
                
        except Exception as e:
            logger.error(f"Gemini API connection test failed: {str(e)}")
            return False
    
    def load_system_prompt(self, config_loader, prompt_key: str) -> Optional[str]:
        """
        Load a system prompt using the config loader.
        
        Args:
            config_loader: ConfigLoader instance
            prompt_key: System prompt key to load
            
        Returns:
            Optional[str]: System prompt content, or None if not found
        """
        try:
            prompt_path = config_loader.get_system_prompt_path(prompt_key)
            
            if not prompt_path:
                logger.error(f"No path configured for system prompt key: {prompt_key}")
                return None
            
            # Read the prompt file
            prompt_file = Path(prompt_path)
            if not prompt_file.exists():
                logger.error(f"System prompt file not found: {prompt_path}")
                return None
            
            with open(prompt_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            if not content:
                logger.warning(f"System prompt file is empty: {prompt_path}")
                return None
            
            logger.debug(f"Loaded system prompt '{prompt_key}' from {prompt_path}")
            return content
            
        except Exception as e:
            logger.error(f"Error loading system prompt '{prompt_key}': {str(e)}")
            return None
    
    def format_member_data(self, contact_data: pd.DataFrame) -> str:
        """
        Format member data from DataFrame into a readable string for AI processing.
        
        Args:
            contact_data: DataFrame containing member data
            
        Returns:
            str: Formatted member data string
        """
        try:
            if contact_data.empty:
                return "No member data provided."
            
            # Convert DataFrame to a more readable format
            formatted_data = []
            
            for _, row in contact_data.iterrows():
                record = {}
                for column in contact_data.columns:
                    value = row[column]
                    # Handle various data types
                    if pd.isna(value):
                        record[column] = "N/A"
                    elif isinstance(value, (int, float)):
                        record[column] = str(value)
                    else:
                        record[column] = str(value)
                
                formatted_data.append(record)
            
            # Convert to JSON for structured representation
            return json.dumps(formatted_data, indent=2, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"Error formatting member data: {str(e)}")
            return "Error formatting member data."
    
    def build_prompt(self, system_prompt: str, context_content: str, member_data: str) -> str:
        """
        Build the complete prompt for Gemini processing.
        
        Args:
            system_prompt: System prompt content
            context_content: Context information from markdown files
            member_data: Formatted member data
            
        Returns:
            str: Complete prompt for AI processing
        """
        try:
            prompt_template = """
{system_prompt}

Context Information:
{context_content}

Member Data:
{member_data}

Please provide a comprehensive summary and insights based on the system prompt, context, and member data provided above.
"""
            
            formatted_prompt = prompt_template.format(
                system_prompt=system_prompt,
                context_content=context_content,
                member_data=member_data
            )
            
            return formatted_prompt.strip()
            
        except Exception as e:
            logger.error(f"Error building prompt: {str(e)}")
            return "Error building prompt."
    
    def generate_insights(self, prompt: str, max_retries: int = 3) -> Optional[str]:
        """
        Generate insights using Gemini Pro.
        
        Args:
            prompt: Complete prompt for AI processing
            max_retries: Maximum number of retry attempts
            
        Returns:
            Optional[str]: Generated insights, or None if failed
        """
        if not self.model:
            logger.error("Gemini model not configured")
            return None
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"Generating insights (attempt {attempt + 1}/{max_retries})")
                
                # Generate content with Gemini
                response = self.model.generate_content(prompt)
                
                if response and response.text:
                    logger.info(f"Successfully generated insights ({len(response.text)} characters)")
                    return response.text.strip()
                else:
                    logger.warning(f"Empty response from Gemini (attempt {attempt + 1})")
                    
            except Exception as e:
                logger.warning(f"Gemini generation failed (attempt {attempt + 1}): {str(e)}")
                
                # If rate limited, wait before retrying
                if "rate limit" in str(e).lower() or "quota" in str(e).lower():
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.info(f"Rate limited, waiting {wait_time} seconds before retry")
                    time.sleep(wait_time)
                elif attempt == max_retries - 1:
                    logger.error(f"Failed to generate insights after {max_retries} attempts")
                    return None
                else:
                    time.sleep(1)  # Brief pause before retry
        
        return None
    
    def process_members(
        self,
        contact_data: pd.DataFrame,
        system_prompt_key: str,
        context_content: str,
        config_loader
    ) -> Generator[Tuple[str, Optional[str]], None, None]:
        """
        Process members with Gemini Pro using system prompts and context.
        
        Args:
            contact_data: DataFrame of contact data
            system_prompt_key: System prompt key to load
            context_content: Context content from markdown files
            config_loader: ConfigLoader instance
            
        Yields:
            Tuple[str, Optional[str]]: (contact_id, generated_content)
        """
        try:
            # Load system prompt
            system_prompt = self.load_system_prompt(config_loader, system_prompt_key)
            if not system_prompt:
                logger.error(f"Failed to load system prompt: {system_prompt_key}")
                return
            
            # Group data by contact_id
            if 'contact_id' not in contact_data.columns:
                logger.error("contact_id column not found in data")
                return
            
            unique_contacts = contact_data['contact_id'].unique()
            
            logger.info(f"Processing {len(unique_contacts)} unique contacts")
            
            for contact_id in unique_contacts:
                try:
                    # Filter data for this contact
                    contact_records = contact_data[contact_data['contact_id'] == contact_id]
                    
                    logger.debug(f"Processing contact {contact_id} ({len(contact_records)} records)")
                    
                    # Format member data
                    formatted_data = self.format_member_data(contact_records)
                    
                    # Build complete prompt
                    complete_prompt = self.build_prompt(
                        system_prompt=system_prompt,
                        context_content=context_content,
                        member_data=formatted_data
                    )
                    
                    # Generate insights
                    generated_content = self.generate_insights(complete_prompt)
                    
                    if generated_content:
                        logger.info(f"Successfully generated insights for contact {contact_id}")
                    else:
                        logger.warning(f"Failed to generate insights for contact {contact_id}")
                    
                    yield contact_id, generated_content
                    
                except Exception as e:
                    logger.error(f"Error processing contact {contact_id}: {str(e)}")
                    yield contact_id, None
                    
        except Exception as e:
            logger.error(f"Error in process_members: {str(e)}")
    
    def process_single_contact(
        self,
        contact_data: pd.DataFrame,
        system_prompt_key: str,
        context_content: str,
        config_loader
    ) -> Optional[str]:
        """
        Process a single contact's data and return insights.
        
        Args:
            contact_data: DataFrame containing data for one contact
            system_prompt_key: System prompt key to load
            context_content: Context content from markdown files
            config_loader: ConfigLoader instance
            
        Returns:
            Optional[str]: Generated insights, or None if failed
        """
        try:
            # Load system prompt
            system_prompt = self.load_system_prompt(config_loader, system_prompt_key)
            if not system_prompt:
                return None
            
            # Format member data
            formatted_data = self.format_member_data(contact_data)
            
            # Build complete prompt
            complete_prompt = self.build_prompt(
                system_prompt=system_prompt,
                context_content=context_content,
                member_data=formatted_data
            )
            
            # Generate insights
            return self.generate_insights(complete_prompt)
            
        except Exception as e:
            logger.error(f"Error processing single contact: {str(e)}")
            return None
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the configured model.
        
        Returns:
            Dict[str, Any]: Model information
        """
        try:
            info = {
                'model_name': self.model_name,
                'api_configured': bool(self.api_key),
                'model_initialized': bool(self.model),
                'connection_test': False
            }
            
            if self.model:
                info['connection_test'] = self.test_connection()
            
            return info
            
        except Exception as e:
            logger.error(f"Error getting model info: {str(e)}")
            return {
                'model_name': self.model_name,
                'api_configured': False,
                'model_initialized': False,
                'connection_test': False,
                'error': str(e)
            }


def create_gemini_processor(
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
) -> GeminiProcessor:
    """
    Factory function to create a GeminiProcessor instance.
    
    Args:
        api_key: Optional API key (will use environment variable if not provided)
        model_name: Name of the Gemini model to use (overrides config)
        config: Optional configuration dictionary from config loader
        
    Returns:
        GeminiProcessor: Configured processor instance
    """
    # Use config if provided, otherwise use defaults
    if config:
        configured_model = model_name or config.get('model_name', 'gemini-2.5-flash')
        generation_config = config.get('generation_config', {})
    else:
        configured_model = model_name or 'gemini-2.5-flash'
        generation_config = {}
    
    return GeminiProcessor(
        api_key=api_key,
        model_name=configured_model,
        generation_config=generation_config
    ) 