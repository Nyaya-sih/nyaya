"""
Pydantic schemas for data validation and API responses.
"""
from datetime import date, datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class PrecedentCitation(BaseModel):
    """Schema for a cited precedent."""
    case_name: str = Field(..., description="Name of the cited case")
    citation: Optional[str] = Field(None, description="Legal citation (e.g., AIR 1950 SC 27)")
    year: Optional[int] = Field(None, ge=1947, le=2030, description="Year of the precedent")
    court: Optional[str] = Field(None, description="Court that decided the precedent")
    legal_principle: Optional[str] = Field(None, description="Key legal principle from the case")


class CaseMetadata(BaseModel):
    """
    Schema for extracted case metadata.
    This is the target structure for LLM extraction.
    """
    # Core identifiers
    case_id: Optional[str] = Field(None, description="Unique case identifier if present")
    case_title: Optional[str] = Field(None, description="Full case title")

    # Court information
    court: Optional[str] = Field(None, description="Court name")
    bench: Optional[List[str]] = Field(default_factory=list, description="Names of judges")
    date_of_judgment: Optional[date] = Field(None, description="Date of judgment")

    # Case classification
    case_type: Optional[str] = Field(None, description="Type of case (Criminal/Civil/Constitutional/etc.)")

    # Parties
    petitioner: Optional[List[str]] = Field(default_factory=list, description="Petitioner names")
    respondent: Optional[List[str]] = Field(default_factory=list, description="Respondent names")

    # Legal elements
    statutes_cited: Optional[List[str]] = Field(default_factory=list, description="Statutes/Acts referenced")
    sections_invoked: Optional[List[str]] = Field(default_factory=list, description="Specific sections invoked")
    charges: Optional[List[str]] = Field(default_factory=list, description="Criminal charges if applicable")

    # Outcome
    verdict: Optional[str] = Field(None, description="Verdict (Convicted/Acquitted/Dismissed/Allowed/etc.)")
    sentence: Optional[str] = Field(None, description="Sentence details if applicable")

    # Arguments and reasoning
    key_arguments_petitioner: Optional[str] = Field(None, description="Summary of petitioner arguments")
    key_arguments_respondent: Optional[str] = Field(None, description="Summary of respondent arguments")
    court_reasoning: Optional[str] = Field(None, description="Summary of court's reasoning")

    # Legal precedents
    precedents_cited: Optional[List[PrecedentCitation]] = Field(
        default_factory=list,
        description="Previous cases cited"
    )

    # Headnotes
    headnotes: Optional[List[str]] = Field(default_factory=list, description="Key legal principles")

    # Confidence scores
    confidence_scores: Dict[str, float] = Field(
        default_factory=dict,
        description="Confidence score (0.0-1.0) for each extracted field"
    )

    @field_validator("confidence_scores")
    @classmethod
    def validate_confidence_scores(cls, v: Dict[str, float]) -> Dict[str, float]:
        """Ensure confidence scores are between 0 and 1."""
        for field, score in v.items():
            if not 0.0 <= score <= 1.0:
                raise ValueError(f"Confidence score for {field} must be between 0.0 and 1.0, got {score}")
        return v

    def get_average_confidence(self) -> float:
        """Calculate average confidence score across all fields."""
        if not self.confidence_scores:
            return 0.0
        return sum(self.confidence_scores.values()) / len(self.confidence_scores)

    def get_low_confidence_fields(self, threshold: float = 0.7) -> List[str]:
        """Get list of fields with confidence below threshold."""
        return [
            field for field, score in self.confidence_scores.items()
            if score < threshold
        ]


class ValidationResult(BaseModel):
    """Schema for validation results."""
    is_valid: bool = Field(..., description="Whether the data passed validation")
    errors: List[str] = Field(default_factory=list, description="Validation errors")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    validation_date: datetime = Field(default_factory=datetime.utcnow)

    def has_errors(self) -> bool:
        """Check if there are any validation errors."""
        return len(self.errors) > 0

    def has_warnings(self) -> bool:
        """Check if there are any validation warnings."""
        return len(self.warnings) > 0


class ExtractionResult(BaseModel):
    """Schema for complete extraction result."""
    metadata: CaseMetadata = Field(..., description="Extracted case metadata")
    full_text: str = Field(..., description="Full text of the judgment")
    validation: ValidationResult = Field(..., description="Validation results")
    extraction_model: str = Field(..., description="Model used for extraction")
    extraction_time: float = Field(..., description="Time taken for extraction in seconds")
    source_file: str = Field(..., description="Path to source file")
    page_count: Optional[int] = Field(None, description="Number of pages in document")


class DownloadManifest(BaseModel):
    """Schema for tracking downloaded cases."""
    court_code: str
    year: int
    cases: List[Dict[str, Any]] = Field(default_factory=list)
    download_date: datetime = Field(default_factory=datetime.utcnow)
    total_cases: int = 0
    successful_downloads: int = 0
    failed_downloads: int = 0


class ProcessingStats(BaseModel):
    """Schema for processing statistics."""
    total_cases: int = 0
    successful_extractions: int = 0
    failed_extractions: int = 0
    average_confidence: float = 0.0
    extraction_errors: List[Dict[str, str]] = Field(default_factory=list)
    processing_time: float = 0.0
    estimated_cost: float = 0.0  # LLM API cost estimate
