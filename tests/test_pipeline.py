"""
Unit tests for NyayaAI data pipeline.
"""
import pytest
from pathlib import Path
from datetime import date

from src.config.settings import settings
from src.database.schemas import CaseMetadata, PrecedentCitation, ValidationResult
from src.data_pipeline.validators.data_validator import DataValidator
from src.data_pipeline.extractors.pdf_extractor import PDFExtractor


class TestSettings:
    """Test configuration settings."""

    def test_settings_load(self):
        """Test that settings load correctly."""
        assert settings is not None
        assert settings.s3_bucket_name == "indian-high-court-judgments"
        assert settings.extraction_temperature >= 0.0
        assert settings.extraction_temperature <= 2.0

    def test_llm_key_check(self):
        """Test LLM key availability check."""
        # This will pass if at least one key is configured
        # Or fail gracefully if no keys are configured
        result = settings.has_llm_key()
        assert isinstance(result, bool)


class TestDataValidator:
    """Test data validation logic."""

    def test_validator_init(self):
        """Test validator initialization."""
        validator = DataValidator()
        assert validator is not None

    def test_validate_date(self):
        """Test date validation."""
        validator = DataValidator()

        # Valid date
        valid_date = date(2024, 1, 15)
        errors = validator._validate_date(valid_date)
        assert len(errors) == 0

        # Date before independence
        old_date = date(1900, 1, 1)
        errors = validator._validate_date(old_date)
        assert len(errors) > 0
        assert "before 1947" in errors[0].lower()

        # Future date
        future_date = date(2030, 1, 1)
        errors = validator._validate_date(future_date)
        assert len(errors) > 0

    def test_validate_court(self):
        """Test court name validation."""
        validator = DataValidator()

        # Valid court
        warnings = validator._validate_court("Supreme Court of India")
        assert len(warnings) == 0

        # Valid high court
        warnings = validator._validate_court("Delhi High Court")
        assert len(warnings) == 0

        # Unknown court
        warnings = validator._validate_court("XYZ Court")
        assert len(warnings) > 0

    def test_validate_verdict(self):
        """Test verdict validation."""
        validator = DataValidator()

        # Valid verdicts
        for verdict in ["Convicted", "Acquitted", "Dismissed", "Allowed"]:
            warnings = validator._validate_verdict(verdict)
            assert len(warnings) == 0

        # Unknown verdict
        warnings = validator._validate_verdict("Random Verdict")
        assert len(warnings) > 0

    def test_validate_complete_metadata(self):
        """Test validation of complete metadata."""
        validator = DataValidator()

        # Create valid metadata
        metadata = CaseMetadata(
            case_id="TEST-001",
            case_title="Test Case v. Example",
            court="Supreme Court of India",
            bench=["Justice A", "Justice B"],
            date_of_judgment=date(2024, 1, 15),
            case_type="Criminal",
            petitioner=["State"],
            respondent=["Accused"],
            statutes_cited=["IPC", "CrPC"],
            sections_invoked=["IPC Section 302"],
            verdict="Convicted",
            confidence_scores={
                "case_title": 0.95,
                "court": 0.98,
                "verdict": 0.92
            }
        )

        result = validator.validate(metadata)
        assert isinstance(result, ValidationResult)
        assert result.is_valid or result.has_warnings()  # Should be valid or have minor warnings

    def test_validate_incomplete_metadata(self):
        """Test validation of incomplete metadata."""
        validator = DataValidator()

        # Create incomplete metadata
        metadata = CaseMetadata(
            case_id="TEST-002",
            confidence_scores={"case_id": 0.5}
        )

        result = validator.validate(metadata)
        assert isinstance(result, ValidationResult)
        assert not result.is_valid or result.has_warnings()
        assert len(result.errors) > 0 or len(result.warnings) > 0


class TestPDFExtractor:
    """Test PDF extraction."""

    def test_extractor_init(self):
        """Test PDF extractor initialization."""
        extractor = PDFExtractor()
        assert extractor is not None

    def test_clean_text(self):
        """Test text cleaning."""
        extractor = PDFExtractor()

        # Test with messy text
        messy_text = "Hello    World\n\n\n\nNew   paragraph\r\nAnother line"
        clean_text = extractor._clean_text(messy_text)

        assert "  " not in clean_text  # No double spaces
        assert "\n\n\n" not in clean_text  # Max double newlines
        assert clean_text.strip() == clean_text  # No leading/trailing whitespace


class TestCaseMetadata:
    """Test CaseMetadata schema."""

    def test_metadata_creation(self):
        """Test creating metadata object."""
        metadata = CaseMetadata(
            case_id="TEST-001",
            case_title="Test Case",
            confidence_scores={"case_id": 0.9}
        )

        assert metadata.case_id == "TEST-001"
        assert metadata.case_title == "Test Case"

    def test_confidence_validation(self):
        """Test confidence score validation."""
        # Valid confidence
        metadata = CaseMetadata(
            confidence_scores={"field1": 0.5, "field2": 1.0, "field3": 0.0}
        )
        assert metadata.confidence_scores is not None

        # Invalid confidence (should raise error)
        with pytest.raises(ValueError):
            CaseMetadata(
                confidence_scores={"field1": 1.5}  # > 1.0
            )

    def test_average_confidence(self):
        """Test average confidence calculation."""
        metadata = CaseMetadata(
            confidence_scores={"field1": 0.8, "field2": 0.6, "field3": 1.0}
        )

        avg = metadata.get_average_confidence()
        assert avg == pytest.approx((0.8 + 0.6 + 1.0) / 3)

    def test_low_confidence_fields(self):
        """Test identifying low confidence fields."""
        metadata = CaseMetadata(
            confidence_scores={
                "high_conf": 0.9,
                "medium_conf": 0.75,
                "low_conf": 0.5
            }
        )

        low_fields = metadata.get_low_confidence_fields(threshold=0.7)
        assert "low_conf" in low_fields
        assert "high_conf" not in low_fields


class TestPrecedentCitation:
    """Test PrecedentCitation schema."""

    def test_precedent_creation(self):
        """Test creating precedent citation."""
        precedent = PrecedentCitation(
            case_name="Landmark Case v. State",
            citation="AIR 1950 SC 27",
            year=1950,
            court="Supreme Court of India"
        )

        assert precedent.case_name == "Landmark Case v. State"
        assert precedent.year == 1950


class TestValidationResult:
    """Test ValidationResult schema."""

    def test_validation_result_creation(self):
        """Test creating validation result."""
        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=["Minor warning"]
        )

        assert result.is_valid
        assert not result.has_errors()
        assert result.has_warnings()

    def test_validation_with_errors(self):
        """Test validation result with errors."""
        result = ValidationResult(
            is_valid=False,
            errors=["Critical error"],
            warnings=[]
        )

        assert not result.is_valid
        assert result.has_errors()
        assert not result.has_warnings()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
