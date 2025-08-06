"""
Schema definitions for Structured Insights.

This module defines the data models, validation schemas, and type guards
for the structured member insights stored in Supabase.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union, Tuple
from enum import Enum
import json
import re
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator
import logging

logger = logging.getLogger(__name__)


class ProcessingStatus(str, Enum):
    """Processing status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


class InsightMetadata(BaseModel):
    """Metadata for structured insights."""
    
    contact_id: str = Field(..., max_length=50, description="Primary contact identifier")
    eni_id: Optional[str] = Field(None, max_length=100, description="ENI identifier")
    member_name: Optional[str] = Field(None, max_length=255, description="Member display name")
    
    # ENI metadata
    eni_source_type: Optional[str] = Field(None, max_length=100, description="Primary ENI source type")
    eni_source_subtype: Optional[str] = Field(None, max_length=100, description="Primary ENI source subtype")
    eni_source_types: Optional[List[str]] = Field(None, description="All ENI source types for combined insights")
    eni_source_subtypes: Optional[List[str]] = Field(None, description="All ENI source subtypes for combined insights")
    
    # Processing metadata
    generator: str = Field(default="structured_insight", max_length=50, description="Generator identifier")
    system_prompt_key: Optional[str] = Field(None, max_length=100, description="System prompt used")
    context_files: Optional[str] = Field(None, description="Context files used")
    record_count: int = Field(default=1, ge=1, description="Number of source records processed")
    total_eni_ids: int = Field(default=1, ge=1, description="Total number of ENI IDs processed")
    
    # Timestamps
    generated_at: datetime = Field(default_factory=datetime.now, description="Original generation timestamp")
    
    # Status and versioning
    processing_status: ProcessingStatus = Field(default=ProcessingStatus.COMPLETED, description="Processing status")
    version: int = Field(default=1, ge=1, description="Version number")
    
    # Additional metadata
    additional_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata as JSON")


class StructuredInsightContent(BaseModel):
    """Core structured insight content sections."""
    
    personal: Optional[str] = Field(None, description="Personal information and interests")
    business: Optional[str] = Field(None, description="Business background and experience")
    investing: Optional[str] = Field(None, description="Investment experience and preferences")
    three_i: Optional[str] = Field(None, description="3i network activities and engagement", alias="3i")
    deals: Optional[str] = Field(None, description="Deal experience, interests, and avoidances")
    introductions: Optional[str] = Field(None, description="Introduction preferences and avoidances")
    
    class Config:
        populate_by_name = True
        extra = "allow"  # Allow additional fields for flexibility

    @field_validator('personal', 'business', 'investing', 'three_i', 'deals', 'introductions')
    @classmethod
    def validate_markdown_content(cls, v):
        """Validate that content is properly formatted markdown."""
        if v is not None and not isinstance(v, str):
            raise ValueError("Content must be a string")
        return v

    def extract_citations(self, content: str) -> List[Tuple[Optional[str], str]]:
        """Extract citation tuples from markdown content."""
        if not content:
            return []
        
        # Pattern to match citations like [2024-01-15,ENI-123456] or [N/A,ENI-123456]
        citation_pattern = r'\[([^,\]]+),([^\]]+)\]'
        matches = re.findall(citation_pattern, content)
        
        citations = []
        for date_str, eni_id in matches:
            date_val = None if date_str.strip() == 'N/A' else date_str.strip()
            citations.append((date_val, eni_id.strip()))
        
        return citations

    def validate_citations(self) -> Dict[str, List[str]]:
        """Validate that all content has proper citations."""
        validation_errors = []
        
        for field_name in ['personal', 'business', 'investing', 'three_i', 'deals', 'introductions']:
            content = getattr(self, field_name)
            if content:
                citations = self.extract_citations(content)
                if not citations:
                    validation_errors.append(f"Missing citations in {field_name}")
        
        return {"errors": validation_errors}


class StructuredInsight(BaseModel):
    """Complete structured insight record."""
    
    # Database fields
    id: Optional[UUID] = Field(None, description="Database primary key")
    created_at: Optional[datetime] = Field(None, description="Database creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Database update timestamp")
    
    # Core data
    metadata: InsightMetadata = Field(..., description="Insight metadata")
    insights: Union[StructuredInsightContent, Dict[str, Any]] = Field(..., description="Structured insight content")
    
    # Extracted fields for easier querying
    personal: Optional[str] = Field(None, description="Extracted personal section")
    business: Optional[str] = Field(None, description="Extracted business section")
    investing: Optional[str] = Field(None, description="Extracted investing section")
    three_i: Optional[str] = Field(None, description="Extracted 3i section")
    deals: Optional[str] = Field(None, description="Extracted deals section")
    introductions: Optional[str] = Field(None, description="Extracted introductions section")

    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }

    @model_validator(mode='after')
    def extract_insight_sections(self):
        """Extract insight sections from the insights field."""
        insights = self.insights
        
        if isinstance(insights, dict):
            # Extract each section
            self.personal = insights.get('personal')
            self.business = insights.get('business')
            self.investing = insights.get('investing')
            self.three_i = insights.get('3i') or insights.get('three_i')
            self.deals = insights.get('deals')
            self.introductions = insights.get('introductions')
        elif isinstance(insights, StructuredInsightContent):
            self.personal = insights.personal
            self.business = insights.business
            self.investing = insights.investing
            self.three_i = insights.three_i
            self.deals = insights.deals
            self.introductions = insights.introductions
        
        return self

    def to_db_dict(self) -> Dict[str, Any]:
        """Convert to dictionary suitable for database insertion."""
        data = {
            # Core identifiers
            'contact_id': self.metadata.contact_id,
            'eni_id': self.metadata.eni_id,
            'member_name': self.metadata.member_name,
            
            # ENI metadata
            'eni_source_type': self.metadata.eni_source_type,
            'eni_source_subtype': self.metadata.eni_source_subtype,
            'eni_source_types': self.metadata.eni_source_types,
            'eni_source_subtypes': self.metadata.eni_source_subtypes,
            
            # Processing metadata
            'generator': self.metadata.generator,
            'system_prompt_key': self.metadata.system_prompt_key,
            'context_files': self.metadata.context_files,
            'record_count': self.metadata.record_count,
            'total_eni_ids': self.metadata.total_eni_ids,
            
            # Content
            'insights': self.insights.dict() if isinstance(self.insights, StructuredInsightContent) else self.insights,
            
            # Extracted sections
            'personal': self.personal,
            'business': self.business,
            'investing': self.investing,
            'three_i': self.three_i,
            'deals': self.deals,
            'introductions': self.introductions,
            
            # Timestamps and status
            'generated_at': self.metadata.generated_at.isoformat() if isinstance(self.metadata.generated_at, datetime) else self.metadata.generated_at,
            'processing_status': self.metadata.processing_status.value,
            'version': self.metadata.version,
            'additional_metadata': self.metadata.additional_metadata,
        }
        
        # Remove None values
        return {k: v for k, v in data.items() if v is not None}

    @classmethod
    def from_db_dict(cls, data: Dict[str, Any]) -> 'StructuredInsight':
        """Create instance from database dictionary."""
        
        # Extract metadata
        metadata = InsightMetadata(
            contact_id=data['contact_id'],
            eni_id=data.get('eni_id'),
            member_name=data.get('member_name'),
            eni_source_type=data.get('eni_source_type'),
            eni_source_subtype=data.get('eni_source_subtype'),
            eni_source_types=data.get('eni_source_types'),
            eni_source_subtypes=data.get('eni_source_subtypes'),
            generator=data.get('generator', 'structured_insight'),
            system_prompt_key=data.get('system_prompt_key'),
            context_files=data.get('context_files'),
            record_count=data.get('record_count', 1),
            total_eni_ids=data.get('total_eni_ids', 1),
            generated_at=data.get('generated_at', datetime.now()),
            processing_status=ProcessingStatus(data.get('processing_status', 'completed')),
            version=data.get('version', 1),
            additional_metadata=data.get('additional_metadata'),
        )
        
        # Create insights content
        insights_data = data.get('insights', {})
        if isinstance(insights_data, dict):
            insights = StructuredInsightContent(**insights_data)
        else:
            insights = insights_data
        
        return cls(
            id=data.get('id'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at'),
            metadata=metadata,
            insights=insights,
        )


class LegacyInsightData(BaseModel):
    """Legacy insight data structure for backward compatibility."""
    
    metadata: Dict[str, Any] = Field(..., description="Legacy metadata structure")
    insights: Union[Dict[str, Any], str] = Field(..., description="Legacy insights content")
    
    def to_structured_insight(self) -> StructuredInsight:
        """Convert legacy data to new structured format."""
        
        # Extract metadata
        meta = self.metadata
        metadata = InsightMetadata(
            contact_id=meta.get('contact_id', ''),
            eni_id=meta.get('eni_id'),
            member_name=meta.get('member_name'),
            eni_source_type=meta.get('eni_source_type'),
            eni_source_subtype=meta.get('eni_source_subtype'),
            eni_source_types=meta.get('eni_source_types'),
            eni_source_subtypes=meta.get('eni_source_subtypes'),
            generator=meta.get('generator', 'structured_insight'),
            system_prompt_key=meta.get('system_prompt_key'),
            context_files=meta.get('context_files'),
            record_count=meta.get('record_count', 1),
            total_eni_ids=meta.get('total_eni_ids', 1),
            generated_at=datetime.fromisoformat(meta['generated_at']) if meta.get('generated_at') else datetime.now(),
        )
        
        # Handle insights content
        insights_content = self.insights
        if isinstance(insights_content, str):
            # Try to parse as JSON
            try:
                insights_content = json.loads(insights_content)
            except json.JSONDecodeError:
                insights_content = {"raw_content": insights_content}
        
        # Handle raw_content field from legacy format
        if isinstance(insights_content, dict) and 'raw_content' in insights_content:
            raw_content = insights_content['raw_content']
            # Try to extract JSON from markdown code blocks
            json_match = re.search(r'```json\s*(.*?)\s*```', raw_content, re.DOTALL)
            if json_match:
                try:
                    insights_content = json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    insights_content = {"error": "Could not parse legacy raw_content"}
        
        # Create structured content
        if isinstance(insights_content, dict):
            structured_content = StructuredInsightContent(**insights_content)
        else:
            structured_content = insights_content
        
        return StructuredInsight(
            metadata=metadata,
            insights=structured_content
        )


# Type guards and validation functions

def is_valid_contact_id(contact_id: str) -> bool:
    """Validate contact ID format."""
    if not contact_id or not isinstance(contact_id, str):
        return False
    # Typical format: CNT-xxxxxxxxx
    return bool(re.match(r'^CNT-[a-zA-Z0-9]{8,}$', contact_id))


def is_valid_eni_id(eni_id: str) -> bool:
    """Validate ENI ID format."""
    if not eni_id or not isinstance(eni_id, str):
        return False
    # Can be single ENI or combined format
    return bool(re.match(r'^(ENI-\d+|COMBINED-.+)$', eni_id))


def validate_structured_insight_json(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate structured insight JSON data.
    
    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []
    
    try:
        # Try to create a StructuredInsight instance
        if 'metadata' in data and 'insights' in data:
            # New format
            insight = StructuredInsight(**data)
        else:
            # Legacy format
            legacy = LegacyInsightData(**data)
            insight = legacy.to_structured_insight()
        
        # Additional validation
        content_validation = insight.insights.validate_citations() if isinstance(insight.insights, StructuredInsightContent) else {"errors": []}
        errors.extend(content_validation.get("errors", []))
        
    except Exception as e:
        errors.append(f"Schema validation failed: {str(e)}")
    
    return len(errors) == 0, errors


def normalize_insight_data(data: Dict[str, Any]) -> StructuredInsight:
    """
    Normalize insight data from various formats to StructuredInsight.
    
    Handles both legacy and new formats.
    """
    try:
        if 'metadata' in data and 'insights' in data:
            # New format
            return StructuredInsight(**data)
        else:
            # Legacy format
            legacy = LegacyInsightData(**data)
            return legacy.to_structured_insight()
    except Exception as e:
        logger.error(f"Failed to normalize insight data: {str(e)}")
        raise ValueError(f"Invalid insight data format: {str(e)}")


# Export all important classes and functions
__all__ = [
    'ProcessingStatus',
    'InsightMetadata',
    'StructuredInsightContent', 
    'StructuredInsight',
    'LegacyInsightData',
    'is_valid_contact_id',
    'is_valid_eni_id',
    'validate_structured_insight_json',
    'normalize_insight_data',
] 