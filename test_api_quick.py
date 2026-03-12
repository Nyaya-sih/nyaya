"""Quick API functionality test."""
import sys
from openai import OpenAI
from src.config.settings import settings
from src.features.similar_cases.search_engine import SimilarCaseSearchEngine, SearchFilters

def main():
    print("=" * 60)
    print("QUICK API TEST")
    print("=" * 60)

    # Test 1: Initialize search engine
    print("\n[1/4] Initializing search engine...")
    try:
        client = OpenAI(api_key=settings.openai_api_key)
        engine = SimilarCaseSearchEngine(client)
        print("✓ Search engine initialized")
        print(f"  - Reranker enabled: {engine.reranker is not None}")
    except Exception as e:
        print(f"✗ Failed: {e}")
        sys.exit(1)

    # Test 2: Check Qdrant connection
    print("\n[2/4] Checking Qdrant collections...")
    try:
        stats = engine.vector_store.get_collection_stats()
        print("✓ Qdrant connected")
        for collection, info in stats.items():
            print(f"  - {collection}: {info['points_count']:,} cases")
    except Exception as e:
        print(f"✗ Failed: {e}")
        sys.exit(1)

    # Test 3: Simple search
    print("\n[3/4] Running test search...")
    try:
        query = "The accused was charged under IPC Section 302 for murder"
        response = engine.search(query, filters=SearchFilters(), top_k=3)
        print(f"✓ Search completed in {response.search_time_ms:.0f}ms")
        print(f"  - Results found: {response.total_results}")
        if response.results:
            print(f"  - Top result: {response.results[0].case_title[:80]}...")
            print(f"  - Similarity: {response.results[0].combined_score:.3f}")
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Test 4: Check API can import
    print("\n[4/4] Checking FastAPI app...")
    try:
        from src.api.main import app
        print("✓ FastAPI app imports successfully")
    except Exception as e:
        print(f"✗ Failed: {e}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED - API is ready!")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Start API: uvicorn src.api.main:app --reload --port 8000")
    print("  2. Test: curl http://localhost:8000/health")
    print("  3. Run quality tests: python scripts/14_test_search_quality.py")

if __name__ == "__main__":
    main()
