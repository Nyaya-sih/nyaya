"""
SQLAlchemy database models for NyayaAI.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, Text, Date, DateTime, Float,
    ForeignKey, Table, Index, JSON
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


# Association table for many-to-many relationship between cases and statutes
case_statutes = Table(
    'case_statutes',
    Base.metadata,
    Column('case_id', Integer, ForeignKey('cases.id', ondelete='CASCADE'), primary_key=True),
    Column('statute_id', Integer, ForeignKey('statutes.id', ondelete='CASCADE'), primary_key=True),
    Column('created_at', DateTime, default=datetime.utcnow)
)


# Association table for many-to-many relationship between cases and precedents
case_precedents = Table(
    'case_precedents',
    Base.metadata,
    Column('case_id', Integer, ForeignKey('cases.id', ondelete='CASCADE'), primary_key=True),
    Column('precedent_id', Integer, ForeignKey('precedents.id', ondelete='CASCADE'), primary_key=True),
    Column('created_at', DateTime, default=datetime.utcnow)
)


class Case(Base):
    """Main case document model."""
    __tablename__ = "cases"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Core identifiers
    case_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True)
    case_title: Mapped[Optional[str]] = mapped_column(String(500), index=True)

    # Court information
    court: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    bench: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)
    date_of_judgment: Mapped[Optional[datetime]] = mapped_column(Date, index=True, nullable=True)

    # Case classification
    case_type: Mapped[Optional[str]] = mapped_column(String(100), index=True)

    # Parties involved
    petitioner: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)
    respondent: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)

    # Legal elements
    sections_invoked: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)
    charges: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)

    # Outcome
    verdict: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    sentence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Case content
    key_arguments_petitioner: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    key_arguments_respondent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    court_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    headnotes: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)
    full_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Extraction metadata
    confidence_scores: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    average_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    extraction_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    extraction_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Validation status
    validation_status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        index=True
    )  # "valid", "needs_review", "invalid", "pending"
    validation_errors: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)
    validation_warnings: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)

    # File metadata
    source_file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    source_file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    statutes: Mapped[list["CaseStatute"]] = relationship(
        "Statute",
        secondary=case_statutes,
        back_populates="cases"
    )
    precedents: Mapped[list["Precedent"]] = relationship(
        "Precedent",
        secondary=case_precedents,
        back_populates="cases"
    )

    # Indexes
    __table_args__ = (
        Index('idx_court_date', 'court', 'date_of_judgment'),
        Index('idx_case_type_verdict', 'case_type', 'verdict'),
        Index('idx_validation_status', 'validation_status'),
    )

    def __repr__(self) -> str:
        return f"<Case(id={self.id}, case_id='{self.case_id}', title='{self.case_title[:50]}...')>"


class Statute(Base):
    """Legal statute/act model."""
    __tablename__ = "statutes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Statute details
    statute_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    statute_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # "Act", "Code", "Constitution"
    year_enacted: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    cases: Mapped[list["Case"]] = relationship(
        "Case",
        secondary=case_statutes,
        back_populates="statutes"
    )

    def __repr__(self) -> str:
        return f"<Statute(id={self.id}, name='{self.statute_name}')>"


class Precedent(Base):
    """Previous case citation/precedent model."""
    __tablename__ = "precedents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Precedent details
    case_name: Mapped[str] = mapped_column(String(500), index=True)
    citation: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True)
    year: Mapped[Optional[int]] = mapped_column(Integer, index=True, nullable=True)
    court: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Legal principle
    legal_principle: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    cases: Mapped[list["Case"]] = relationship(
        "Case",
        secondary=case_precedents,
        back_populates="precedents"
    )

    def __repr__(self) -> str:
        return f"<Precedent(id={self.id}, case_name='{self.case_name}', citation='{self.citation}')>"
