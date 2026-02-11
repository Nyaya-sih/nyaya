"""
Data validation module for extracted case metadata.
Validates against known legal references and business rules.
"""
from datetime import date
from typing import List, Set
from loguru import logger

from src.database.schemas import CaseMetadata, ValidationResult


class DataValidator:
    """
    Validates extracted case metadata for accuracy and completeness.
    """

    # Known Indian courts
    VALID_COURTS = {
        "Supreme Court of India",
        "Delhi High Court",
        "Bombay High Court",
        "Calcutta High Court",
        "Madras High Court",
        "Karnataka High Court",
        "Kerala High Court",
        "Gujarat High Court",
        "Rajasthan High Court",
        "Punjab and Haryana High Court",
        "Allahabad High Court",
        "Andhra Pradesh High Court",
        "Telangana High Court",
        "Madhya Pradesh High Court",
        "Chhattisgarh High Court",
        "Orissa High Court",
        "Patna High Court",
        "Jharkhand High Court",
        "Uttarakhand High Court",
        "Himachal Pradesh High Court",
        "Jammu and Kashmir High Court",
        "Gauhati High Court",
        "Meghalaya High Court",
        "Manipur High Court",
        "Tripura High Court",
        "Sikkim High Court",
    }

    # Common statute abbreviations
    KNOWN_STATUTES = {
        "IPC", "Indian Penal Code",
        "CrPC", "Code of Criminal Procedure",
        "CPC", "Code of Civil Procedure",
        "Evidence Act", "Indian Evidence Act",
        "BNS", "Bharatiya Nyaya Sanhita",
        "BNSS", "Bharatiya Nagarik Suraksha Sanhita",
        "BSA", "Bharatiya Sakshya Adhiniyam",
        "Constitution", "Constitution of India",
        "POCSO Act", "NDPS Act", "IT Act",
        "Companies Act", "Arbitration Act",
        "Consumer Protection Act", "RTI Act",
        "Income Tax Act", "GST Act",
    }

    # Valid case types
    VALID_CASE_TYPES = {
        "Criminal", "Civil", "Constitutional",
        "Family", "Labour", "Tax", "Commercial",
        "Arbitration", "Election", "Administrative",
        "Writ Petition", "Appeal", "Revision",
        "PIL", "Transfer Petition"
    }

    # Valid verdict types
    VALID_VERDICTS = {
        "Convicted", "Acquitted", "Dismissed", "Allowed",
        "Partly Allowed", "Remanded", "Settled", "Withdrawn",
        "Quashed", "Set Aside", "Upheld", "Modified"
    }

    def __init__(self):
        """Initialize validator."""
        logger.info("Data validator initialized")

    def validate(self, metadata: CaseMetadata) -> ValidationResult:
        """
        Validate case metadata.

        Args:
            metadata: Extracted case metadata

        Returns:
            ValidationResult with errors and warnings
        """
        logger.debug(f"Validating metadata", case_id=metadata.case_id)

        errors = []
        warnings = []

        # Validate required fields
        if not metadata.case_title:
            errors.append("Missing case_title")

        if not metadata.court:
            errors.append("Missing court name")

        # Validate date
        if metadata.date_of_judgment:
            date_errors = self._validate_date(metadata.date_of_judgment)
            errors.extend(date_errors)
        else:
            warnings.append("Missing date_of_judgment")

        # Validate court name
        if metadata.court:
            court_warnings = self._validate_court(metadata.court)
            warnings.extend(court_warnings)

        # Validate case type
        if metadata.case_type:
            case_type_warnings = self._validate_case_type(metadata.case_type)
            warnings.extend(case_type_warnings)
        else:
            warnings.append("Missing case_type")

        # Validate verdict
        if metadata.verdict:
            verdict_warnings = self._validate_verdict(metadata.verdict)
            warnings.extend(verdict_warnings)
        else:
            warnings.append("Missing verdict")

        # Validate statutes
        if metadata.statutes_cited:
            statute_warnings = self._validate_statutes(metadata.statutes_cited)
            warnings.extend(statute_warnings)
        else:
            warnings.append("No statutes cited")

        # Validate parties
        if not metadata.petitioner:
            warnings.append("No petitioner information")
        if not metadata.respondent:
            warnings.append("No respondent information")

        # Validate bench
        if not metadata.bench:
            warnings.append("No bench information")

        # Check confidence scores
        low_confidence_fields = metadata.get_low_confidence_fields(threshold=0.6)
        if low_confidence_fields:
            warnings.append(f"Low confidence fields: {', '.join(low_confidence_fields)}")

        # Check average confidence
        avg_confidence = metadata.get_average_confidence()
        if avg_confidence < 0.5:
            errors.append(f"Average confidence too low: {avg_confidence:.2f}")

        is_valid = len(errors) == 0

        result = ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings
        )

        logger.info(
            f"Validation complete",
            case_id=metadata.case_id,
            is_valid=is_valid,
            errors=len(errors),
            warnings=len(warnings)
        )

        return result

    def _validate_date(self, judgment_date: date) -> List[str]:
        """Validate judgment date."""
        errors = []

        # Check if date is in valid range (after Indian independence)
        if judgment_date.year < 1947:
            errors.append(f"Date before 1947: {judgment_date}")

        # Check if date is not in the future
        if judgment_date > date.today():
            errors.append(f"Date in the future: {judgment_date}")

        return errors

    def _validate_court(self, court: str) -> List[str]:
        """Validate court name."""
        warnings = []

        # Fuzzy match against known courts
        court_lower = court.lower()
        matched = False

        for valid_court in self.VALID_COURTS:
            if valid_court.lower() in court_lower or court_lower in valid_court.lower():
                matched = True
                break

        if not matched:
            warnings.append(f"Unknown court name: {court}")

        return warnings

    def _validate_case_type(self, case_type: str) -> List[str]:
        """Validate case type."""
        warnings = []

        case_type_lower = case_type.lower()
        matched = False

        for valid_type in self.VALID_CASE_TYPES:
            if valid_type.lower() in case_type_lower or case_type_lower in valid_type.lower():
                matched = True
                break

        if not matched:
            warnings.append(f"Unknown case type: {case_type}")

        return warnings

    def _validate_verdict(self, verdict: str) -> List[str]:
        """Validate verdict."""
        warnings = []

        verdict_lower = verdict.lower()
        matched = False

        for valid_verdict in self.VALID_VERDICTS:
            if valid_verdict.lower() in verdict_lower or verdict_lower in valid_verdict.lower():
                matched = True
                break

        if not matched:
            warnings.append(f"Unknown verdict type: {verdict}")

        return warnings

    def _validate_statutes(self, statutes: List[str]) -> List[str]:
        """Validate statute citations."""
        warnings = []

        for statute in statutes:
            statute_lower = statute.lower()
            matched = False

            for known_statute in self.KNOWN_STATUTES:
                if known_statute.lower() in statute_lower:
                    matched = True
                    break

            if not matched:
                warnings.append(f"Unknown statute: {statute}")

        return warnings

    def validate_batch(self, metadata_list: List[CaseMetadata]) -> List[ValidationResult]:
        """
        Validate multiple case metadata objects.

        Args:
            metadata_list: List of CaseMetadata objects

        Returns:
            List of ValidationResult objects
        """
        logger.info(f"Batch validation started", batch_size=len(metadata_list))

        results = [self.validate(metadata) for metadata in metadata_list]

        valid_count = sum(1 for r in results if r.is_valid)
        logger.info(
            f"Batch validation complete",
            total=len(results),
            valid=valid_count,
            invalid=len(results) - valid_count
        )

        return results

    def get_validation_summary(self, results: List[ValidationResult]) -> dict:
        """
        Get summary statistics from validation results.

        Args:
            results: List of ValidationResult objects

        Returns:
            Dictionary with summary statistics
        """
        total = len(results)
        valid = sum(1 for r in results if r.is_valid)
        with_warnings = sum(1 for r in results if r.has_warnings())

        # Collect all unique errors and warnings
        all_errors = set()
        all_warnings = set()
        for result in results:
            all_errors.update(result.errors)
            all_warnings.update(result.warnings)

        return {
            "total_cases": total,
            "valid_cases": valid,
            "invalid_cases": total - valid,
            "cases_with_warnings": with_warnings,
            "validation_rate": valid / total if total > 0 else 0,
            "unique_errors": list(all_errors),
            "unique_warnings": list(all_warnings),
            "error_count": len(all_errors),
            "warning_count": len(all_warnings)
        }
