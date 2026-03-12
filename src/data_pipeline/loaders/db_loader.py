"""
Database loader for saving extracted case data to PostgreSQL.
"""

from typing import List, Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError
from loguru import logger

from src.config.settings import settings
from src.database.models import Base, Case, Statute, Precedent
from src.database.schemas import CaseMetadata, ValidationResult, ExtractionResult


class DatabaseLoader:
    """
    Loads extracted case data into PostgreSQL database.
    """

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize database loader.

        Args:
            database_url: Database connection URL (uses settings if None)
        """
        self.database_url = database_url or settings.database_url
        self.engine = create_engine(self.database_url, echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)

        logger.info("Database loader initialized", database=self.database_url)

    def init_db(self) -> None:
        """
        Initialize database schema (create all tables).
        """
        logger.info("Initializing database schema")
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database schema created successfully")
        except Exception as e:
            logger.error(f"Failed to create database schema", error=str(e))
            raise

    def load_case(
        self,
        metadata: CaseMetadata,
        full_text: str,
        validation: ValidationResult,
        extraction_model: str,
        source_file: str,
        page_count: Optional[int] = None,
    ) -> Optional[int]:
        """
        Load a single case into the database.

        Args:
            metadata: Extracted case metadata
            full_text: Full judgment text
            validation: Validation results
            extraction_model: Model used for extraction
            source_file: Path to source PDF file
            page_count: Number of pages in document

        Returns:
            Case ID if successful, None otherwise
        """
        session = self.SessionLocal()

        try:
            # Determine validation status
            if not validation.is_valid:
                validation_status = "invalid"
            elif validation.has_warnings():
                validation_status = "needs_review"
            else:
                validation_status = "valid"

            # Create Case object
            case = Case(
                case_id=self._truncate(metadata.case_id, 255),
                case_title=self._truncate(metadata.case_title, 500),
                court=self._truncate(metadata.court, 255),
                bench=metadata.bench if metadata.bench else None,
                date_of_judgment=metadata.date_of_judgment,
                case_type=self._truncate(metadata.case_type, 100),
                petitioner=metadata.petitioner if metadata.petitioner else None,
                respondent=metadata.respondent if metadata.respondent else None,
                sections_invoked=metadata.sections_invoked
                if metadata.sections_invoked
                else None,
                charges=metadata.charges if metadata.charges else None,
                verdict=self._truncate(metadata.verdict, 100),
                sentence=metadata.sentence,
                key_arguments_petitioner=metadata.key_arguments_petitioner,
                key_arguments_respondent=metadata.key_arguments_respondent,
                court_reasoning=metadata.court_reasoning,
                headnotes=metadata.headnotes if metadata.headnotes else None,
                full_text=full_text,
                confidence_scores=metadata.confidence_scores,
                average_confidence=metadata.get_average_confidence(),
                extraction_model=self._truncate(extraction_model, 100),
                validation_status=validation_status,
                validation_errors=validation.errors if validation.errors else None,
                validation_warnings=validation.warnings
                if validation.warnings
                else None,
                source_file_path=self._truncate(source_file, 500),
                page_count=page_count,
            )

            # Add case to session
            session.add(case)
            session.flush()  # Get the case ID

            # Add statutes
            if metadata.statutes_cited:
                for statute_name in metadata.statutes_cited:
                    statute = self._get_or_create_statute(session, statute_name)
                    case.statutes.append(statute)

            # Add precedents
            if metadata.precedents_cited:
                for prec_data in metadata.precedents_cited:
                    try:
                        if hasattr(prec_data, "case_name"):
                            case_name = prec_data.case_name
                            citation = prec_data.citation
                            year = prec_data.year
                            court = prec_data.court
                            legal_principle = prec_data.legal_principle
                        elif isinstance(prec_data, dict):
                            case_name = prec_data.get("case_name")
                            citation = prec_data.get("citation")
                            year = prec_data.get("year")
                            court = prec_data.get("court")
                            legal_principle = prec_data.get("legal_principle")
                        elif isinstance(prec_data, str):
                            case_name = prec_data
                            citation = None
                            year = None
                            court = None
                            legal_principle = None
                        else:
                            logger.warning(
                                "Skipping unsupported precedent entry",
                                case_id=metadata.case_id,
                            )
                            continue

                        if not case_name:
                            logger.warning(
                                "Skipping precedent without case_name",
                                case_id=metadata.case_id,
                            )
                            continue

                        precedent = self._get_or_create_precedent(
                            session,
                            str(case_name),
                            citation,
                            year,
                            court,
                            legal_principle,
                        )
                        case.precedents.append(precedent)
                    except Exception as e:
                        logger.warning(
                            "Skipping invalid precedent entry",
                            case_id=metadata.case_id,
                            error=str(e),
                        )

            session.commit()

            logger.info(
                f"Case loaded successfully",
                case_id=metadata.case_id,
                db_id=case.id,
                validation_status=validation_status,
            )

            return case.id

        except IntegrityError as e:
            session.rollback()
            logger.warning(
                f"Case already exists or integrity error",
                case_id=metadata.case_id,
                error=str(e),
            )
            return None

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to load case", case_id=metadata.case_id, error=str(e))
            return None

        finally:
            session.close()

    @staticmethod
    def _truncate(value: Optional[str], max_len: int) -> Optional[str]:
        """Trim string fields to DB column length to avoid insertion failures."""
        if value is None:
            return None
        value = str(value)
        if len(value) <= max_len:
            return value
        return value[:max_len]

    def _get_or_create_statute(self, session: Session, statute_name: str) -> Statute:
        """
        Get existing statute or create new one.

        Args:
            session: Database session
            statute_name: Name of the statute

        Returns:
            Statute object
        """
        statute = session.query(Statute).filter_by(statute_name=statute_name).first()

        if not statute:
            statute = Statute(statute_name=statute_name)
            session.add(statute)
            session.flush()

        return statute

    def _get_or_create_precedent(
        self,
        session: Session,
        case_name: str,
        citation: Optional[str],
        year: Optional[int],
        court: Optional[str],
        legal_principle: Optional[str],
    ) -> Precedent:
        """
        Get existing precedent or create new one.

        Args:
            session: Database session
            case_name: Name of the case
            citation: Legal citation
            year: Year of the precedent
            court: Court that decided the precedent
            legal_principle: Key legal principle

        Returns:
            Precedent object
        """
        case_name = self._truncate(case_name, 500) or "Unknown Precedent"
        citation = self._truncate(citation.strip() if citation else None, 255)
        if citation == "":
            citation = None
        court = self._truncate(court, 255)

        # Try to find by citation first (most unique)
        if citation:
            precedent = session.query(Precedent).filter_by(citation=citation).first()
            if precedent:
                return precedent

        # Create new precedent
        precedent = Precedent(
            case_name=case_name,
            citation=citation,
            year=year,
            court=court,
            legal_principle=legal_principle,
        )
        session.add(precedent)
        session.flush()

        return precedent

    def load_batch(self, extraction_results: List[ExtractionResult]) -> dict:
        """
        Load multiple cases into the database.

        Args:
            extraction_results: List of ExtractionResult objects

        Returns:
            Dictionary with loading statistics
        """
        logger.info(f"Batch loading started", batch_size=len(extraction_results))

        stats = {
            "total": len(extraction_results),
            "successful": 0,
            "failed": 0,
            "duplicates": 0,
            "case_ids": [],
        }

        for result in extraction_results:
            case_id = self.load_case(
                metadata=result.metadata,
                full_text=result.full_text,
                validation=result.validation,
                extraction_model=result.extraction_model,
                source_file=result.source_file,
                page_count=result.page_count,
            )

            if case_id is not None:
                stats["successful"] += 1
                stats["case_ids"].append(case_id)
            elif case_id is None:
                stats["duplicates"] += 1
            else:
                stats["failed"] += 1

        logger.info(
            f"Batch loading complete",
            total=stats["total"],
            successful=stats["successful"],
            failed=stats["failed"],
            duplicates=stats["duplicates"],
        )

        return stats

    def get_case_by_id(self, case_id: str) -> Optional[Case]:
        """
        Retrieve a case by its case_id.

        Args:
            case_id: Case identifier

        Returns:
            Case object or None
        """
        session = self.SessionLocal()
        try:
            case = session.query(Case).filter_by(case_id=case_id).first()
            return case
        finally:
            session.close()

    def get_cases_by_validation_status(
        self, status: str, limit: int = 100
    ) -> List[Case]:
        """
        Get cases by validation status.

        Args:
            status: Validation status (valid/needs_review/invalid/pending)
            limit: Maximum number of cases to return

        Returns:
            List of Case objects
        """
        session = self.SessionLocal()
        try:
            cases = (
                session.query(Case)
                .filter_by(validation_status=status)
                .limit(limit)
                .all()
            )
            return cases
        finally:
            session.close()

    def get_database_stats(self) -> dict:
        """
        Get database statistics.

        Returns:
            Dictionary with statistics
        """
        session = self.SessionLocal()
        try:
            total_cases = session.query(Case).count()
            valid_cases = (
                session.query(Case).filter_by(validation_status="valid").count()
            )
            needs_review = (
                session.query(Case).filter_by(validation_status="needs_review").count()
            )
            invalid_cases = (
                session.query(Case).filter_by(validation_status="invalid").count()
            )
            total_statutes = session.query(Statute).count()
            total_precedents = session.query(Precedent).count()

            # Average confidence
            from sqlalchemy import func

            avg_conf = session.query(func.avg(Case.average_confidence)).scalar() or 0.0

            return {
                "total_cases": total_cases,
                "valid_cases": valid_cases,
                "needs_review": needs_review,
                "invalid_cases": invalid_cases,
                "total_statutes": total_statutes,
                "total_precedents": total_precedents,
                "average_confidence": float(avg_conf),
            }
        finally:
            session.close()
