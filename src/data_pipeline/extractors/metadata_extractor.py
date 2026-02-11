"""
LLM-powered metadata extraction from legal documents.
This is the most critical module for structured data extraction.
"""
import json
import time
from typing import Dict, Any, Optional
from datetime import datetime
from loguru import logger

from src.utils.llm_client import LLMClient
from src.database.schemas import CaseMetadata, PrecedentCitation
from src.config.settings import settings


class MetadataExtractor:
    """
    Extract structured metadata from legal judgment text using LLMs.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """
        Initialize metadata extractor.

        Args:
            llm_client: LLM client instance (creates new if None)
        """
        self.llm_client = llm_client or LLMClient()
        logger.info("Metadata extractor initialized", model=self.llm_client.model)

    def extract_case_metadata(self, judgment_text: str, case_id: Optional[str] = None) -> CaseMetadata:
        """
        Extract structured metadata from judgment text.

        Args:
            judgment_text: Full text of the judgment
            case_id: Optional case identifier for logging

        Returns:
            CaseMetadata object with extracted information
        """
        logger.info(f"Extracting metadata", case_id=case_id, text_length=len(judgment_text))

        start_time = time.time()

        try:
            # Truncate text if too long (keep first 15000 and last 5000 chars)
            if len(judgment_text) > 20000:
                truncated_text = judgment_text[:15000] + "\n\n[...MIDDLE SECTION TRUNCATED...]\n\n" + judgment_text[-5000:]
                logger.warning(f"Text truncated", original_length=len(judgment_text), truncated_length=len(truncated_text))
            else:
                truncated_text = judgment_text

            # Build extraction prompt
            system_prompt = self._build_system_prompt()
            user_prompt = self._build_user_prompt(truncated_text)

            # Call LLM with structured output request
            response_text = self.llm_client.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=settings.extraction_temperature,
                max_tokens=4000
            )

            # Parse JSON response
            metadata_dict = self._parse_llm_response(response_text)

            # Convert to Pydantic model
            metadata = self._dict_to_metadata(metadata_dict)

            elapsed = time.time() - start_time
            avg_confidence = metadata.get_average_confidence()

            logger.info(
                f"Metadata extraction complete",
                case_id=case_id,
                elapsed=f"{elapsed:.2f}s",
                avg_confidence=f"{avg_confidence:.2f}"
            )

            return metadata

        except Exception as e:
            logger.error(f"Metadata extraction failed", case_id=case_id, error=str(e))
            # Return empty metadata with error info
            return CaseMetadata(confidence_scores={"error": 0.0})

    def _build_system_prompt(self) -> str:
        """Build the system prompt for extraction."""
        return """You are an expert legal document parser specializing in Indian court judgments. Your task is to extract structured information from judgment text with high accuracy.

Extract ONLY information that is explicitly stated in the document. Do NOT infer or guess. For missing information, use null values.

Output MUST be valid JSON matching this exact schema:
{
  "case_id": "string or null",
  "case_title": "string or null",
  "court": "string or null",
  "bench": ["array of judge names"] or null,
  "date_of_judgment": "YYYY-MM-DD or null",
  "case_type": "Criminal/Civil/Constitutional/etc. or null",
  "petitioner": ["array of names"] or null,
  "respondent": ["array of names"] or null,
  "statutes_cited": ["array of statute names"] or null,
  "sections_invoked": ["array of section references"] or null,
  "charges": ["array of charge descriptions"] or null,
  "verdict": "string or null",
  "sentence": "string or null",
  "key_arguments_petitioner": "string summary or null",
  "key_arguments_respondent": "string summary or null",
  "court_reasoning": "string summary or null",
  "precedents_cited": [{"case_name": "string", "citation": "string", "year": number, "court": "string", "legal_principle": "string"}] or null,
  "headnotes": ["array of key legal principles"] or null,
  "confidence_scores": {"field_name": 0.0-1.0}
}

IMPORTANT RULES:
1. Normalize statute names: "IPC" not "Indian Penal Code", "CrPC" not "Code of Criminal Procedure"
2. Dates must be in ISO format: YYYY-MM-DD
3. Provide confidence score (0.0-1.0) for EVERY extracted field
4. Confidence 1.0 = explicitly stated, 0.7-0.9 = strongly implied, 0.5-0.6 = weakly implied, 0.0 = not found
5. For sections, use format: "IPC Section 302", "CrPC Section 164"
6. Extract ALL cited precedents with full details
7. Summarize arguments in 2-3 sentences each
8. For bench, use full judge names as they appear
"""

    def _build_user_prompt(self, judgment_text: str) -> str:
        """Build the user prompt with judgment text."""
        return f"""Extract structured metadata from this Indian court judgment. Return ONLY valid JSON, no other text.

JUDGMENT TEXT:
{judgment_text}

Remember:
- Extract only what is explicitly stated
- Use null for missing fields
- Provide confidence scores for all fields
- Use ISO date format (YYYY-MM-DD)
- Normalize statute names (IPC, CrPC, CPC, etc.)

JSON OUTPUT:"""

    def _parse_llm_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse LLM response to extract JSON.

        Args:
            response_text: Raw LLM response

        Returns:
            Parsed dictionary
        """
        try:
            # Try direct JSON parsing
            return json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
                return json.loads(json_text)
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
                return json.loads(json_text)
            else:
                # Try to find JSON object in text
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                if start != -1 and end > start:
                    json_text = response_text[start:end]
                    return json.loads(json_text)
                else:
                    raise ValueError("No valid JSON found in response")

    def _dict_to_metadata(self, data: Dict[str, Any]) -> CaseMetadata:
        """
        Convert dictionary to CaseMetadata object.

        Args:
            data: Dictionary from LLM

        Returns:
            CaseMetadata object
        """
        # Parse date if present
        date_of_judgment = None
        if data.get("date_of_judgment"):
            try:
                date_of_judgment = datetime.strptime(data["date_of_judgment"], "%Y-%m-%d").date()
            except (ValueError, TypeError):
                logger.warning(f"Invalid date format: {data.get('date_of_judgment')}")

        # Parse precedents
        precedents = []
        if data.get("precedents_cited"):
            for prec in data["precedents_cited"]:
                if isinstance(prec, dict):
                    try:
                        precedents.append(PrecedentCitation(**prec))
                    except Exception as e:
                        logger.warning(f"Failed to parse precedent: {prec}, error: {e}")

        # Ensure confidence_scores is a dict
        confidence_scores = data.get("confidence_scores", {})
        if not isinstance(confidence_scores, dict):
            confidence_scores = {}

        # Create metadata object
        metadata = CaseMetadata(
            case_id=data.get("case_id"),
            case_title=data.get("case_title"),
            court=data.get("court"),
            bench=data.get("bench") or [],
            date_of_judgment=date_of_judgment,
            case_type=data.get("case_type"),
            petitioner=data.get("petitioner") or [],
            respondent=data.get("respondent") or [],
            statutes_cited=data.get("statutes_cited") or [],
            sections_invoked=data.get("sections_invoked") or [],
            charges=data.get("charges") or [],
            verdict=data.get("verdict"),
            sentence=data.get("sentence"),
            key_arguments_petitioner=data.get("key_arguments_petitioner"),
            key_arguments_respondent=data.get("key_arguments_respondent"),
            court_reasoning=data.get("court_reasoning"),
            precedents_cited=precedents,
            headnotes=data.get("headnotes") or [],
            confidence_scores=confidence_scores
        )

        return metadata

    def extract_batch(self, texts: list[tuple[str, str]]) -> list[CaseMetadata]:
        """
        Extract metadata from multiple documents.

        Args:
            texts: List of (text, case_id) tuples

        Returns:
            List of CaseMetadata objects
        """
        logger.info(f"Batch extraction started", batch_size=len(texts))

        results = []
        for text, case_id in texts:
            try:
                metadata = self.extract_case_metadata(text, case_id)
                results.append(metadata)
            except Exception as e:
                logger.error(f"Batch extraction failed for case", case_id=case_id, error=str(e))
                results.append(CaseMetadata(confidence_scores={"error": 0.0}))

        logger.info(f"Batch extraction complete", total=len(results))
        return results
