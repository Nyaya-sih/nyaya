"""
Refresh Qdrant payloads for all indexed cases without re-embedding.

This updates statutes_cited and related metadata payload fields.
"""

from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm

from src.config.settings import settings
from src.database.models import Case
from src.features.similar_cases.vector_store import VectorStore


def main() -> None:
    """Refresh payloads in Qdrant collections."""
    engine = create_engine(settings.database_url, echo=False)
    session_local = sessionmaker(bind=engine)
    session = session_local()
    vector_store = VectorStore(host=settings.qdrant_host, port=settings.qdrant_port)

    try:
        cases = session.query(Case).filter(Case.validation_status != "invalid").all()
        if not cases:
            logger.warning("No cases found for payload refresh")
            return

        logger.info("Refreshing payloads", count=len(cases))
        for case in tqdm(cases, desc="Updating payloads"):
            payload = vector_store._build_payload(case)
            case_id = payload.get("case_id")
            if case_id is None:
                continue

            for collection in [
                vector_store.COLLECTION_COMBINED,
                vector_store.COLLECTION_FACTUAL,
                vector_store.COLLECTION_LEGAL,
            ]:
                vector_store.client.set_payload(
                    collection_name=collection,
                    payload=payload,
                    points=[case_id],
                )

        logger.info("Payload refresh complete")
    finally:
        session.close()


if __name__ == "__main__":
    main()
