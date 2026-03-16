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
from collections import Counter
from typing import Optional
import json
import math
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
        vector_candidate_k: Optional[int] = None,
        reranker_candidate_limit: Optional[int] = None,
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
            vector_candidate_k: Optional override for vector candidate pool size.
            reranker_candidate_limit: Optional override for reranker pool size.

        Returns:
            SearchResponse object.
        """
        start = time.time()
        filters = filters or SearchFilters()
        warnings: list[str] = []
        retrieval_mode = "full"

        prepared_text = self._prepare_query_text(query_text)
        summarized_text = self._summarize_query_text(prepared_text)
        query_embedding = self.embedding_generator.generate_query_embedding(
            summarized_text
        )
        query_metadata = self._extract_query_metadata(prepared_text)
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
            vector_pool = int(vector_candidate_k or settings.vector_search_candidates)
            candidates = self.vector_store.search(
                query_embedding=query_embedding,
                top_k=vector_pool,
                court_filter=filters.court,
                case_type_filter=filters.case_type,
                year_from=filters.year_from,
                year_to=filters.year_to,
                verdict_filter=filters.verdict,
                collection=collection,
                exclude_case_id=exclude_case_id,
            )

            if settings.enable_hybrid_retrieval:
                candidates = self._build_hybrid_candidates(
                    query_text=prepared_text,
                    query_embedding=query_embedding,
                    base_candidates=candidates,
                    filters=filters,
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
                limit = int(
                    reranker_candidate_limit or settings.reranker_candidate_limit
                )
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

            candidate_payload = self._enrich_candidate_metadata(candidate.payload)
            explanation = self.similarity_analyzer.compute_rule_based_similarity(
                query_payload=query_metadata,
                candidate_payload=candidate_payload,
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
                    statutes_cited=candidate_payload.get("statutes_cited", []) or [],
                    sections_invoked=candidate_payload.get("sections_invoked", [])
                    or [],
                    key_arguments_petitioner=candidate_payload.get(
                        "key_arguments_petitioner", ""
                    )
                    or "",
                    key_arguments_respondent=candidate_payload.get(
                        "key_arguments_respondent", ""
                    )
                    or "",
                    court_reasoning=candidate_payload.get("court_reasoning", "") or "",
                    headnotes=candidate_payload.get("headnotes", []) or [],
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

        inferred_from_sections = self._infer_statutes_from_sections(
            self._extract_sections(normalized)
        )
        if inferred_from_sections:
            statutes.extend(inferred_from_sections)
        statutes = sorted(set(statutes))

        case_type = self._extract_case_type(normalized)

        sections_invoked = self._extract_sections(normalized)
        court = self._extract_court(normalized)
        year = self._extract_year(normalized)
        verdict = self._extract_verdict(normalized)

        return {
            "statutes_cited": statutes,
            "sections_invoked": sections_invoked,
            "case_type": case_type,
            "verdict": verdict,
            "year": year,
            "court": court,
        }

    def _prepare_query_text(self, query_text: str) -> str:
        """Prepare query text by removing boilerplate and prioritizing useful blocks."""
        stripped = self._strip_boilerplate_blocks(query_text)
        salient = self._extract_salient_blocks(stripped)
        if len(salient.strip()) >= 300:
            return salient
        return stripped

    def _strip_boilerplate_blocks(self, query_text: str) -> str:
        """Remove repetitive legal header/noise blocks from uploaded text."""
        if not query_text:
            return ""

        lines = [line.strip() for line in query_text.replace("\r", "\n").split("\n")]
        cleaned_lines = []
        skip_line_patterns = [
            r"^in the .{0,80}court",
            r"^before[:\s]",
            r"^coram[:\s]",
            r"^appearance[:\s]",
            r"^advocate for",
            r"^for the petitioner",
            r"^for the respondent",
            r"^order\b",
            r"^oral order\b",
            r"^page no",
            r"^case no\.?",
            r"^cs/?\d",
            r"^ia no\.?",
            r"^\.{2,}$",
        ]

        compiled = [
            re.compile(pattern, re.IGNORECASE) for pattern in skip_line_patterns
        ]
        for idx, line in enumerate(lines):
            if not line:
                continue
            if idx < 120 and any(pattern.search(line) for pattern in compiled):
                continue
            if idx < 120 and line.isupper() and len(line) < 130:
                continue
            cleaned_lines.append(line)

        return "\n".join(cleaned_lines).strip()

    def _extract_salient_blocks(self, text: str) -> str:
        """Select fact/issue/reasoning heavy paragraphs from cleaned text."""
        if not text:
            return ""

        paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
        if not paragraphs:
            return text

        priority_terms = {
            "facts": 3,
            "fact": 3,
            "issue": 3,
            "questions": 2,
            "reason": 3,
            "held": 3,
            "finding": 2,
            "analysis": 2,
            "evidence": 2,
            "section": 2,
            "article": 2,
            "statute": 2,
            "petitioner": 1,
            "respondent": 1,
            "therefore": 1,
            "accordingly": 1,
        }

        scored: list[tuple[int, str]] = []
        for paragraph in paragraphs:
            lower = paragraph.lower()
            score = 0
            for term, weight in priority_terms.items():
                if term in lower:
                    score += weight
            if len(paragraph) > 450:
                score += 1
            scored.append((score, paragraph))

        scored.sort(key=lambda item: item[0], reverse=True)
        selected = [paragraph for _, paragraph in scored[:8] if paragraph]
        if not selected:
            selected = paragraphs[:6]
        return "\n\n".join(selected)

    def _extract_verdict(self, text: str) -> Optional[str]:
        """Infer coarse verdict label from query text."""
        verdict_patterns = {
            "Allowed": ["petition is allowed", "appeal allowed", "is allowed"],
            "Dismissed": [
                "petition is dismissed",
                "appeal dismissed",
                "is dismissed",
            ],
            "Convicted": ["convicted", "conviction"],
            "Acquitted": ["acquitted", "acquittal"],
            "Bail Granted": ["bail granted", "released on bail"],
            "Bail Rejected": ["bail rejected", "bail denied"],
        }
        for label, patterns in verdict_patterns.items():
            if any(pattern in text for pattern in patterns):
                return label
        return None

    def _infer_statutes_from_sections(self, sections: list[str]) -> list[str]:
        """Infer statutes from section-style citations."""
        inferred = set()
        for section in sections:
            upper = section.upper()
            if "IPC" in upper:
                inferred.add("IPC")
            if "CRPC" in upper:
                inferred.add("CrPC")
            if "CPC" in upper and "CRPC" not in upper:
                inferred.add("CPC")
            if "ARTICLE" in upper:
                inferred.add("Constitution")
            if "NDPS" in upper:
                inferred.add("NDPS")
            if "POCSO" in upper:
                inferred.add("POCSO")
            if "NI" in upper or "NEGOTIABLE" in upper:
                inferred.add("Negotiable Instruments Act")
        return sorted(inferred)

    def _enrich_candidate_metadata(self, payload: dict) -> dict:
        """Backfill sparse candidate metadata from payload text fields."""
        enriched = dict(payload)
        full_blob = "\n".join(
            [
                str(payload.get("case_title", "") or ""),
                str(payload.get("court_reasoning", "") or ""),
                str(payload.get("key_arguments_petitioner", "") or ""),
                str(payload.get("key_arguments_respondent", "") or ""),
                " ".join(payload.get("headnotes", []) or []),
                str(payload.get("full_text", "") or "")[:3000],
            ]
        ).lower()

        sections = list(payload.get("sections_invoked", []) or [])
        if not sections:
            sections = self._extract_sections(full_blob)
            if sections:
                enriched["sections_invoked"] = sections

        statutes = list(payload.get("statutes_cited", []) or [])
        statutes.extend(self._infer_statutes_from_sections(sections))
        if not statutes:
            for statute in ["ipc", "crpc", "cpc", "ndps", "pocso", "companies act"]:
                if statute in full_blob:
                    statutes.append(
                        statute.upper()
                        if statute in {"ipc", "crpc", "cpc"}
                        else statute.title()
                    )
        if statutes:
            enriched["statutes_cited"] = sorted(
                set(str(item).strip() for item in statutes if str(item).strip())
            )

        case_type = str(payload.get("case_type", "") or "").strip()
        if not case_type:
            inferred_case_type = self._extract_case_type(full_blob)
            if inferred_case_type:
                enriched["case_type"] = inferred_case_type

        verdict = str(payload.get("verdict", "") or "").strip()
        if not verdict:
            inferred_verdict = self._extract_verdict(full_blob)
            if inferred_verdict:
                enriched["verdict"] = inferred_verdict

        return enriched

    def _build_hybrid_candidates(
        self,
        query_text: str,
        query_embedding,
        base_candidates: list[SearchResult],
        filters: SearchFilters,
        collection: str,
        exclude_case_id: Optional[int],
    ) -> list[SearchResult]:
        """Blend vector and BM25-like lexical signals before reranking."""
        candidates = list(base_candidates)
        extra_per_collection = int(settings.hybrid_extra_candidates)
        if extra_per_collection > 0 and hasattr(
            self.vector_store, "search_across_collections"
        ):
            extra_collections = [
                self.vector_store.COLLECTION_COMBINED,
                self.vector_store.COLLECTION_LEGAL,
                self.vector_store.COLLECTION_FACTUAL,
            ]
            if hasattr(self.vector_store, "COLLECTION_FULLTEXT"):
                extra_collections.append(self.vector_store.COLLECTION_FULLTEXT)
            extra_collections = [
                name for name in extra_collections if name and name != collection
            ]
            if extra_collections:
                expanded = self.vector_store.search_across_collections(
                    query_embedding=query_embedding,
                    collections=extra_collections,
                    top_k_each=extra_per_collection,
                    court_filter=filters.court,
                    case_type_filter=filters.case_type,
                    year_from=filters.year_from,
                    year_to=filters.year_to,
                    verdict_filter=filters.verdict,
                    exclude_case_id=exclude_case_id,
                )
                by_case = {item.case_id: item for item in candidates}
                for item in expanded:
                    existing = by_case.get(item.case_id)
                    if (
                        existing is None
                        or item.similarity_score > existing.similarity_score
                    ):
                        by_case[item.case_id] = item
                candidates = list(by_case.values())

        if not candidates:
            return candidates
        if len(candidates) == 1:
            return candidates

        query_terms = self._extract_lexical_query_terms(query_text)
        lexical_scores = self._bm25_like_scores(query_terms, candidates)
        vector_scores = {
            item.case_id: float(item.similarity_score) for item in candidates
        }

        vec_values = list(vector_scores.values())
        vec_min = min(vec_values)
        vec_max = max(vec_values)

        v_weight = float(settings.hybrid_vector_weight)
        l_weight = float(settings.hybrid_lexical_weight)
        total = v_weight + l_weight
        if total <= 0:
            v_weight, l_weight = 0.7, 0.3
            total = 1.0
        v_weight /= total
        l_weight /= total

        fused: list[SearchResult] = []
        for item in candidates:
            if vec_max == vec_min:
                vector_norm = 0.5
            else:
                vector_norm = (item.similarity_score - vec_min) / (vec_max - vec_min)
            lexical_norm = lexical_scores.get(item.case_id, 0.0)
            hybrid_score = (v_weight * float(vector_norm)) + (
                l_weight * float(lexical_norm)
            )
            fused.append(
                SearchResult(
                    case_id=item.case_id,
                    case_title=item.case_title,
                    court=item.court,
                    date_of_judgment=item.date_of_judgment,
                    case_type=item.case_type,
                    verdict=item.verdict,
                    similarity_score=hybrid_score,
                    payload=item.payload,
                )
            )

        fused.sort(key=lambda item: item.similarity_score, reverse=True)
        return fused

    def _extract_lexical_query_terms(self, query_text: str) -> set[str]:
        """Extract high-signal lexical terms for BM25-like matching."""
        lower = query_text.lower()
        tokens = re.findall(r"[a-z0-9]{3,}", lower)
        stop = {
            "the",
            "and",
            "for",
            "with",
            "that",
            "from",
            "this",
            "were",
            "have",
            "been",
            "court",
            "case",
            "order",
            "judgment",
        }
        filtered = [token for token in tokens if token not in stop]
        counts = Counter(filtered)
        top_text_terms = [term for term, _ in counts.most_common(40)]

        metadata = self._extract_query_metadata(query_text)
        statute_terms = [item.lower() for item in metadata.get("statutes_cited", [])]
        section_terms = [
            item.lower().replace(" ", "")
            for item in metadata.get("sections_invoked", [])
        ]
        return set(top_text_terms + statute_terms + section_terms)

    def _bm25_like_scores(
        self, query_terms: set[str], candidates: list[SearchResult]
    ) -> dict[int, float]:
        """Compute BM25-like lexical scores over candidate payload text."""
        if not query_terms or not candidates:
            return {item.case_id: 0.0 for item in candidates}

        doc_tokens: dict[int, list[str]] = {}
        doc_len: dict[int, int] = {}
        term_doc_freq: Counter[str] = Counter()

        for item in candidates:
            payload = item.payload or {}
            blob = " ".join(
                [
                    str(payload.get("case_title", "") or ""),
                    " ".join(payload.get("headnotes", []) or []),
                    str(payload.get("court_reasoning", "") or ""),
                    str(payload.get("full_text", "") or "")[:2500],
                    " ".join(payload.get("statutes_cited", []) or []),
                    " ".join(payload.get("sections_invoked", []) or []),
                ]
            ).lower()
            tokens = re.findall(r"[a-z0-9]{2,}", blob)
            doc_tokens[item.case_id] = tokens
            doc_len[item.case_id] = len(tokens)
            unique_terms = set(tokens)
            for term in query_terms:
                if term in unique_terms:
                    term_doc_freq[term] += 1

        avgdl = sum(doc_len.values()) / max(len(doc_len), 1)
        n_docs = len(candidates)
        k1 = 1.2
        b = 0.75

        raw_scores: dict[int, float] = {}
        for item in candidates:
            tokens = doc_tokens[item.case_id]
            tf = Counter(tokens)
            dl = max(doc_len[item.case_id], 1)
            score = 0.0
            for term in query_terms:
                term_freq = tf.get(term, 0)
                if term_freq <= 0:
                    continue
                df = term_doc_freq.get(term, 0)
                idf = math.log(1.0 + ((n_docs - df + 0.5) / (df + 0.5)))
                numerator = term_freq * (k1 + 1.0)
                denominator = term_freq + k1 * (1 - b + b * (dl / max(avgdl, 1.0)))
                score += idf * (numerator / max(denominator, 1e-6))
            raw_scores[item.case_id] = score

        values = list(raw_scores.values())
        if not values:
            return {item.case_id: 0.0 for item in candidates}
        vmin = min(values)
        vmax = max(values)
        if vmax == vmin:
            return {case_id: 0.0 for case_id in raw_scores}

        return {
            case_id: (score - vmin) / (vmax - vmin)
            for case_id, score in raw_scores.items()
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
            r"\b(?:section|sections|sec\.?|u/s)\s+([0-9a-z\s,/&().-]+)", text
        ):
            for part in re.findall(r"[0-9]{1,4}[a-z]?", match):
                sections.add(f"Section {part.upper()}")

        for match in re.findall(r"\barticle\s+([0-9]{1,3}[a-z]?)", text):
            sections.add(f"Article {match.upper()}")

        for match in re.findall(r"\bipc\s+([0-9]{1,4}[a-z]?)", text):
            sections.add(f"IPC {match.upper()}")
        for match in re.findall(r"\bcrpc\s+([0-9]{1,4}[a-z]?)", text):
            sections.add(f"CrPC {match.upper()}")
        for match in re.findall(
            r"\b(?:under|u/s)\s+([0-9]{1,4}[a-z]?)\s+of\s+(?:the\s+)?([a-z][a-z\s]{2,40}act)",
            text,
        ):
            section_no, act_name = match
            act = " ".join(word.capitalize() for word in act_name.split())
            sections.add(f"Section {section_no.upper()} {act}")

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
                "civil jurisdiction",
                "original civil",
                "civil suit",
                "plaintiff",
                "damages",
                "property",
                "decree",
                "cs no",
                "cs/",
                "title suit",
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
            r"high court at ([a-z &]+)",
            r"supreme court of india",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                if "supreme court" in pattern:
                    return "Supreme Court of India"
                name = match.group(1).strip()
                stop_tokens = {
                    "original",
                    "side",
                    "appellate",
                    "civil",
                    "criminal",
                    "jurisdiction",
                    "bench",
                    "ordinary",
                    "special",
                    "ia",
                    "no",
                    "coram",
                    "before",
                }
                name_parts = [part for part in name.split() if part]
                cleaned_parts = []
                for part in name_parts:
                    if part in stop_tokens:
                        break
                    cleaned_parts.append(part)
                name = " ".join(cleaned_parts[:4])
                name = " ".join(word.capitalize() for word in name.split())
                if name:
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
