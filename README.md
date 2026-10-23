# Nyaya AI

Nyaya AI is an explainable legal research and courtroom-analysis platform for Indian legal materials. It combines retrieval, role-based analysis, rebuttal generation, synthesis, and a live courtroom interface so users can inspect not only the conclusion, but also the evidence and reasoning behind it.

## What It Includes

- FastAPI backend for legal search, assistant queries, case analysis, outcome tendencies, and courtroom runs.
- Next.js frontend with the courtroom workspace, agent inspector, public explanations, search, and case views.
- PostgreSQL with `pgvector` for structured data and embeddings.
- Redis for application/runtime support.
- Qdrant for vector retrieval.
- Evidence-aware courtroom roles including judge, petitioner, respondent, and synthesis.
- Retrieval and courtroom sample documents under `frontend/public/samples/`.

## Repository Layout

```text
src/                 FastAPI backend and domain logic
frontend/             Next.js frontend
tests/               Backend and workflow tests
scripts/             Data, retrieval, indexing, and demo utilities
legal_kb/             Legal knowledge-base assets and manifests
docker-compose.yml    PostgreSQL, Redis, Qdrant, and pgAdmin services
```

## Quick Start

### 1. Configure the environment

```bash
cp .env.template .env
```

Add the required model keys to `.env`. Do not commit `.env` or credentials.

### 2. Start infrastructure

```bash
docker compose up -d postgres redis qdrant
```

Optional pgAdmin is available at `http://localhost:5050`.

### 3. Install backend dependencies

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Start the API

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

## Courtroom Demo

The courtroom flow can be exercised with the generated sample documents and the frontend courtroom route:

```text
http://localhost:3000/courtroom
```

The interface exposes the active roles, streamed events, evidence, public explanation, and final synthesis. The backend sample-generation utilities are available at:

```bash
python scripts/generate_courtroom_sample.py --help
python scripts/generate_retrieval_demo.py --help
```

## Testing

Run the backend test suite from the repository root:

```bash
pytest
```

Run frontend checks:

```bash
cd frontend
npm run lint
npm run build
```

## Data And Credentials

The repository contains code, manifests, sample fixtures, and public demo assets. Large datasets, local databases, API keys, `.env` files, generated caches, and runtime outputs should remain local. Review `.gitignore` before adding new generated artifacts.

## Status

Nyaya AI is an active research and development project. Retrieval quality, model routing, courtroom orchestration, and public explanations are under continuous evaluation through the tests and evaluation scripts in this repository.
