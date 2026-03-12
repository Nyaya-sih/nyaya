"""
Multi-level case embedding generator for NyayaAI.

Strategy: Generate THREE separate embeddings per case and combine them:
1. Factual embedding - what happened in the case
2. Legal embedding - what laws were applied
3. Outcome embedding - what the result was

Combined: weighted average (factual: 0.4, legal: 0.4, outcome: 0.2)
"""

from dataclasses import dataclass
from typing import Optional, Any, Iterable
import re

import numpy as np
from loguru import logger
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
import tiktoken


@dataclass
class CaseEmbedding:
    """Container for multi-level case embeddings."""

    case_id: int
    factual_embedding: np.ndarray
    legal_embedding: np.ndarray
    outcome_embedding: np.ndarray
    combined_embedding: np.ndarray
    token_count: int


class EmbeddingGenerator:
    """Generate multi-level embeddings for cases and queries."""

    EMBEDDING_MODEL = "text-embedding-3-large"
    EMBEDDING_DIM = 3072
    ENCODING = "cl100k_base"
    WEIGHTS = {"factual": 0.4, "legal": 0.4, "outcome": 0.2}
    FULLTEXT_TOKEN_BUDGET = 6000

    def __init__(self, client: OpenAI) -> None:
        """Initialize the embedding generator.

        Args:
            client: OpenAI client instance.
        """
        self.client = client
        self.encoder = tiktoken.get_encoding(self.ENCODING)
        self.total_tokens_used = 0
        self.total_api_calls = 0

    def build_factual_text(self, case: Any) -> str:
        """Build text focused on facts of the case.

        Fields: case_title, petitioner, respondent, charges,
                key_arguments_petitioner, key_arguments_respondent
        Truncate to 2000 tokens.

        Args:
            case: SQLAlchemy Case instance.

        Returns:
            Factual text string.
        """
        parts = []

        case_title = getattr(case, "case_title", None)
        if case_title:
            parts.append(f"Case Title: {case_title}")

        petitioner = self._join_list(getattr(case, "petitioner", None))
        if petitioner:
            parts.append(f"Petitioner: {petitioner}")

        respondent = self._join_list(getattr(case, "respondent", None))
        if respondent:
            parts.append(f"Respondent: {respondent}")

        charges = self._join_list(getattr(case, "charges", None))
        if charges:
            parts.append(f"Charges: {charges}")

        key_args_pet = getattr(case, "key_arguments_petitioner", None)
        if key_args_pet:
            parts.append(f"Petitioner Arguments: {key_args_pet}")

        key_args_resp = getattr(case, "key_arguments_respondent", None)
        if key_args_resp:
            parts.append(f"Respondent Arguments: {key_args_resp}")

        text = "\n".join(parts)
        return self._truncate_to_tokens(text, 2000)

    def build_legal_text(self, case: Any) -> str:
        """Build text focused on legal aspects.

        Fields: court, statutes_cited, sections_invoked,
                court_reasoning, precedents_cited
        Truncate to 2000 tokens.

        Args:
            case: SQLAlchemy Case instance.

        Returns:
            Legal text string.
        """
        parts = []

        court = getattr(case, "court", None)
        if court:
            parts.append(f"Court: {court}")

        statutes = self._join_list(self._get_statute_names(case))
        if statutes:
            parts.append(f"Statutes Cited: {statutes}")

        sections = self._join_list(getattr(case, "sections_invoked", None))
        if sections:
            parts.append(f"Sections Invoked: {sections}")

        reasoning = getattr(case, "court_reasoning", None)
        if reasoning:
            parts.append(f"Court Reasoning: {reasoning}")

        precedents_text = self._format_precedents(getattr(case, "precedents", None))
        if precedents_text:
            parts.append(f"Precedents Cited: {precedents_text}")

        text = "\n".join(parts)
        return self._truncate_to_tokens(text, 2000)

    def build_outcome_text(self, case: Any) -> str:
        """Build text focused on case outcome.

        Fields: case_type, verdict, sentence, headnotes, year
        Truncate to 500 tokens.

        Args:
            case: SQLAlchemy Case instance.

        Returns:
            Outcome text string.
        """
        parts = []

        case_type = getattr(case, "case_type", None)
        if case_type:
            parts.append(f"Case Type: {case_type}")

        verdict = getattr(case, "verdict", None)
        if verdict:
            parts.append(f"Verdict: {verdict}")

        sentence = getattr(case, "sentence", None)
        if sentence:
            parts.append(f"Sentence: {sentence}")

        headnotes = self._join_list(getattr(case, "headnotes", None))
        if headnotes:
            parts.append(f"Headnotes: {headnotes}")

        date_of_judgment = getattr(case, "date_of_judgment", None)
        if date_of_judgment:
            parts.append(f"Year: {date_of_judgment.year}")

        text = "\n".join(parts)
        return self._truncate_to_tokens(text, 500)

    def build_fulltext_text(self, case: Any) -> str:
        """Build full-text-lite input for embedding.

        Prefer full_text; fall back to key fields if missing.
        Strip boilerplate headers and truncate to token budget.

        Args:
            case: SQLAlchemy Case instance.

        Returns:
            Full-text-lite string.
        """
        full_text = getattr(case, "full_text", None) or ""
        if not full_text:
            parts = [
                getattr(case, "case_title", "") or "",
                getattr(case, "court", "") or "",
                getattr(case, "key_arguments_petitioner", "") or "",
                getattr(case, "key_arguments_respondent", "") or "",
                getattr(case, "court_reasoning", "") or "",
            ]
            full_text = "\n".join([part for part in parts if part])

        cleaned = self._strip_boilerplate(full_text)
        return self._truncate_to_tokens(cleaned, self.FULLTEXT_TOKEN_BUDGET)

    def generate_fulltext_embedding(self, case: Any) -> np.ndarray:
        """Generate normalized full-text-lite embedding for a case."""
        text = self.build_fulltext_text(case)
        embedding = self._normalize(self._get_embedding(text))
        return embedding

    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text to max_tokens using tiktoken.

        Args:
            text: Input text.
            max_tokens: Maximum token count.

        Returns:
            Truncated text string.
        """
        if not text:
            return ""
        tokens = self.encoder.encode(text)
        if len(tokens) <= max_tokens:
            return text
        return self.encoder.decode(tokens[:max_tokens])

    def _strip_boilerplate(self, text: str) -> str:
        """Remove common header boilerplate from judgment text."""
        if not text:
            return ""
        lines = [line.strip() for line in text.replace("\r", "\n").split("\n") if line.strip()]
        if not lines:
            return text

        header_regex = re.compile(
            r"^(in the|before|coram|dated|date|court|judg(e)?ment|order|oral|appearance|through|present|cause title|case no|cs no|crl|wp|owp|cwp|ia no|oa no|petitioner|respondent|appellant|versus|vs\.?|v\.)",
            re.IGNORECASE,
        )
        content_lines = []
        for idx, line in enumerate(lines):
            if idx < 25 and (header_regex.match(line) or (line.isupper() and len(line) < 120)):
                continue
            content_lines.append(line)

        if content_lines:
            return "\n".join(content_lines)
        return "\n".join(lines)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _get_embedding(self, text: str) -> np.ndarray:
        """Get embedding from OpenAI with retry logic.

        Return zero vector for empty text.
        Track total_tokens_used and total_api_calls.

        Args:
            text: Input text.

        Returns:
            Embedding vector.
        """
        if not text.strip():
            logger.warning("Empty text provided to embedding generator")
            return np.zeros(self.EMBEDDING_DIM, dtype=np.float32)

        token_count = len(self.encoder.encode(text))
        self.total_tokens_used += token_count
        self.total_api_calls += 1

        response = self.client.embeddings.create(
            model=self.EMBEDDING_MODEL,
            input=text
        )
        embedding = np.array(response.data[0].embedding, dtype=np.float32)
        return embedding

    def generate_case_embedding(self, case: Any) -> CaseEmbedding:
        """Generate complete multi-level embedding for a case.

        Makes 3 API calls (factual, legal, outcome).
        Returns weighted normalized combined embedding.

        Args:
            case: SQLAlchemy Case instance.

        Returns:
            CaseEmbedding instance.
        """
        factual_text = self.build_factual_text(case)
        legal_text = self.build_legal_text(case)
        outcome_text = self.build_outcome_text(case)

        factual_embedding = self._normalize(self._get_embedding(factual_text))
        legal_embedding = self._normalize(self._get_embedding(legal_text))
        outcome_embedding = self._normalize(self._get_embedding(outcome_text))

        combined = (
            self.WEIGHTS["factual"] * factual_embedding
            + self.WEIGHTS["legal"] * legal_embedding
            + self.WEIGHTS["outcome"] * outcome_embedding
        )
        combined_embedding = self._normalize(combined)

        token_count = (
            len(self.encoder.encode(factual_text))
            + len(self.encoder.encode(legal_text))
            + len(self.encoder.encode(outcome_text))
        )

        return CaseEmbedding(
            case_id=getattr(case, "id"),
            factual_embedding=factual_embedding,
            legal_embedding=legal_embedding,
            outcome_embedding=outcome_embedding,
            combined_embedding=combined_embedding,
            token_count=token_count
        )

    def generate_query_embedding(self, query_text: str) -> np.ndarray:
        """Generate single embedding for a user query.

        Truncate to 6000 tokens before embedding.

        Args:
            query_text: User query text.

        Returns:
            Query embedding vector.
        """
        truncated = self._truncate_to_tokens(query_text, 6000)
        embedding = self._get_embedding(truncated)
        return self._normalize(embedding)

    @property
    def estimated_cost(self) -> float:
        """Cost = total_tokens_used / 1_000_000 * 0.13"""
        return (self.total_tokens_used / 1_000_000) * 0.13

    def _normalize(self, vector: np.ndarray) -> np.ndarray:
        """Normalize a vector to unit norm.

        Args:
            vector: Input vector.

        Returns:
            Normalized vector.
        """
        norm = np.linalg.norm(vector)
        if norm == 0:
            return vector
        return vector / norm

    def _join_list(self, values: Optional[Iterable[Any]]) -> str:
        """Join list-like values into a readable string.

        Args:
            values: Iterable of values.

        Returns:
            Joined string or empty string.
        """
        if not values:
            return ""
        return "; ".join([str(value) for value in values if value])

    def _format_precedents(self, precedents: Optional[Iterable[Any]]) -> str:
        """Format precedent objects into a readable string.

        Args:
            precedents: Iterable of precedent objects.

        Returns:
            Formatted precedents string.
        """
        if not precedents:
            return ""

        formatted = []
        for precedent in precedents:
            name = getattr(precedent, "case_name", None)
            citation = getattr(precedent, "citation", None)
            if name and citation:
                formatted.append(f"{name} ({citation})")
            elif name:
                formatted.append(str(name))
        return "; ".join(formatted)

    def _get_statute_names(self, case: Any) -> list[str]:
        """Extract statute names from a case.

        Args:
            case: SQLAlchemy Case instance.

        Returns:
            List of statute names.
        """
        statutes = []
        case_statutes = getattr(case, "statutes", None)
        if case_statutes:
            for statute in case_statutes:
                name = getattr(statute, "statute_name", None)
                if name:
                    statutes.append(name)

        fallback = getattr(case, "statutes_cited", None)
        if fallback:
            for item in fallback:
                if item:
                    statutes.append(str(item))

        return list(dict.fromkeys(statutes))
