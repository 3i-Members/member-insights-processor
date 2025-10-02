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

    # ENI metadata (arrays only - single values dropped)
    eni_source_types: Optional[List[str]] = Field(
        None, description="All ENI source types for combined insights"
    )
    eni_source_subtypes: Optional[List[str]] = Field(
        None, description="All ENI source subtypes for combined insights"
    )

    # Processing metadata
    generator: str = Field(
        default="structured_insight", max_length=50, description="Generator identifier"
    )
    system_prompt_key: Optional[str] = Field(None, max_length=100, description="System prompt used")
    context_files: Optional[str] = Field(None, description="Context files used")
    record_count: int = Field(default=1, ge=1, description="Number of source records processed")
    total_eni_ids: int = Field(default=1, ge=1, description="Total number of ENI IDs processed")

    # Timestamps
    generated_at: datetime = Field(
        default_factory=datetime.now, description="Original generation timestamp"
    )

    # Status and versioning
    processing_status: ProcessingStatus = Field(
        default=ProcessingStatus.COMPLETED, description="Processing status"
    )
    version: int = Field(default=1, ge=1, description="Version number")


class StructuredInsightContent(BaseModel):
    """Core structured insight content sections."""

    personal: Optional[str] = Field(None, description="Personal information and interests")
    business: Optional[str] = Field(None, description="Business background and experience")
    investing: Optional[str] = Field(None, description="Investment experience and preferences")
    three_i: Optional[str] = Field(
        None, description="3i network activities and engagement", alias="3i"
    )
    deals: Optional[str] = Field(None, description="Deal experience, interests, and avoidances")
    introductions: Optional[str] = Field(
        None, description="Introduction preferences and avoidances"
    )

    class Config:
        populate_by_name = True
        extra = "allow"  # Allow additional fields for flexibility

    @field_validator("personal", "business", "investing", "three_i", "deals", "introductions")
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
        citation_pattern = r"\[([^,\]]+),([^\]]+)\]"
        matches = re.findall(citation_pattern, content)

        citations = []
        for date_str, eni_id in matches:
            date_val = None if date_str.strip() == "N/A" else date_str.strip()
            citations.append((date_val, eni_id.strip()))

        return citations

    def validate_citations(self) -> Dict[str, List[str]]:
        """Validate that all content has proper citations."""
        validation_errors = []

        for field_name, content in [
            ("personal", self.personal),
            ("business", self.business),
            ("investing", self.investing),
            ("three_i", self.three_i),
            ("deals", self.deals),
            ("introductions", self.introductions),
        ]:
            if content and not self.extract_citations(content):
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
    insights: Union[StructuredInsightContent, Dict[str, Any]] = Field(
        ..., description="Structured insight content"
    )

    # Versioning
    is_latest: Optional[bool] = Field(
        None, description="Whether this is the latest version for contact_id + generator"
    )

    # Token/cost tracking (top-level)
    est_input_tokens: Optional[int] = Field(
        None, description="Sum of input tokens across accepted iterations for this contact"
    )
    est_insights_tokens: Optional[int] = Field(
        None, description="Estimated tokens of the latest consolidated insights"
    )
    generation_time_seconds: Optional[float] = Field(
        None, description="Sum of generation durations across accepted iterations for this contact"
    )

    class Config:
        use_enum_values = True
        json_encoders = {datetime: lambda v: v.isoformat(), UUID: lambda v: str(v)}

    def to_db_dict(self) -> Dict[str, Any]:
        """Convert to dictionary suitable for database insertion."""
        data = {
            # Core identifiers
            "contact_id": self.metadata.contact_id,
            "eni_id": self.metadata.eni_id,
            "member_name": self.metadata.member_name,
            # ENI metadata (arrays only)
            "eni_source_types": self.metadata.eni_source_types,
            "eni_source_subtypes": self.metadata.eni_source_subtypes,
            # Processing metadata
            "generator": self.metadata.generator,
            "system_prompt_key": self.metadata.system_prompt_key,
            "context_files": self.metadata.context_files,
            "record_count": self.metadata.record_count,
            "total_eni_ids": self.metadata.total_eni_ids,
            # Content (all insights stored in single JSONB column)
            "insights": (
                self.insights.dict()
                if isinstance(self.insights, StructuredInsightContent)
                else self.insights
            ),
            # Timestamps and status
            "generated_at": (
                self.metadata.generated_at.isoformat()
                if isinstance(self.metadata.generated_at, datetime)
                else self.metadata.generated_at
            ),
            "processing_status": self.metadata.processing_status.value,
            "version": self.metadata.version,
            # Versioning
            "is_latest": self.is_latest,
        }

        # Token/cost tracking: include only when present (not None)
        if self.est_input_tokens is not None:
            data["est_input_tokens"] = self.est_input_tokens
        if self.est_insights_tokens is not None:
            data["est_insights_tokens"] = self.est_insights_tokens
        if self.generation_time_seconds is not None:
            data["generation_time_seconds"] = self.generation_time_seconds

        # Remove None values to avoid SQL insert issues
        return {k: v for k, v in data.items() if v is not None}

    @classmethod
    def from_db_dict(cls, data: Dict[str, Any]) -> "StructuredInsight":
        """Create instance from database dictionary."""

        # Extract metadata
        metadata = InsightMetadata(
            contact_id=data["contact_id"],
            eni_id=data.get("eni_id"),
            member_name=data.get("member_name"),
            eni_source_types=data.get("eni_source_types"),
            eni_source_subtypes=data.get("eni_source_subtypes"),
            generator=data.get("generator", "structured_insight"),
            system_prompt_key=data.get("system_prompt_key"),
            context_files=data.get("context_files"),
            record_count=data.get("record_count", 1),
            total_eni_ids=data.get("total_eni_ids", 1),
            generated_at=data.get("generated_at", datetime.now()),
            processing_status=ProcessingStatus(data.get("processing_status", "completed")),
            version=data.get("version", 1),
        )

        # Create insights content
        insights_data = data.get("insights", {})
        if isinstance(insights_data, dict):
            insights = StructuredInsightContent(**insights_data)
        else:
            insights = insights_data

        return cls(
            id=data.get("id"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            metadata=metadata,
            insights=insights,
            # Versioning
            is_latest=data.get("is_latest"),
            # Map token/cost tracking if present
            est_input_tokens=data.get("est_input_tokens"),
            est_insights_tokens=data.get("est_insights_tokens"),
            generation_time_seconds=data.get("generation_time_seconds"),
        )


class LegacyInsightData(BaseModel):
    """Legacy insight data structure for backward compatibility."""

    contact_id: str
    content: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None

    def to_structured_insight(self) -> StructuredInsight:
        """Convert legacy data to current StructuredInsight format."""
        # Extract personal, business, etc. from content if available
        insights_content = StructuredInsightContent(
            personal=self.content.get("personal", ""),
            business=self.content.get("business", ""),
            investing=self.content.get("investing", ""),
            three_i=self.content.get("3i", ""),
            deals=self.content.get("deals", ""),
            introductions=self.content.get("introductions", ""),
        )

        # Create metadata
        metadata = InsightMetadata(
            contact_id=self.contact_id,
            eni_id=self.metadata.get("eni_id") if self.metadata else None,
            member_name=self.metadata.get("member_name") if self.metadata else None,
            generator=(
                self.metadata.get("generator", "legacy_import")
                if self.metadata
                else "legacy_import"
            ),
        )

        return StructuredInsight(metadata=metadata, insights=insights_content)


def normalize_insight_data(data: Dict[str, Any]) -> StructuredInsight:
    """
    Normalize insight data from various sources to StructuredInsight format.

    Args:
        data: Raw insight data dictionary

    Returns:
        StructuredInsight: Normalized StructuredInsight object
    """
    normalized = {}

    # Handle different contact_id field names
    contact_id = None
    for contact_field in ["contact_id", "contactId", "Contact_ID"]:
        if contact_field in data:
            contact_id = data[contact_field]
            break

    # Also check in metadata if not found at top level
    if not contact_id and "metadata" in data:
        metadata_dict = data["metadata"]
        for contact_field in ["contact_id", "contactId", "Contact_ID"]:
            if contact_field in metadata_dict:
                contact_id = metadata_dict[contact_field]
                break

    if not contact_id:
        raise ValueError("Missing contact_id in data")

    # Handle different insight content structures
    insights_content = {}
    if "insights" in data and isinstance(data["insights"], dict):
        insights_content = data["insights"]
    elif "content" in data and isinstance(data["content"], dict):
        insights_content = data["content"]
    else:
        # Try to extract from top-level fields
        for field in ["personal", "business", "investing", "3i", "deals", "introductions"]:
            if field in data:
                insights_content[field] = data[field]

    # Create structured insight content
    structured_content = StructuredInsightContent(**insights_content)

    # Create metadata
    metadata_dict = data.get("metadata", {})
    metadata = InsightMetadata(
        contact_id=contact_id,
        eni_id=data.get("eni_id") or metadata_dict.get("eni_id"),
        member_name=data.get("member_name") or metadata_dict.get("member_name"),
        eni_source_types=data.get("eni_source_types") or metadata_dict.get("eni_source_types"),
        eni_source_subtypes=data.get("eni_source_subtypes")
        or metadata_dict.get("eni_source_subtypes"),
        generator=data.get("generator") or metadata_dict.get("generator", "structured_insight"),
        system_prompt_key=data.get("system_prompt_key") or metadata_dict.get("system_prompt_key"),
        context_files=data.get("context_files") or metadata_dict.get("context_files"),
        record_count=data.get("record_count") or metadata_dict.get("record_count", 1),
        total_eni_ids=data.get("total_eni_ids") or metadata_dict.get("total_eni_ids", 1),
        generated_at=metadata_dict.get("generated_at", datetime.now()),
        processing_status=ProcessingStatus(metadata_dict.get("processing_status", "completed")),
        version=metadata_dict.get("version", 1),
    )

    return StructuredInsight(
        metadata=metadata,
        insights=structured_content,
        est_input_tokens=data.get("est_input_tokens"),
        est_insights_tokens=data.get("est_insights_tokens"),
        generation_time_seconds=data.get("generation_time_seconds"),
    )


def is_valid_contact_id(contact_id: str) -> bool:
    """
    Validate contact ID format.

    Args:
        contact_id: Contact identifier to validate

    Returns:
        bool: True if valid format
    """
    if not contact_id or not isinstance(contact_id, str):
        return False

    # Pattern: CNT- followed by at least 6 alphanumeric characters
    pattern = r"^CNT-[A-Za-z0-9]{6,}$"
    return bool(re.match(pattern, contact_id))


def create_insight_from_ai_response(
    contact_id: str, ai_response: str, metadata: Optional[Dict[str, Any]] = None
) -> StructuredInsight:
    """
    Create a StructuredInsight from AI response text.

    Args:
        contact_id: Contact identifier
        ai_response: AI-generated insight text
        metadata: Optional metadata dictionary

    Returns:
        StructuredInsight: Parsed and validated insight
    """
    # Try to parse JSON from AI response
    insights_data = {}

    # Try to extract JSON from markdown code blocks
    json_match = re.search(r"```json\s*(.*?)\s*```", ai_response, re.DOTALL)
    if json_match:
        try:
            insights_data = json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # If no JSON block found, try to parse entire response as JSON
    if not insights_data:
        try:
            insights_data = json.loads(ai_response)
        except json.JSONDecodeError:
            # Fallback: create basic structure with raw content
            insights_data = {
                "personal": "",
                "business": "",
                "investing": "",
                "3i": "",
                "deals": "",
                "introductions": "",
                "raw_content": ai_response,
            }

    # Create insight content
    insights_content = StructuredInsightContent(**insights_data)

    # Create metadata
    insight_metadata = InsightMetadata(contact_id=contact_id, **(metadata or {}))

    return StructuredInsight(metadata=insight_metadata, insights=insights_content)
