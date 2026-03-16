"""Tests for VectorStore."""

from datetime import date

import numpy as np

from src.features.similar_cases.vector_store import VectorStore, SearchResult


class DummyCollectionInfo:
    """Dummy collection info."""

    def __init__(self):
        self.vectors_count = 10
        self.points_count = 10


class DummyCollections:
    """Dummy collections wrapper."""

    def __init__(self, names):
        self.collections = [type("obj", (), {"name": name})() for name in names]


class DummySearchHit:
    """Dummy search hit."""

    def __init__(self, payload, score):
        self.payload = payload
        self.score = score


class DummyQdrantClient:
    """Fake Qdrant client for tests."""

    def __init__(self):
        self.created_collections = []
        self.payload_indexes = []
        self.last_search_filter = None

    def get_collections(self):
        return DummyCollections([])

    def create_collection(self, collection_name, vectors_config):
        self.created_collections.append(collection_name)

    def delete_collection(self, collection_name):
        return None

    def create_payload_index(self, collection_name, field_name, field_schema):
        self.payload_indexes.append((collection_name, field_name, field_schema))

    def upsert(self, collection_name, points):
        return None

    def search(self, collection_name, query_vector, limit, query_filter=None):
        self.last_search_filter = query_filter
        payload = {
            "case_id": 1,
            "case_title": "Case",
            "court": "Court",
            "date_of_judgment": "2024-01-01",
            "case_type": "Criminal",
            "verdict": "Convicted",
        }
        return [DummySearchHit(payload, 0.9)]

    def get_collection(self, collection_name):
        return DummyCollectionInfo()


class DummyCase:
    """Dummy case object."""

    def __init__(self):
        self.id = 1
        self.case_title = "Test"
        self.court = "Court"
        self.date_of_judgment = date(2024, 1, 1)
        self.case_type = "Criminal"
        self.verdict = "Convicted"
        self.statutes_cited = None
        self.sections_invoked = None
        self.charges = None
        self.key_arguments_petitioner = None
        self.key_arguments_respondent = None
        self.court_reasoning = None
        self.headnotes = None
        self.full_text = None
        self.average_confidence = None
        self.validation_status = None
        self.source_file_path = None
        self.precedents = []


def test_create_collections():
    """Collections created with correct config."""
    store = VectorStore()
    store.client = DummyQdrantClient()
    store.create_collections(recreate=False)
    assert store.COLLECTION_COMBINED in store.client.created_collections


def test_build_payload_handles_none():
    """None fields -> empty string/list."""
    store = VectorStore()
    payload = store._build_payload(DummyCase())
    assert payload["statutes_cited"] == []
    assert payload["case_title"] == "Test"


def test_build_payload_date_formats():
    """Date -> string, year -> int."""
    store = VectorStore()
    payload = store._build_payload(DummyCase())
    assert payload["date_of_judgment"] == "2024-01-01"
    assert payload["year"] == 2024


def test_search_returns_search_results():
    """Results are SearchResult objects."""
    store = VectorStore()
    store.client = DummyQdrantClient()
    results = store.search(np.zeros(3072))
    assert isinstance(results[0], SearchResult)


def test_search_with_court_filter():
    """Filter applied correctly."""
    store = VectorStore()
    store.client = DummyQdrantClient()
    store.search(np.zeros(3072), court_filter="Court")
    assert store.client.last_search_filter is not None


def test_search_excludes_case_id():
    """Query case not in results."""
    store = VectorStore()
    store.client = DummyQdrantClient()
    store.search(np.zeros(3072), exclude_case_id=1)
    assert store.client.last_search_filter is not None


def test_get_collection_stats():
    """Returns dict with expected keys."""
    store = VectorStore()
    store.client = DummyQdrantClient()
    stats = store.get_collection_stats()
    assert store.COLLECTION_COMBINED in stats


def test_search_across_collections_deduplicates_by_best_score():
    """Cross-collection search should keep best score per case ID."""

    class MultiClient(DummyQdrantClient):
        def search(self, collection_name, query_vector, limit, query_filter=None):
            if collection_name == VectorStore.COLLECTION_COMBINED:
                return [
                    DummySearchHit(
                        {
                            "case_id": 1,
                            "case_title": "Case One",
                            "court": "Court",
                            "date_of_judgment": "2024-01-01",
                            "case_type": "Criminal",
                            "verdict": "Convicted",
                        },
                        0.6,
                    )
                ]
            return [
                DummySearchHit(
                    {
                        "case_id": 1,
                        "case_title": "Case One",
                        "court": "Court",
                        "date_of_judgment": "2024-01-01",
                        "case_type": "Criminal",
                        "verdict": "Convicted",
                    },
                    0.8,
                ),
                DummySearchHit(
                    {
                        "case_id": 2,
                        "case_title": "Case Two",
                        "court": "Court",
                        "date_of_judgment": "2023-01-01",
                        "case_type": "Civil",
                        "verdict": "Allowed",
                    },
                    0.7,
                ),
            ]

    store = VectorStore()
    store.client = MultiClient()

    merged = store.search_across_collections(
        query_embedding=np.zeros(3072),
        collections=[store.COLLECTION_COMBINED, store.COLLECTION_LEGAL],
        top_k_each=5,
    )
    assert len(merged) == 2
    assert merged[0].case_id == 1
    assert merged[0].similarity_score == 0.8
