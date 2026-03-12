"""
Evaluate search quality. Run this after embedding generation.

Test 1: Self-Retrieval (sample_size=50)
  - For each case, search using its own text
  - Case should appear as #1 result
  - Target: >95% accuracy
  - IMPORTANT: Don't exclude the case (exclude_case_id=None)

Test 2: Category Coherence (sample_size=20 per type)
  - For Criminal/Civil/Writ cases, check if results are same type
  - Target: >80% same-type results
  - Exclude the query case from results

Test 3: Statute Clustering (sample_size=20)
  - Cases with IPC Section 302 should return IPC 302 cases
  - Cases with NDPS Act should return NDPS cases

Test 4: Filter Validation
  - Apply court filter: results should only be from that court
  - Apply case_type filter: results should match type
  - Apply year range: results should be within range

Test 5: Performance Benchmark
  - Time 20 searches
  - Report: min, max, mean, p95 latency
  - Target: <3000ms mean

Test 6: Manual Spot Check (n=5)
  - Show 5 random cases with their top-5 results
  - Print for human review (press Enter to continue)

Final report:
  Self-retrieval: X% (PASS/FAIL)
  Category coherence: Criminal X%, Civil X%, Writ X%
  Filter validation: PASS/FAIL
  Mean latency: Xms (PASS/FAIL)

  OVERALL: READY FOR FRONTEND / NEEDS IMPROVEMENT
"""

import random
import time
import sys

import numpy as np
from loguru import logger
from openai import OpenAI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config.settings import settings
from src.database.models import Case, Statute
from src.features.similar_cases.search_engine import SimilarCaseSearchEngine, SearchFilters


def main() -> None:
    """Run search quality evaluations."""
    openai_client = OpenAI(api_key=settings.openai_api_key)
    search_engine = SimilarCaseSearchEngine(openai_client)

    engine = create_engine(settings.database_url, echo=False)
    session_local = sessionmaker(bind=engine)
    session = session_local()

    try:
        cases = session.query(Case).filter(Case.validation_status != "invalid").all()
        if not cases:
            logger.error("No cases available for testing")
            return

        self_retrieval_score = _test_self_retrieval(search_engine, cases)
        category_scores = _test_category_coherence(search_engine, session)
        statute_scores = _test_statute_clustering(search_engine, session)
        filter_pass = _test_filter_validation(search_engine, session)
        performance_stats = _test_performance(search_engine, cases)
        _manual_spot_check(search_engine, cases)

        overall_ready = (
            self_retrieval_score >= 0.95
            and all(score >= 0.80 for score in category_scores.values())
            and filter_pass
            and performance_stats["mean_ms"] < 3000
        )

        logger.info(
            "Metrics",
            self_retrieval=f"{self_retrieval_score:.2%}",
            criminal=f"{category_scores.get('Criminal', 0):.2%}",
            civil=f"{category_scores.get('Civil', 0):.2%}",
            writ=f"{category_scores.get('Writ', 0):.2%}",
            statute_ipc_302=f"{statute_scores.get('IPC Section 302', 0):.2%}",
            statute_ndps=f"{statute_scores.get('NDPS', 0):.2%}",
            filter_validation="PASS" if filter_pass else "FAIL",
            latency_mean_ms=f"{performance_stats['mean_ms']:.0f}",
            latency_p95_ms=f"{performance_stats['p95_ms']:.0f}",
        )
        print("Metrics:")
        print(f"  Self-retrieval: {self_retrieval_score:.2%}")
        print(f"  Category coherence - Criminal: {category_scores.get('Criminal', 0):.2%}")
        print(f"  Category coherence - Civil: {category_scores.get('Civil', 0):.2%}")
        print(f"  Category coherence - Writ: {category_scores.get('Writ', 0):.2%}")
        print(f"  Statute clustering - IPC Section 302: {statute_scores.get('IPC Section 302', 0):.2%}")
        print(f"  Statute clustering - NDPS: {statute_scores.get('NDPS', 0):.2%}")
        print(f"  Filter validation: {'PASS' if filter_pass else 'FAIL'}")
        print(f"  Mean latency: {performance_stats['mean_ms']:.0f} ms")
        print(f"  P95 latency: {performance_stats['p95_ms']:.0f} ms")
        logger.info(
            "Final report",
            self_retrieval=f"{self_retrieval_score:.2%}",
            criminal=f"{category_scores.get('Criminal', 0):.2%}",
            civil=f"{category_scores.get('Civil', 0):.2%}",
            writ=f"{category_scores.get('Writ', 0):.2%}",
            filter_validation="PASS" if filter_pass else "FAIL",
            mean_latency_ms=f"{performance_stats['mean_ms']:.0f}",
            overall="READY FOR FRONTEND" if overall_ready else "NEEDS IMPROVEMENT",
        )
    finally:
        session.close()


def _test_self_retrieval(search_engine: SimilarCaseSearchEngine, cases: list[Case]) -> float:
    """Evaluate self-retrieval accuracy.

    Args:
        search_engine: SimilarCaseSearchEngine instance.
        cases: List of Case objects.

    Returns:
        Self-retrieval accuracy.
    """
    sample = random.sample(cases, min(50, len(cases)))
    hits = 0
    total = 0

    for case in sample:
        if not case.full_text or len(case.full_text) < 100:
            continue
        response = search_engine.search(case.full_text, filters=SearchFilters(), top_k=1, exclude_case_id=None)
        total += 1
        if response.results and response.results[0].case_id == case.id:
            hits += 1

    accuracy = hits / max(total, 1)
    logger.info("Self-retrieval accuracy", accuracy=f"{accuracy:.2%}")
    return accuracy


def _test_category_coherence(search_engine: SimilarCaseSearchEngine, session) -> dict:
    """Evaluate category coherence for main case types.

    Args:
        search_engine: SimilarCaseSearchEngine instance.
        session: SQLAlchemy session.

    Returns:
        Dictionary of coherence scores by case type.
    """
    scores = {}
    for case_type in ["Criminal", "Civil", "Writ"]:
        cases = session.query(Case).filter(Case.case_type == case_type).all()
        sample = random.sample(cases, min(20, len(cases)))
        total = 0
        matches = 0
        for case in sample:
            if not case.full_text or len(case.full_text) < 100:
                continue
            response = search_engine.search(
                case.full_text,
                filters=SearchFilters(case_type=case_type),
                top_k=5,
                exclude_case_id=case.id,
            )
            for result in response.results:
                total += 1
                if result.case_type == case_type:
                    matches += 1
        scores[case_type] = matches / max(total, 1)
        logger.info("Category coherence", case_type=case_type, score=f"{scores[case_type]:.2%}")
    return scores


def _test_statute_clustering(search_engine: SimilarCaseSearchEngine, session) -> dict:
    """Evaluate statute clustering for IPC 302 and NDPS cases.

    Args:
        search_engine: SimilarCaseSearchEngine instance.
        session: SQLAlchemy session.

    Returns:
        Dictionary with clustering scores.
    """
    scores = {}
    statute_tests = {
        "IPC Section 302": "IPC Section 302",
        "NDPS": "NDPS",
    }
    for label, keyword in statute_tests.items():
        cases = (
            session.query(Case)
            .outerjoin(Case.statutes)
            .filter(
                (Case.sections_invoked.any(keyword))
                | (Statute.statute_name.ilike(f"%{keyword}%"))
            )
            .all()
        )
        if not cases:
            scores[label] = 0.0
            continue
        sample = random.sample(cases, min(20, len(cases)))
        total = 0
        matches = 0
        for case in sample:
            if not case.full_text or len(case.full_text) < 100:
                continue
            response = search_engine.search(case.full_text, filters=SearchFilters(), top_k=5, exclude_case_id=case.id)
            for result in response.results:
                total += 1
                if keyword in (result.sections_invoked or []) or keyword in (result.statutes_cited or []):
                    matches += 1
        scores[label] = matches / max(total, 1)
        logger.info("Statute clustering", statute=label, score=f"{scores[label]:.2%}")
    return scores


def _test_filter_validation(search_engine: SimilarCaseSearchEngine, session) -> bool:
    """Validate filter behavior.

    Args:
        search_engine: SimilarCaseSearchEngine instance.
        session: SQLAlchemy session.

    Returns:
        True if filters validated successfully.
    """
    case = session.query(Case).filter(Case.court.isnot(None)).first()
    if not case or not case.full_text:
        return False

    filters = SearchFilters(court=case.court)
    response = search_engine.search(case.full_text, filters=filters, top_k=5, exclude_case_id=case.id)
    court_ok = all(result.court == case.court for result in response.results)

    case_type_ok = True
    if case.case_type:
        filters = SearchFilters(case_type=case.case_type)
        response = search_engine.search(case.full_text, filters=filters, top_k=5, exclude_case_id=case.id)
        case_type_ok = all(result.case_type == case.case_type for result in response.results)

    year_ok = True
    if case.date_of_judgment:
        year = case.date_of_judgment.year
        filters = SearchFilters(year_from=year - 1, year_to=year + 1)
        response = search_engine.search(case.full_text, filters=filters, top_k=5, exclude_case_id=case.id)
        for result in response.results:
            if result.date_of_judgment:
                result_year = int(result.date_of_judgment.split("-")[0])
                if not (year - 1 <= result_year <= year + 1):
                    year_ok = False

    logger.info("Filter validation", court=court_ok, case_type=case_type_ok, year=year_ok)
    return court_ok and case_type_ok and year_ok


def _test_performance(search_engine: SimilarCaseSearchEngine, cases: list[Case]) -> dict:
    """Benchmark search performance.

    Args:
        search_engine: SimilarCaseSearchEngine instance.
        cases: List of Case objects.

    Returns:
        Performance statistics.
    """
    sample = [case for case in random.sample(cases, min(20, len(cases))) if case.full_text]
    latencies = []
    for case in sample:
        start = time.time()
        search_engine.search(case.full_text, filters=SearchFilters(), top_k=5, exclude_case_id=case.id)
        latencies.append((time.time() - start) * 1000)

    stats = {
        "min_ms": float(np.min(latencies)) if latencies else 0.0,
        "max_ms": float(np.max(latencies)) if latencies else 0.0,
        "mean_ms": float(np.mean(latencies)) if latencies else 0.0,
        "p95_ms": float(np.percentile(latencies, 95)) if latencies else 0.0,
    }
    logger.info("Performance benchmark", **{k: f"{v:.0f}" for k, v in stats.items()})
    return stats


def _manual_spot_check(search_engine: SimilarCaseSearchEngine, cases: list[Case]) -> None:
    """Manual spot check for legal relevance.

    Args:
        search_engine: SimilarCaseSearchEngine instance.
        cases: List of Case objects.
    """
    sample = random.sample(cases, min(5, len(cases)))
    for case in sample:
        if not case.full_text or len(case.full_text) < 100:
            continue
        response = search_engine.search(case.full_text, filters=SearchFilters(), top_k=5, exclude_case_id=case.id)
        logger.info("Manual spot check", case_id=case.id, case_title=case.case_title)
        for result in response.results:
            logger.info("Result", rank=result.rank, case_id=result.case_id, title=result.case_title)
        if sys.stdin.isatty():
            input("Press Enter to continue...")
        else:
            logger.info("Skipping manual pause (non-interactive mode)")


if __name__ == "__main__":
    main()
