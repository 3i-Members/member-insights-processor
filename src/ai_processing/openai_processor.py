"""
OpenAI Processor Module

This module handles AI processing using OpenAI's API, formatting member data, 
loading system prompts, and generating insights.
"""

import os
import logging
import time
import json
from typing import Dict, List, Optional, Any
import pandas as pd
from openai import OpenAI

logger = logging.getLogger(__name__)


class OpenAIProcessor:
    """Handles AI processing using OpenAI's API."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "o1-mini", generation_config: Optional[Dict] = None):
        """
        Initialize the OpenAI processor.
        
        Args:
            api_key: OpenAI API key (optional, will use environment variable if not provided)
            model_name: OpenAI model name to use
            generation_config: Generation configuration parameters
        """
        # Support both standard and alternate env var names
        self.api_key = api_key or os.getenv('OPENAI_API_KEY') or os.getenv('OPEN_AI_KEY')
        self.model_name = model_name
        self.generation_config = generation_config or {}
        self.client = None
        self._configure_openai()

    def _configure_openai(self) -> None:
        """Configure the OpenAI client."""
        try:
            if not self.api_key:
                raise ValueError("OpenAI API key not provided and OPENAI_API_KEY environment variable not set")
            
            self.client = OpenAI(api_key=self.api_key)
            
            logger.info(f"Successfully configured OpenAI model: {self.model_name}")
            if self.generation_config:
                logger.info(f"Generation config: {self.generation_config}")
            
        except Exception as e:
            logger.error(f"Failed to configure OpenAI: {str(e)}")
            self.client = None

    def _format_member_data(self, contact_data: pd.DataFrame) -> str:
        """
        Format member data for the AI prompt.
        
        Args:
            contact_data: DataFrame containing member data
            
        Returns:
            str: Formatted member data as JSON string
        """
        try:
            # Convert DataFrame to list of dictionaries
            records = []
            for _, row in contact_data.iterrows():
                record = {}
                for column in contact_data.columns:
                    value = row[column]
                    # Handle NaN and None values
                    if pd.isna(value) or value is None:
                        record[column] = None
                    else:
                        record[column] = str(value)
                records.append(record)
            
            # Convert to formatted JSON
            formatted_data = json.dumps(records, indent=2, ensure_ascii=False)
            return formatted_data
            
        except Exception as e:
            logger.error(f"Error formatting member data: {str(e)}")
            return "Error formatting member data"

    def _build_prompt(
        self,
        system_prompt: str,
        context_content: str,
        member_data: str,
        additional_context: Optional[str] = None
    ) -> str:
        """
        Build the complete prompt for OpenAI.
        
        Args:
            system_prompt: The system prompt content
            context_content: Context information about the data type
            member_data: Formatted member data
            additional_context: Optional additional context
            
        Returns:
            str: Complete formatted prompt
        """
        try:
            prompt_parts = [
                f"SYSTEM PROMPT:\n{system_prompt}",
                f"\nCONTEXT INFORMATION:\n{context_content}"
            ]
            
            if additional_context:
                prompt_parts.append(f"\nADDITIONAL CONTEXT:\n{additional_context}")
            
            prompt_parts.append(f"\nMEMBER DATA:\n{member_data}")
            prompt_parts.append("\nPlease provide comprehensive insights based on the above information.")
            
            return "\n\n".join(prompt_parts)
            
        except Exception as e:
            logger.error(f"Error building prompt: {str(e)}")
            return "Error building prompt"

    def generate_insights(
        self,
        system_prompt: str,
        context_content: str,
        member_data: pd.DataFrame,
        additional_context: Optional[str] = None,
        max_retries: int = 3
    ) -> Optional[str]:
        """
        Generate insights using OpenAI.
        
        Args:
            system_prompt: The system prompt content
            context_content: Context information about the data type
            member_data: DataFrame containing member data
            additional_context: Optional additional context
            max_retries: Maximum number of retry attempts
            
        Returns:
            Optional[str]: Generated insights or None if failed
        """
        if not self.client:
            logger.error("OpenAI client not configured")
            return None

        try:
            # Format member data
            formatted_data = self._format_member_data(member_data)
            
            # Build complete prompt
            full_prompt = self._build_prompt(
                system_prompt=system_prompt,
                context_content=context_content,
                member_data=formatted_data,
                additional_context=additional_context
            )

            # Generate insights with retries
            for attempt in range(max_retries):
                try:
                    logger.debug(f"Generating insights with OpenAI (attempt {attempt + 1})")
                    
                    # Prepare generation parameters
                    generation_params = {
                        'model': self.model_name,
                        'messages': [
                            {'role': 'user', 'content': full_prompt}
                        ]
                    }
                    
                    # Determine which token limit parameter to use per model family
                    model_lower = self.model_name.lower()
                    uses_completion_tokens = (
                        model_lower.startswith('o1') or
                        model_lower.startswith('gpt-5') or
                        model_lower.startswith('gpt-4.1') or
                        model_lower.startswith('gpt-4o')
                    )

                    # Map generation config into API params respecting model differences
                    if uses_completion_tokens:
                        # Newer models expect max_completion_tokens; avoid sending max_tokens
                        if 'max_tokens' in self.generation_config:
                            requested = self.generation_config['max_tokens']
                            # Cap to 128k completion tokens per current API guidance
                            generation_params['max_completion_tokens'] = min(int(requested), 128000)
                        # Do not send temperature/top_p/penalties for these model families
                    else:
                        # Legacy models accept max_tokens
                        for key, value in self.generation_config.items():
                            if key == 'max_tokens':
                                generation_params['max_tokens'] = value
                            elif key in ['temperature', 'top_p', 'presence_penalty', 'frequency_penalty']:
                                generation_params[key] = value

                    # Make API call
                    response = self.client.chat.completions.create(**generation_params)
                    
                    # Extract content
                    if response.choices and len(response.choices) > 0:
                        content = response.choices[0].message.content
                        if content:
                            logger.debug("Successfully generated insights with OpenAI")
                            return content.strip()
                    
                    logger.warning("OpenAI returned empty response")
                    return None
                    
                except Exception as e:
                    logger.warning(f"OpenAI generation failed (attempt {attempt + 1}): {str(e)}")
                    if attempt < max_retries - 1:
                        # Exponential backoff
                        delay = 2 ** attempt
                        logger.debug(f"Retrying in {delay} seconds...")
                        time.sleep(delay)
                    else:
                        logger.error("Failed to generate insights after all attempts")
                        return None

        except Exception as e:
            logger.error(f"Error in generate_insights: {str(e)}")
            return None

    def process_single_contact(
        self,
        contact_data: pd.DataFrame,
        system_prompt_key: str,
        context_content: str,
        config_loader,
        additional_context: Optional[str] = None
    ) -> Optional[str]:
        """
        Process a single contact's data with OpenAI.
        
        Args:
            contact_data: DataFrame containing the contact's data
            system_prompt_key: Key to identify which system prompt to use
            context_content: Context information about the data type
            config_loader: Configuration loader instance
            additional_context: Optional additional context
            
        Returns:
            Optional[str]: Generated insights or None if failed
        """
        try:
            # Load system prompt
            system_prompt_path = config_loader.get_system_prompt_path(system_prompt_key)
            if not system_prompt_path:
                logger.error(f"System prompt path not found for key: {system_prompt_key}")
                return None

            # Read system prompt file
            try:
                with open(system_prompt_path, 'r', encoding='utf-8') as f:
                    system_prompt = f.read().strip()
            except Exception as e:
                logger.error(f"Failed to read system prompt file {system_prompt_path}: {str(e)}")
                return None

            if not system_prompt:
                logger.error(f"System prompt is empty: {system_prompt_path}")
                return None

            # Generate insights
            insights = self.generate_insights(
                system_prompt=system_prompt,
                context_content=context_content,
                member_data=contact_data,
                additional_context=additional_context
            )

            return insights

        except Exception as e:
            logger.error(f"Error processing contact with OpenAI: {str(e)}")
            return None

    def test_connection(self) -> Dict[str, Any]:
        """
        Test the OpenAI connection.
        
        Returns:
            Dict[str, Any]: Connection test results
        """
        test_result = {
            'connected': False,
            'model': self.model_name,
            'api_key_present': bool(self.api_key),
            'client_configured': bool(self.client),
            'error': None
        }

        try:
            if not self.client:
                test_result['error'] = "OpenAI client not configured"
                return test_result

            # Test with a simple completion
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {'role': 'user', 'content': 'Hello, this is a test. Please respond with "Connection successful".'}
                ],
                max_tokens=10
            )

            if response.choices and len(response.choices) > 0:
                test_result['connected'] = True
                test_result['response'] = response.choices[0].message.content
            else:
                test_result['error'] = "No response from OpenAI"

        except Exception as e:
            test_result['error'] = str(e)
            logger.error(f"OpenAI connection test failed: {str(e)}")

        return test_result


def create_openai_processor(
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
) -> OpenAIProcessor:
    """
    Factory function to create an OpenAI processor instance.
    
    Args:
        api_key: OpenAI API key (optional)
        model_name: Model name to use (optional)
        config: Configuration dictionary (optional)
        
    Returns:
        OpenAIProcessor: Configured processor instance
    """
    if config:
        configured_model = model_name or config.get('model_name', 'o1-mini')
        generation_config = config.get('generation_config', {})
    else:
        configured_model = model_name or 'o1-mini'
        generation_config = {}
    
    return OpenAIProcessor(
        api_key=api_key,
        model_name=configured_model,
        generation_config=generation_config
    ) 