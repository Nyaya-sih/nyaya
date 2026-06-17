"""Embed legal KB chunks and build FAISS index."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import time
from typing import Any

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from tqdm import tqdm


ROOT = Path("legal_kb")
CHUNKS_DIR = ROOT / "chunks"
EMBED_DIR = ROOT / "embeddings"
FAISS_DIR = ROOT / "faiss"
INDEX_PATH = CHUNKS_DIR / "index.json"
MODEL_NAME = "sentence-transformers/multi-qa-mpnet-base-dot-v1"
BATCH_SIZE = 64
MAX_TOKENS = 512


@dataclass
class ActRuntime:
    slug: str
    chunk_count: int
    elapsed_sec: float


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def truncate_to_model_tokens(tokenizer, text: str, max_tokens: int) -> tuple[str, bool]:
    encoded = tokenizer(
        text,
        add_special_tokens=True,
        truncation=False,
        return_attention_mask=False,
        return_token_type_ids=False,
    )
    ids = encoded["input_ids"]
    if len(ids) <= max_tokens:
        return text, False

    trunc_ids = ids[:max_tokens]
    truncated_text = tokenizer.decode(trunc_ids, skip_special_tokens=True)
    return truncated_text, True


def main() -> None:
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    by_act = index["by_act"]
    target_acts = [
        slug for slug, meta in by_act.items() if int(meta.get("chunk_count", 0)) > 0
    ]

    model = SentenceTransformer(MODEL_NAME)
    tokenizer = model.tokenizer

    EMBED_DIR.mkdir(parents=True, exist_ok=True)
    FAISS_DIR.mkdir(parents=True, exist_ok=True)

    chunk_id_map: list[dict[str, Any]] = []
    chunk_text_lookup: dict[str, str] = {}
    all_vectors: list[np.ndarray] = []
    failed_embeddings: list[dict[str, str]] = []
    truncation_logs: list[dict[str, Any]] = []
    act_timings: list[ActRuntime] = []

    total_chunks = sum(int(by_act[s]["chunk_count"]) for s in target_acts)
    global_bar = tqdm(
        total=total_chunks, desc="Global embedding progress", unit="chunk"
    )

    faiss_idx_counter = 0
    overall_start = time.perf_counter()

    for slug in target_acts:
        act_path = CHUNKS_DIR / f"{slug}.jsonl"
        rows = load_jsonl(act_path)
        act_start = time.perf_counter()

        act_vectors: list[np.ndarray] = []
        act_bar = tqdm(total=len(rows), desc=f"Embedding {slug}", unit="chunk")

        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i : i + BATCH_SIZE]
            texts: list[str] = []
            batch_rows: list[dict[str, Any]] = []

            for row in batch:
                embed_input = f"{row['act_name']} | {row['section_or_article']} | {row['chunk_text']}"
                trunc_text, truncated = truncate_to_model_tokens(
                    tokenizer, embed_input, MAX_TOKENS
                )
                if truncated:
                    truncation_logs.append(
                        {
                            "chunk_id": row.get("chunk_id", ""),
                            "act_slug": slug,
                            "orig_tokens": len(
                                tokenizer(embed_input, add_special_tokens=True)[
                                    "input_ids"
                                ]
                            ),
                            "kept_tokens": MAX_TOKENS,
                        }
                    )
                texts.append(trunc_text)
                batch_rows.append(row)

            try:
                embs = model.encode(
                    texts,
                    batch_size=BATCH_SIZE,
                    show_progress_bar=False,
                    convert_to_numpy=True,
                    normalize_embeddings=False,
                )
            except Exception as exc:
                for row in batch_rows:
                    failed_embeddings.append(
                        {
                            "chunk_id": str(row.get("chunk_id", "")),
                            "reason": str(exc),
                        }
                    )
                act_bar.update(len(batch_rows))
                global_bar.update(len(batch_rows))
                continue

            for row, vec in zip(batch_rows, embs):
                vec = np.asarray(vec, dtype=np.float32)
                act_vectors.append(vec)
                all_vectors.append(vec)

                chunk_id_map.append(
                    {
                        "faiss_idx": faiss_idx_counter,
                        "chunk_id": row.get("chunk_id"),
                        "act_name": row.get("act_name"),
                        "act_slug": row.get("act_slug"),
                        "section_or_article": row.get("section_or_article"),
                        "section_title": row.get("section_title"),
                        "chapter_or_part": row.get("chapter_or_part"),
                        "year": row.get("year"),
                        "tier": row.get("tier"),
                        "is_superseded": row.get("is_superseded"),
                        "superseded_by": row.get("superseded_by"),
                        "mapped_to": row.get("mapped_to"),
                        "source_url": row.get("source_url"),
                        "jurisdiction": row.get("jurisdiction"),
                    }
                )
                chunk_text_lookup[str(row.get("chunk_id"))] = str(
                    row.get("chunk_text", "")
                )
                faiss_idx_counter += 1

            act_bar.update(len(batch_rows))
            global_bar.update(len(batch_rows))

        act_bar.close()

        if act_vectors:
            act_mat = np.vstack(act_vectors).astype(np.float32)
            np.save(EMBED_DIR / f"{slug}.npy", act_mat)
        else:
            np.save(EMBED_DIR / f"{slug}.npy", np.zeros((0, 768), dtype=np.float32))

        act_elapsed = time.perf_counter() - act_start
        act_timings.append(
            ActRuntime(slug=slug, chunk_count=len(rows), elapsed_sec=act_elapsed)
        )

    global_bar.close()

    if all_vectors:
        all_mat = np.vstack(all_vectors).astype(np.float32)
    else:
        all_mat = np.zeros((0, 768), dtype=np.float32)

    faiss.normalize_L2(all_mat)
    index_flat = faiss.IndexFlatIP(all_mat.shape[1] if all_mat.shape[0] else 768)
    if all_mat.shape[0] > 0:
        index_flat.add(all_mat)
    faiss.write_index(index_flat, str(FAISS_DIR / "legal_kb.index"))

    (FAISS_DIR / "chunk_id_map.json").write_text(
        json.dumps(chunk_id_map, indent=2), encoding="utf-8"
    )
    (FAISS_DIR / "chunk_text_lookup.json").write_text(
        json.dumps(chunk_text_lookup), encoding="utf-8"
    )

    # Validation queries
    test_queries = [
        "What is the punishment for murder in India",
        "Rights of arrested person",
        "Fundamental right to equality",
        "Consumer complaint procedure",
        "Bail conditions under BNSS",
    ]
    expected_hints = {
        test_queries[0]: ["bharatiya_nyaya_sanhita_2023", "indian_penal_code_1860"],
        test_queries[1]: [
            "bharatiya_nagarik_suraksha_sanhita_2023",
            "constitution_of_india",
            "code_of_criminal_procedure_1973",
        ],
        test_queries[2]: ["constitution_of_india"],
        test_queries[3]: ["consumer_protection_act_2019"],
        test_queries[4]: ["bharatiya_nagarik_suraksha_sanhita_2023"],
    }

    print("VALIDATION_RESULTS_START")
    for q in test_queries:
        q_emb = model.encode(
            [q], convert_to_numpy=True, show_progress_bar=False
        ).astype(np.float32)
        faiss.normalize_L2(q_emb)
        scores, idxs = index_flat.search(q_emb, 3)
        hits = []
        for score, idx in zip(scores[0], idxs[0]):
            if idx < 0 or idx >= len(chunk_id_map):
                continue
            meta = chunk_id_map[idx]
            hits.append((float(score), meta))

        print(f"Query: {q}")
        for score, meta in hits:
            print(
                "- "
                f"{meta['chunk_id']} | {meta['act_name']} | {meta['section_or_article']} | {score:.4f}"
            )

        if not hits or all(score < 0.3 for score, _ in hits):
            print("  FLAG: all top-3 scores < 0.3")

        present_slugs = {m["act_slug"] for _, m in hits}
        if not any(exp in present_slugs for exp in expected_hints[q]):
            print("  FLAG: expected relevant act missing in top-3")
    print("VALIDATION_RESULTS_END")

    total_time = time.perf_counter() - overall_start
    index_size = (FAISS_DIR / "legal_kb.index").stat().st_size

    print(f"TOTAL_VECTORS: {index_flat.ntotal}")
    print(f"INDEX_FILE_SIZE_BYTES: {index_size}")
    print(f"EMBEDDING_TIME_TOTAL_SEC: {total_time:.2f}")
    print("EMBEDDING_TIME_PER_ACT_SEC_START")
    for t in act_timings:
        print(f"{t.slug}: chunks={t.chunk_count}, sec={t.elapsed_sec:.2f}")
    print("EMBEDDING_TIME_PER_ACT_SEC_END")

    print("FAILED_EMBEDDINGS_START")
    if not failed_embeddings:
        print("none")
    else:
        for item in failed_embeddings:
            print(f"{item['chunk_id']} | {item['reason']}")
    print("FAILED_EMBEDDINGS_END")

    print(f"TRUNCATION_COUNT: {len(truncation_logs)}")
    if truncation_logs:
        trunc_log_path = FAISS_DIR / "truncation_log.json"
        trunc_log_path.write_text(
            json.dumps(truncation_logs, indent=2), encoding="utf-8"
        )
        print(f"TRUNCATION_LOG_FILE: {trunc_log_path}")

    print("OUTPUT_FILES_WRITTEN")
    print("- legal_kb/faiss/legal_kb.index")
    print("- legal_kb/faiss/chunk_id_map.json")
    print("- legal_kb/faiss/chunk_text_lookup.json")


if __name__ == "__main__":
    main()
