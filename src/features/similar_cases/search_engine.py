"""
Main search pipeline orchestrator.

Full pipeline:
1. Generate query embedding
2. Extract heuristic metadata from query text
3. Vector search (top-50) with optional filters
4. Cross-encoder reranking (top-10)
5. Rule-based similarity explanation for each result
6. Return SearchResponse with disclaimer
"""

from dataclasses import dataclass, field
from typing import Optional
import json
import re
import time

from loguru import logger
from openai import OpenAI

from src.config.settings import settings
from src.features.similar_cases.embedding_generator import EmbeddingGenerator
from src.features.similar_cases.reranker import CrossEncoderReranker, RankedResult
from src.features.similar_cases.similarity_analyzer import (
    SimilarityAnalyzer,
    SimilarityExplanation,
)
from src.features.similar_cases.vector_store import VectorStore, SearchResult


@dataclass
class SearchFilters:
    """Filters for similar case search."""

    court: Optional[str] = None
    case_type: Optional[str] = None
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    verdict: Optional[str] = None
    similarity_mode: str = "combined"  # combined | factual | legal


@dataclass
class CaseSearchResult:
    """Search result with similarity explanation."""

    rank: int
    case_id: int
    case_title: str
    court: str
    date_of_judgment: str
    case_type: str
    verdict: str
    combined_score: float
    vector_score: float
    rerank_score: float
    similarity_explanation: SimilarityExplanation
    statutes_cited: list[str]
    sections_invoked: list[str]
    key_arguments_petitioner: str
    key_arguments_respondent: str
    court_reasoning: str
    headnotes: list[str]


@dataclass
class SearchResponse:
    """Search response envelope."""

    query_summary: str
    total_results: int
    search_time_ms: float
    results: list[CaseSearchResult]
    filters_applied: dict
    disclaimer: str
    retrieval_mode: str = "full"
    warnings: list[str] = field(default_factory=list)


class SimilarCaseSearchEngine:
    """Search engine orchestrating embeddings, retrieval, reranking, and explanations."""

    DISCLAIMER = (
        "This tool provides historical case references for research purposes only. "
        "Similarity scores are statistical measures and do not constitute legal advice. "
        "Always consult the original judgments and verify citations independently. "
        "NyayaAI is a decision support tool, not a legal opinion."
    )

    def __init__(self, openai_client: OpenAI) -> None:
        """Initialize all components.

        Args:
            openai_client: OpenAI client instance.
        """
        self.embedding_generator = EmbeddingGenerator(openai_client)
        self.llm_client: Optional[OpenAI] = openai_client
        self.vector_store = VectorStore(
            host=settings.qdrant_host, port=settings.qdrant_port
        )
        self.reranker = CrossEncoderReranker() if settings.enable_reranking else None
        self.similarity_analyzer = SimilarityAnalyzer(openai_client)

    def search(
        self,
        query_text: str,
        filters: Optional[SearchFilters] = None,
        top_k: int = settings.default_top_k,
        exclude_case_id: Optional[int] = None,
    ) -> SearchResponse:
        """Run full search pipeline. Track time.

        collection_map:
          combined -> COLLECTION_COMBINED
          factual  -> COLLECTION_FACTUAL
          legal    -> COLLECTION_LEGAL

        Return empty SearchResponse if no candidates found.

        Args:
            query_text: Query text.
            filters: Optional search filters.
            top_k: Number of results to return.
            exclude_case_id: Case ID to exclude from results.

        Returns:
            SearchResponse object.
        """
        start = time.time()
        filters = filters or SearchFilters()
        warnings: list[str] = []
        retrieval_mode = "full"

        summarized_text = self._summarize_query_text(query_text)
        query_embedding = self.embedding_generator.generate_query_embedding(
            summarized_text
        )
        query_metadata = self._extract_query_metadata(query_text)
        if filters.court:
            query_metadata["court"] = filters.court
        if filters.case_type:
            query_metadata["case_type"] = filters.case_type

        llm_client = getattr(self, "llm_client", None)
        if settings.enable_query_llm_metadata and llm_client:
            if self._needs_llm_metadata(query_metadata):
                query_metadata = self._augment_metadata_with_llm(
                    query_text, query_metadata
                )

        if not self._looks_like_legal_text(query_text, query_metadata):
            elapsed = (time.time() - start) * 1000
            return SearchResponse(
                query_summary=self._build_query_summary(summarized_text, filters),
                total_results=0,
                search_time_ms=elapsed,
                results=[],
                filters_applied=self._filters_dict(filters),
                disclaimer=(
                    "The uploaded document does not appear to be a legal judgment or petition. "
                    "Please upload a court document or paste case text for similarity search."
                ),
                retrieval_mode="rejected",
                warnings=warnings,
            )

        collection_map = {
            "combined": self.vector_store.COLLECTION_COMBINED,
            "factual": self.vector_store.COLLECTION_FACTUAL,
            "legal": self.vector_store.COLLECTION_LEGAL,
            "fulltext": getattr(
                self.vector_store,
                "COLLECTION_FULLTEXT",
                self.vector_store.COLLECTION_COMBINED,
            ),
        }
        collection = collection_map.get(
            filters.similarity_mode, self.vector_store.COLLECTION_COMBINED
        )
        if settings.enable_fulltext_search and hasattr(
            self.vector_store, "COLLECTION_FULLTEXT"
        ):
            if filters.similarity_mode in {"combined", "fulltext"}:
                if self.vector_store.collection_exists(
                    self.vector_store.COLLECTION_FULLTEXT
                ):
                    collection = self.vector_store.COLLECTION_FULLTEXT
                else:
                    logger.warning(
                        "Full-text collection not found, falling back",
                        collection=collection,
                    )
                    warnings.append(
                        "Full-text collection unavailable; using combined embeddings instead."
                    )

        try:
            candidates = self.vector_store.search(
                query_embedding=query_embedding,
                top_k=settings.vector_search_candidates,
                court_filter=filters.court,
                case_type_filter=filters.case_type,
                year_from=filters.year_from,
                year_to=filters.year_to,
                verdict_filter=filters.verdict,
                collection=collection,
                exclude_case_id=exclude_case_id,
            )
        except Exception as exc:
            logger.error("Vector search failed", error=str(exc))
            warnings.append("Vector search failed; returning no results.")
            elapsed = (time.time() - start) * 1000
            return SearchResponse(
                query_summary=self._build_query_summary(summarized_text, filters),
                total_results=0,
                search_time_ms=elapsed,
                results=[],
                filters_applied=self._filters_dict(filters),
                disclaimer=self.DISCLAIMER,
                retrieval_mode="degraded",
                warnings=warnings,
            )

        if not candidates:
            elapsed = (time.time() - start) * 1000
            return SearchResponse(
                query_summary=self._build_query_summary(summarized_text, filters),
                total_results=0,
                search_time_ms=elapsed,
                results=[],
                filters_applied=self._filters_dict(filters),
                disclaimer=self.DISCLAIMER,
                retrieval_mode=retrieval_mode,
                warnings=warnings,
            )

        if settings.enable_reranking and self.reranker:
            try:
                rerank_pool = sorted(
                    candidates,
                    key=lambda item: item.similarity_score,
                    reverse=True,
                )
                limit = int(settings.reranker_candidate_limit)
                if limit > 0:
                    rerank_pool = rerank_pool[:limit]
                ranked_candidates = self.reranker.rerank(
                    summarized_text, rerank_pool, top_k=top_k
                )
            except Exception as exc:
                logger.warning("Reranker failed; using vector ranking", error=str(exc))
                warnings.append("Reranker unavailable; using vector ranking fallback.")
                retrieval_mode = "degraded"
                ranked_candidates = self._wrap_vector_results(candidates, top_k)
        elif settings.enable_reranking and not self.reranker:
            warnings.append("Reranker disabled/unavailable; using vector ranking only.")
            retrieval_mode = "degraded"
            ranked_candidates = self._wrap_vector_results(candidates, top_k)
        else:
            ranked_candidates = self._wrap_vector_results(candidates, top_k)

        results = []
        rank = 1
        for candidate in ranked_candidates:
            if candidate.combined_score < settings.similarity_threshold:
                continue

            explanation = self.similarity_analyzer.compute_rule_based_similarity(
                query_payload=query_metadata,
                candidate_payload=candidate.payload,
                vector_score=candidate.vector_score,
            )
            results.append(
                CaseSearchResult(
                    rank=rank,
                    case_id=candidate.case_id,
                    case_title=candidate.case_title,
                    court=candidate.court,
                    date_of_judgment=candidate.date_of_judgment,
                    case_type=candidate.case_type,
                    verdict=candidate.verdict,
                    combined_score=candidate.combined_score,
                    vector_score=candidate.vector_score,
                    rerank_score=candidate.rerank_score,
                    similarity_explanation=explanation,
                    statutes_cited=candidate.payload.get("statutes_cited", []) or [],
                    sections_invoked=candidate.payload.get("sections_invoked", [])
                    or [],
                    key_arguments_petitioner=candidate.payload.get(
                        "key_arguments_petitioner", ""
                    )
                    or "",
                    key_arguments_respondent=candidate.payload.get(
                        "key_arguments_respondent", ""
                    )
                    or "",
                    court_reasoning=candidate.payload.get("court_reasoning", "") or "",
                    headnotes=candidate.payload.get("headnotes", []) or [],
                )
            )
            rank += 1

        elapsed = (time.time() - start) * 1000
        return SearchResponse(
            query_summary=self._build_query_summary(summarized_text, filters),
            total_results=len(results),
            search_time_ms=elapsed,
            results=results,
            filters_applied=self._filters_dict(filters),
            disclaimer=self.DISCLAIMER,
            retrieval_mode=retrieval_mode,
            warnings=warnings,
        )

    def _extract_query_metadata(self, query_text: str) -> dict:
        """Heuristic metadata extraction (no LLM).

        Detect statutes by keyword matching:
          IPC, CrPC, CPC, IEA, BNS, BNSS, POCSO, NDPS,
          IT Act, Companies Act, Motor Vehicles Act,
          Negotiable Instruments Act, PMLA, Armed Forces Act

        Detect case_type:
          Criminal: bail, fir, accused, conviction, murder, theft, assault, rape
          Writ: writ, article 226, article 32, fundamental rights, mandamus, habeas
          Civil: contract, civil suit, plaintiff, damages, property, decree
          Constitutional: constitution, article 14, article 19, article 21

        Return dict with statutes_cited, case_type, verdict=None, year=None

        Args:
            query_text: Query text.

        Returns:
            Metadata dictionary.
        """
        text = query_text.lower()
        normalized = " ".join(text.split())
        statutes = []
        statute_keywords = {
            "IPC": ["ipc", "indian penal code"],
            "CrPC": ["crpc", "code of criminal procedure", "bnss"],
            "CPC": ["cpc", "code of civil procedure"],
            "IEA": ["iea", "evidence act", "bsa"],
            "BNS": ["bns", "bharatiya nyaya sanhita"],
            "BNSS": ["bnss", "bharatiya nagarik suraksha sanhita"],
            "POCSO": ["pocso"],
            "NDPS": ["ndps"],
            "IT Act": ["it act", "information technology act"],
            "Companies Act": ["companies act"],
            "Motor Vehicles Act": ["motor vehicles act"],
            "Negotiable Instruments Act": ["negotiable instruments act", "ni act"],
            "PMLA": ["pmla", "prevention of money laundering"],
            "Armed Forces Act": ["armed forces act", "afspa"],
        }
        for statute, keywords in statute_keywords.items():
            if any(keyword in text for keyword in keywords):
                statutes.append(statute)

        case_type = self._extract_case_type(normalized)

        sections_invoked = self._extract_sections(normalized)
        court = self._extract_court(normalized)
        year = self._extract_year(normalized)

        return {
            "statutes_cited": statutes,
            "sections_invoked": sections_invoked,
            "case_type": case_type,
            "verdict": None,
            "year": year,
            "court": court,
        }

    def _looks_like_legal_text(self, query_text: str, query_metadata: dict) -> bool:
        """Heuristic check for legal document relevance."""
        if query_metadata.get("statutes_cited"):
            return True
        if query_metadata.get("sections_invoked"):
            return True
        if query_metadata.get("case_type"):
            return True
        if query_metadata.get("court"):
            return True

        text = query_text.lower()
        strong_indicators = [
            "court",
            "judge",
            "judgment",
            "petition",
            "appellant",
            "respondent",
            "petitioner",
            "versus",
            "v.",
            "appeal",
            "writ",
            "bench",
        ]
        weak_indicators = [
            "section",
            "article",
            "ipc",
            "crpc",
            "cpc",
            "evidence act",
            "constitution",
            "criminal",
            "civil",
        ]

        score = sum(1 for keyword in strong_indicators if keyword in text) * 2
        score += sum(1 for keyword in weak_indicators if keyword in text)

        if score >= 3:
            return True

        import re

        case_number_patterns = [
            r"\b[a-z]{1,6}\s?no\.\s?\d+\/\d{4}",
            r"\b[a-z]{1,6}\s?\d+\/\d{4}",
            r"\bcs\/\d+\/\d{4}",
            r"\bcrl\.?\s?\d+\/\d{4}",
            r"\bwp\s?\d+\/\d{4}",
        ]
        return any(re.search(pattern, text) for pattern in case_number_patterns)

    def _extract_year(self, text: str) -> Optional[int]:
        """Extract a plausible judgment year from text."""
        import re

        matches = re.findall(r"(19[5-9]\d|20[0-2]\d)", text)
        if not matches:
            return None
        try:
            return int(matches[0])
        except ValueError:
            return None

    def _extract_sections(self, text: str) -> list[str]:
        """Extract statutory sections/articles from text."""
        sections = set()
        for match in re.findall(
            r"\b(?:section|sections|sec\.?|u/s)\s+([0-9a-z\s,/&-]+)", text
        ):
            for part in re.findall(r"[0-9]{1,4}[a-z]?", match):
                sections.add(f"Section {part.upper()}")

        for match in re.findall(r"\barticle\s+([0-9]{1,3}[a-z]?)", text):
            sections.add(f"Article {match.upper()}")

        for match in re.findall(r"\bipc\s+([0-9]{1,4}[a-z]?)", text):
            sections.add(f"IPC {match.upper()}")
        for match in re.findall(r"\bcrpc\s+([0-9]{1,4}[a-z]?)", text):
            sections.add(f"CrPC {match.upper()}")

        return sorted(sections)

    def _extract_case_type(self, text: str) -> Optional[str]:
        """Infer case type from common keywords and case numbers."""
        if any(
            term in text
            for term in [
                "bail",
                "fir",
                "accused",
                "conviction",
                "murder",
                "theft",
                "assault",
                "rape",
                "crl",
                "criminal appeal",
                "cr.a",
                "cr.a.",
            ]
        ):
            return "Criminal"
        if any(
            term in text
            for term in [
                "writ",
                "article 226",
                "article 32",
                "mandamus",
                "habeas",
                "owp",
                "cwp",
                "wp no",
                "w.p.",
            ]
        ):
            return "Writ"
        if any(
            term in text
            for term in [
                "contract",
                "civil suit",
                "plaintiff",
                "damages",
                "property",
                "decree",
                "cs no",
                "o.s.",
            ]
        ):
            return "Civil"
        if any(
            term in text
            for term in ["constitution", "article 14", "article 19", "article 21"]
        ):
            return "Constitutional"
        if any(
            term in text
            for term in ["family court", "maintenance", "divorce", "matrimonial"]
        ):
            return "Family"
        if any(term in text for term in ["tax", "gst", "income tax", "vat"]):
            return "Tax"
        return None

    def _summarize_query_text(self, query_text: str) -> str:
        """Strip boilerplate headers and keep the substantive portion."""
        if not query_text:
            return ""

        cleaned = query_text.replace("\r", "\n")
        lines = [line.strip() for line in cleaned.split("\n") if line.strip()]
        if not lines:
            return query_text

        heading_patterns = [
            "judgment",
            "order",
            "oral order",
            "judgement",
        ]
        start_index = None
        for i, line in enumerate(lines[:60]):
            lower = line.lower()
            if any(pattern in lower for pattern in heading_patterns):
                start_index = i + 1
                break

        if start_index is not None and start_index < len(lines):
            content_lines = lines[start_index:]
        else:
            content_lines = []
            header_regex = re.compile(
                r"^(in the|before|coram|dated|date|court|judg(e)?ment|order|oral|appearance|through|present|cause title|case no|cs no|crl|wp|owp|cwp|ia no|oa no|petitioner|respondent|appellant|versus|vs\.?|v\.)",
                re.IGNORECASE,
            )
            for idx, line in enumerate(lines):
                if idx < 25 and (
                    header_regex.match(line) or (line.isupper() and len(line) < 120)
                ):
                    continue
                content_lines.append(line)

        summary = "\n".join(content_lines).strip()
        if summary:
            return summary

        fallback_lines = lines[10:] if len(lines) > 10 else lines
        fallback_summary = "\n".join(fallback_lines).strip()
        return fallback_summary or query_text

    def _needs_llm_metadata(self, metadata: dict) -> bool:
        """Determine if LLM metadata extraction should run."""
        return (
            not metadata.get("case_type")
            or len(metadata.get("sections_invoked", [])) < 2
        )

    def _augment_metadata_with_llm(self, query_text: str, metadata: dict) -> dict:
        """Use a small LLM pass to extract case_type and sections."""
        if not self.llm_client:
            return metadata
        prompt = (
            "Extract case_type and sections_invoked from the text. "
            "Return strict JSON with keys: case_type (string or null), sections_invoked (array of strings), statutes_cited (array of strings). "
            "Case type must be one of: Criminal, Civil, Writ, Constitutional, Family, Tax, Commercial, Contempt, Miscellaneous."
        )
        snippet = query_text[:3000]
        try:
            response = self.llm_client.chat.completions.create(
                model=settings.query_metadata_model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": snippet},
                ],
                temperature=0.0,
                max_tokens=250,
            )
            content = (response.choices[0].message.content or "").strip()
            json_blob = content
            if "```" in content:
                json_blob = re.sub(
                    r"```(?:json)?", "", content, flags=re.IGNORECASE
                ).strip()
                json_blob = json_blob.replace("```", "").strip()
            start = json_blob.find("{")
            end = json_blob.rfind("}")
            if start != -1 and end != -1:
                json_blob = json_blob[start : end + 1]
            parsed = json.loads(json_blob)
        except Exception as exc:
            logger.warning("Query LLM metadata extraction failed", error=str(exc))
            return metadata

        case_type = parsed.get("case_type")
        sections = parsed.get("sections_invoked") or []
        statutes = parsed.get("statutes_cited") or []

        merged = dict(metadata)
        if case_type and not merged.get("case_type"):
            merged["case_type"] = case_type
        if sections:
            merged["sections_invoked"] = sorted(
                set(merged.get("sections_invoked", []) + sections)
            )
        if statutes:
            merged["statutes_cited"] = sorted(
                set(merged.get("statutes_cited", []) + statutes)
            )
        return merged

    def _extract_court(self, text: str) -> Optional[str]:
        """Extract court name from text heuristically."""
        import re

        patterns = [
            r"high court of judicature at ([a-z &]+)",
            r"high court of judicature of ([a-z &]+)",
            r"high court of ([a-z &]+)",
            r"supreme court of india",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                if "supreme court" in pattern:
                    return "Supreme Court of India"
                name = match.group(1).strip()
                name = " ".join(word.capitalize() for word in name.split())
                return f"High Court of {name}"
        return None

    def _build_query_summary(self, query_text: str, filters: SearchFilters) -> str:
        """Build human-readable summary of the search query + filters applied.

        Args:
            query_text: Query text.
            filters: Search filters.

        Returns:
            Summary string.
        """
        trimmed = query_text.strip().replace("\n", " ")
        summary = trimmed[:200] + ("..." if len(trimmed) > 200 else "")
        filter_parts = []
        if filters.court:
            filter_parts.append(f"court={filters.court}")
        if filters.case_type:
            filter_parts.append(f"case_type={filters.case_type}")
        if filters.verdict:
            filter_parts.append(f"verdict={filters.verdict}")
        if filters.year_from or filters.year_to:
            filter_parts.append(
                f"year={filters.year_from or 'any'}-{filters.year_to or 'any'}"
            )
        if filter_parts:
            summary = f"{summary} | Filters: {', '.join(filter_parts)}"
        return summary

    def _filters_dict(self, filters: SearchFilters) -> dict:
        """Convert filters to dict for response."""
        return {
            "court": filters.court,
            "case_type": filters.case_type,
            "year_from": filters.year_from,
            "year_to": filters.year_to,
            "verdict": filters.verdict,
            "similarity_mode": filters.similarity_mode,
        }

    def _wrap_vector_results(
        self, candidates: list[SearchResult], top_k: int
    ) -> list[RankedResult]:
        """Wrap vector results as ranked results when reranking is disabled."""
        ranked = []
        for candidate in candidates[:top_k]:
            ranked.append(
                RankedResult(
                    case_id=candidate.case_id,
                    case_title=candidate.case_title,
                    court=candidate.court,
                    date_of_judgment=candidate.date_of_judgment,
                    case_type=candidate.case_type,
                    verdict=candidate.verdict,
                    rerank_score=candidate.similarity_score,
                    vector_score=candidate.similarity_score,
                    combined_score=candidate.similarity_score,
                    payload=candidate.payload,
                )
            )
        return ranked
