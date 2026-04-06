"""Query parsing utilities for legal assistant."""

from dataclasses import dataclass
import re


@dataclass
class ParsedQuery:
    """Normalized query parse output."""

    normalized_question: str
    statutes_hint: list[str]
    sections_hint: list[str]


class QueryParser:
    """Lightweight deterministic parser for user legal questions."""

    _STATUTE_PATTERNS = {
        "IPC": re.compile(r"\bipc\b", re.IGNORECASE),
        "CrPC": re.compile(r"\bcrpc\b", re.IGNORECASE),
        "CPC": re.compile(r"\bcpc\b", re.IGNORECASE),
        "BNS": re.compile(r"\bbns\b", re.IGNORECASE),
        "BNSS": re.compile(r"\bbnss\b", re.IGNORECASE),
        "Evidence Act": re.compile(r"\bevidence\s+act\b", re.IGNORECASE),
        "Constitution": re.compile(r"\barticle\s+\d+\b", re.IGNORECASE),
    }
    _SECTION_PATTERN = re.compile(r"\b(section|sec\.)\s*\d+[a-zA-Z-]*\b", re.IGNORECASE)

    def parse(self, question: str) -> ParsedQuery:
        """Parse user question for lightweight legal hints."""
        normalized = " ".join(question.strip().split())
        statutes = [
            name
            for name, pattern in self._STATUTE_PATTERNS.items()
            if pattern.search(normalized)
        ]
        sections = [
            match.group(0) for match in self._SECTION_PATTERN.finditer(normalized)
        ]
        return ParsedQuery(
            normalized_question=normalized,
            statutes_hint=statutes,
            sections_hint=sections,
        )
