# Run These (Local Setup + Launch)

This is a practical, copy-paste runbook to get NyayaAI running locally.

## 0) Where to run from

All commands below assume you are in:

```bash
cd /home/psycho/projects/law/nyaya-ai
```

## 1) One-time local setup

### 1.1 Create and activate virtualenv

```bash
python -m venv venv
source venv/bin/activate
```

### 1.2 Install Python dependencies

```bash
pip install -r requirements.txt
```

### 1.3 Configure environment file

```bash
cp .env.template .env
```

Then open `.env` and set at least:

- `OPENAI_API_KEY` (required for embedding/query flows)
- any DB host/port overrides if your Docker ports differ
- recommended retrieval knobs for local performance/quality balance:
  - `VECTOR_SEARCH_CANDIDATES=18`
  - `RERANKER_CANDIDATE_LIMIT=14`
  - `ENABLE_HYBRID_RETRIEVAL=true`
  - `HYBRID_EXTRA_CANDIDATES=0`

## 2) Start infrastructure (Postgres + Qdrant + Redis)

```bash
docker-compose up -d
docker-compose ps
```

Expected: services are `Up` for postgres, qdrant, redis.

## 3) Initialize database schema

```bash
PYTHONPATH=. venv/bin/python -c "from src.data_pipeline.loaders.db_loader import DatabaseLoader; DatabaseLoader().init_db()"
```

## 4) Optional: sanity checks

### 4.1 Run full tests

```bash
PYTHONPATH=. venv/bin/pytest tests/ -q
```

### 4.2 Verify vector/db index integrity

```bash
PYTHONPATH=. venv/bin/python scripts/16_verify_index_integrity.py
```

## 5) If you need to (re)build retrieval indexes

Only do this if your local DB/Qdrant are fresh or empty.

### 5.1 Generate core embeddings

```bash
PYTHONPATH=. venv/bin/python scripts/13_generate_embeddings.py --yes --batch-size 32
```

### 5.2 Generate fulltext-lite embeddings

```bash
PYTHONPATH=. venv/bin/python scripts/14_generate_fulltext_embeddings.py --yes --batch-size 32
```

### 5.3 Sync + rebuild manifest

```bash
PYTHONPATH=. venv/bin/python scripts/18_sync_vector_index.py
PYTHONPATH=. venv/bin/python scripts/19_rebuild_embedding_manifest.py
PYTHONPATH=. venv/bin/python scripts/16_verify_index_integrity.py
```

## 6) Start backend API

In terminal 1:

```bash
cd /home/psycho/projects/law/nyaya-ai
source venv/bin/activate
PYTHONPATH=. venv/bin/uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

Quick health check:

```bash
curl http://localhost:8000/health
```

## 7) Start frontend

In terminal 2:

```bash
cd /home/psycho/projects/law/nyaya-ai/frontend
npm install
npm run dev
```

Open: `http://localhost:3000`

## 8) Quick retrieval quality/perf checks (optional)

```bash
cd /home/psycho/projects/law/nyaya-ai
PYTHONPATH=. venv/bin/python scripts/17_eval_retrieval_quality.py --max-queries 200
PYTHONPATH=. venv/bin/python scripts/15_benchmark_search.py --quick
```

Reports written to:

- `data/processed/retrieval_eval_report.json`
- `data/processed/benchmark_results.json`

## 9) Stop everything

### 9.1 Stop frontend/API

Use `Ctrl+C` in the running terminal windows.

### 9.2 Stop Docker services

```bash
cd /home/psycho/projects/law/nyaya-ai
docker-compose down
```

## Common gotchas

- If API import errors occur, ensure `PYTHONPATH=.` is set.
- If `OPENAI_API_KEY` is missing, embedding/query features will fail.
- If `/cases/{id}/similar` returns empty unexpectedly, re-run index integrity and ensure Qdrant collections are populated.
- If port conflicts occur, change `--port` for uvicorn or free occupied ports.
