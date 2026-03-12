"""Tests for EmbeddingGenerator."""

import numpy as np

from src.features.similar_cases.embedding_generator import EmbeddingGenerator


class DummyEmbeddingResponse:
    """Dummy embedding response object."""

    def __init__(self, embedding):
        self.data = [type("obj", (), {"embedding": embedding})()]


class DummyEmbeddingsClient:
    """Dummy embeddings client."""

    def __init__(self):
        self.calls = 0

    def create(self, model, input):
        self.calls += 1
        embedding = [0.01] * 3072
        return DummyEmbeddingResponse(embedding)


class DummyOpenAIClient:
    """Dummy OpenAI client."""

    def __init__(self):
        self.embeddings = DummyEmbeddingsClient()


class DummyCase:
    """Dummy case object."""

    def __init__(self):
        self.id = 123
        self.case_title = "State v. Doe"
        self.petitioner = ["State"]
        self.respondent = ["John Doe"]
        self.charges = ["IPC Section 302"]
        self.key_arguments_petitioner = "Argument A"
        self.key_arguments_respondent = "Argument B"
        self.court = "Delhi High Court"
        self.statutes_cited = ["IPC"]
        self.sections_invoked = ["IPC Section 302"]
        self.court_reasoning = "Reasoning"
        self.precedents = []
        self.case_type = "Criminal"
        self.verdict = "Convicted"
        self.sentence = "Life"
        self.headnotes = ["Headnote"]
        self.date_of_judgment = type("obj", (), {"year": 2024})()


def test_build_factual_text_with_all_fields():
    """All fields present -> correct format."""
    generator = EmbeddingGenerator(DummyOpenAIClient())
    case = DummyCase()
    text = generator.build_factual_text(case)
    assert "Case Title" in text
    assert "Petitioner" in text
    assert "Respondent" in text


def test_build_factual_text_with_missing_fields():
    """None fields -> graceful skip."""
    generator = EmbeddingGenerator(DummyOpenAIClient())
    case = DummyCase()
    case.case_title = None
    case.petitioner = None
    case.respondent = None
    text = generator.build_factual_text(case)
    assert "Case Title" not in text


def test_build_legal_text():
    """Statutes and sections included."""
    generator = EmbeddingGenerator(DummyOpenAIClient())
    case = DummyCase()
    text = generator.build_legal_text(case)
    assert "Statutes" in text
    assert "Sections" in text


def test_build_outcome_text():
    """Verdict and case_type included."""
    generator = EmbeddingGenerator(DummyOpenAIClient())
    case = DummyCase()
    text = generator.build_outcome_text(case)
    assert "Verdict" in text
    assert "Case Type" in text


def test_truncate_to_tokens():
    """Long text gets truncated to max_tokens."""
    generator = EmbeddingGenerator(DummyOpenAIClient())
    text = "word " * 5000
    truncated = generator._truncate_to_tokens(text, 100)
    assert len(generator.encoder.encode(truncated)) <= 100


def test_get_embedding_returns_numpy_array():
    """Mock API -> returns np.ndarray shape (3072,)."""
    generator = EmbeddingGenerator(DummyOpenAIClient())
    embedding = generator._get_embedding("test")
    assert isinstance(embedding, np.ndarray)
    assert embedding.shape == (3072,)


def test_get_embedding_empty_text():
    """Empty text -> zero vector."""
    generator = EmbeddingGenerator(DummyOpenAIClient())
    embedding = generator._get_embedding("")
    assert np.allclose(embedding, np.zeros(3072))


def test_generate_case_embedding_makes_3_calls():
    """Exactly 3 API calls per case."""
    client = DummyOpenAIClient()
    generator = EmbeddingGenerator(client)
    case = DummyCase()
    generator.generate_case_embedding(case)
    assert client.embeddings.calls == 3


def test_combined_embedding_normalized():
    """Combined vector has unit norm."""
    generator = EmbeddingGenerator(DummyOpenAIClient())
    case = DummyCase()
    embedding = generator.generate_case_embedding(case)
    norm = np.linalg.norm(embedding.combined_embedding)
    assert np.isclose(norm, 1.0)


def test_estimated_cost_calculation():
    """Token count -> correct cost."""
    generator = EmbeddingGenerator(DummyOpenAIClient())
    generator.total_tokens_used = 1_000_000
    assert np.isclose(generator.estimated_cost, 0.13)
