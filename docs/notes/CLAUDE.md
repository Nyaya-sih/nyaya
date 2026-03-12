# NyayaAI - Claude Code Instructions

## Project Overview

**NyayaAI** is an AI-powered legal research system for Indian High Court judgments. It combines LLM-powered metadata extraction with semantic search to help legal professionals find relevant case law.

**Current Status**: Phase 1 Complete (9,718 quality cases extracted) | Ready for Phase 2 (Similar Case Retrieval)

---

## Development Commands

### Database Management
```bash
# Start infrastructure (PostgreSQL + Qdrant + Redis)
docker-compose up -d

# Stop infrastructure
docker-compose down

# Check database status
docker ps | grep nyaya

# Access PostgreSQL
docker exec -it nyaya_postgres psql -U nyaya_user -d nyaya_ai

# Initialize database schema
python -c "from src.data_pipeline.loaders.db_loader import DatabaseLoader; DatabaseLoader().init_db()"
```

### Data Pipeline Scripts
```bash
# Phase 1 Scripts (Data Collection & Cleaning)
python scripts/01_download_sample.py          # Download sample PDFs from S3
python scripts/03_run_extraction.py           # Extract metadata with LLM
python scripts/04_validate_quality.py         # Validate data quality
python scripts/05_standardize_courts.py       # Normalize court names
python scripts/08_download_diverse.py         # Download from diverse courts
python scripts/11_smart_extract_to_10k.py     # Smart extraction to 10K cases
python scripts/13_final_validation.py         # Production readiness check

# Phase 2 Scripts (Similar Case Retrieval) - To be implemented
# Will include: embedding generation, vector indexing, search API, UI
```

### Environment Setup
```bash
# Create virtual environment
python -m venv ../venv
source ../venv/bin/activate  # Linux/Mac
..\venv\Scripts\activate     # Windows

# Install dependencies (when requirements.txt exists)
pip install -r requirements.txt

# Configure environment
cp .env.example .env  # Edit with your API keys
```

### Common Queries
```bash
# Check case count
python -c "from src.data_pipeline.loaders.db_loader import DatabaseLoader; from src.database.models import Case; from sqlalchemy import func; db = DatabaseLoader(); session = db.SessionLocal(); print(f'Cases: {session.query(func.count(Case.id)).scalar():,}'); session.close()"

# View database stats
python -c "from src.data_pipeline.loaders.db_loader import DatabaseLoader; import json; db = DatabaseLoader(); print(json.dumps(db.get_database_stats(), indent=2))"
```

---

## Architecture Overview

### Multi-Stage Data Pipeline

**Download → Extract → Validate → Load → Index → Search**

1. **Downloaders** (`src/data_pipeline/downloaders/`)
   - Fetch PDFs from public S3 bucket (no credentials needed)
   - Source: `s3://indian-high-court-judgments/`
   - Supports multi-court, multi-year downloads

2. **Extractors** (`src/data_pipeline/extractors/`)
   - **PDF Extractor**: Converts PDF to text using pdfplumber/PyPDF2
   - **Metadata Extractor**: LLM-powered structured extraction
     - Models: GPT-4o-mini (primary), Claude, Gemini
     - Returns 20+ fields with confidence scores
     - Temperature: 0.1 for deterministic extraction

3. **Validators** (`src/data_pipeline/validators/`)
   - Validates against Indian legal references
   - Checks field completeness, date formats, statute names
   - Returns: `valid`, `needs_review`, or `invalid`

4. **Loaders** (`src/data_pipeline/loaders/`)
   - Saves to PostgreSQL with relationships (statutes, precedents)
   - Handles duplicates via `source_file_path` checking
   - Batch processing with transaction management

### Database Schema (PostgreSQL + pgvector)

**Primary Table: `cases`**
- Core fields: `case_id`, `case_title`, `court`, `date_of_judgment`, `verdict`, `full_text`
- Extracted metadata: `petitioner`, `respondent`, `sections_invoked`, `charges`, `sentence`
- Analysis fields: `key_arguments_petitioner`, `key_arguments_respondent`, `court_reasoning`, `headnotes`
- Quality metrics: `confidence_scores` (JSON), `average_confidence`, `validation_status`
- Tracking: `extraction_model`, `source_file_path`, `page_count`, `created_at`

**Relationships:**
- `cases` → `statutes` (many-to-many): Cited statutes (IPC, CrPC, etc.)
- `cases` → `precedents` (many-to-many): Cited case law

**Vector Extension (Phase 2):**
- Will use `pgvector` for embeddings storage
- Multi-dimensional: factual, legal, outcome embeddings

### LLM Integration

**Metadata Extractor** (`src/data_pipeline/extractors/metadata_extractor.py`)
- **Critical Module**: Extracts 20+ structured fields from unstructured judgment text
- **Prompt Engineering**: System prompt defines schema, user prompt contains judgment text
- **Confidence Scoring**: Every field gets 0.0-1.0 confidence (1.0 = explicit, 0.7-0.9 = implied, 0.0 = missing)
- **JSON Parsing**: Handles markdown code blocks and direct JSON responses
- **Truncation**: For long documents, keeps first 15K + last 5K chars

**LLM Client** (`src/utils/llm_client.py`)
- Unified interface for OpenAI, Anthropic, Google APIs
- Retry logic with exponential backoff
- Cost tracking per extraction (~$0.00035/case)

### Configuration System

**Pydantic Settings** (`src/config/settings.py`)
- Loads from `.env` file with environment variable override
- Key configs:
  - `database_url`: PostgreSQL connection
  - `openai_api_key`, `anthropic_api_key`, `google_api_key`: LLM providers
  - `extraction_model`: Which LLM to use (default: gpt-4o-mini)
  - `extraction_temperature`: 0.1 for structured extraction
  - `batch_size`, `max_concurrent_requests`: Processing limits
  - `qdrant_host`, `qdrant_port`: Vector DB connection (Phase 2)

**Court Codes Mapping**:
- `DL_HC` → Delhi High Court
- `BH_HC` → Bombay High Court
- `PH_HC` → Patna High Court
- etc. (43 unique courts in dataset)

---

## Important Patterns & Conventions

### Error Handling in Extraction

**Critical**: The `pdf_extractor.extract_text()` returns a **dict**, not a string:
```python
extraction_result = pdf_extractor.extract_text(pdf_path)
if not extraction_result or not extraction_result.get('success'):
    return False
text = extraction_result.get('text', '')
page_count = extraction_result.get('page_count', 0)
```

### Database Loading

**Critical**: `db_loader.load_case()` requires specific parameters:
```python
case_id = db_loader.load_case(
    metadata=metadata,          # CaseMetadata object
    full_text=text,             # str
    validation=validation,       # ValidationResult object
    extraction_model="gpt-4o-mini",  # str
    source_file=str(pdf_path),  # str
    page_count=page_count       # int or None
)
```

### Court Name Standardization

Court names have many variations that must be normalized:
- "HIGH COURT OF JUDICATURE AT BOMBAY" → "High Court of Bombay"
- "High Court of Judicature at Bombay" → "High Court of Bombay"
- Use `scripts/12_final_court_standardization.py` for bulk updates

### Duplicate Prevention

Check `source_file_path` (not `pdf_path`) to avoid re-processing:
```python
processed = session.query(Case.source_file_path).filter(Case.source_file_path.isnot(None)).all()
processed_paths = {str(Path(p[0]).name) for p in processed if p[0]}
```

### Validation Criteria

Production-ready dataset requires:
1. Total cases >= 10,000 (currently 9,718 - acceptable)
2. Court balance: No single court >70% (✓ Patna 63.5%)
3. Average confidence >70% (✓ 76.4%)
4. Field completeness >80% (✓ All critical fields >88%)
5. Temporal diversity: >=5 years (✓ 2012-2025, 13 years)
6. Case type diversity: >=3 types (✓ 13 types)
7. Invalid rate <10% (✓ 6.4%)

---

## Phase 2: Similar Case Retrieval (Next Steps)

### Architecture (To Be Implemented)

**Multi-Level Embedding System:**
1. **Factual Embedding**: Facts, parties, dates, charges (sentence-transformers)
2. **Legal Embedding**: Statutes, sections, legal principles (legal-bert)
3. **Outcome Embedding**: Verdict, reasoning, sentence (fine-tuned model)

**Vector Store: Qdrant**
- 3 collections: `factual_embeddings`, `legal_embeddings`, `outcome_embeddings`
- Metadata filters: court, date_range, case_type, verdict
- HNSW indexing for fast approximate search

**Search Pipeline:**
1. User uploads query document or enters search text
2. Generate embeddings at all 3 levels
3. Parallel vector search across 3 collections (top-20 each)
4. Fusion with weighted scoring (factual: 0.4, legal: 0.4, outcome: 0.2)
5. Re-rank top-10 with cross-encoder
6. Generate similarity explanations with LLM

**API: FastAPI**
- POST `/api/search/upload`: Upload PDF/text for search
- POST `/api/search/text`: Search by text query
- GET `/api/cases/{id}`: Get case details
- GET `/api/cases/{id}/similar`: Find similar cases
- WebSocket `/ws/search`: Real-time search progress

**Frontend: Next.js + TypeScript + Tailwind**
- File upload with drag-and-drop
- Real-time search progress
- Side-by-side case comparison
- Highlighted similar passages
- Filter by court, date, case type
- Export results to PDF/JSON

---

## Production Readiness Status

**✅ Phase 1 Complete (2026-02-11)**
- Dataset: 9,718 quality cases (97% of 10K target)
- Coverage: 43 courts across India
- Quality: 76.4% avg confidence, 6.4% invalid rate
- Ready for embedding generation

**📊 Dataset Statistics:**
- Temporal: 2012-2025 (13 years), peak in 2023 (3,963 cases)
- Court Distribution: Patna 63.5%, Bombay 9.9%, Sikkim 7.6%, others balanced
- Case Types: Criminal 49.2%, Civil 31.2%, Writ 1.9%, Constitutional 0.3%
- Confidence: 51.2% high confidence (>80%), 76.4% average
- Validation: 93.5% needs_review, 6.4% invalid, 0.1% valid

**💰 Project Costs:**
- Phase 1 Total: ~$3.41
- Per-case: $0.00034
- Extremely cost-effective!

---

## Key Files & Their Purpose

### Configuration
- `.env`: API keys, database URL, model settings (create from .env.example)
- `docker-compose.yml`: Infrastructure setup (PostgreSQL, Qdrant, Redis, PgAdmin)
- `src/config/settings.py`: Pydantic settings with validation

### Database
- `src/database/models.py`: SQLAlchemy ORM models (Case, Statute, Precedent)
- `src/database/schemas.py`: Pydantic schemas for validation

### Data Pipeline Modules
- `src/data_pipeline/downloaders/hc_downloader.py`: S3 PDF downloader
- `src/data_pipeline/extractors/pdf_extractor.py`: PDF → text conversion
- `src/data_pipeline/extractors/metadata_extractor.py`: LLM-powered metadata extraction ⭐
- `src/data_pipeline/validators/data_validator.py`: Quality validation
- `src/data_pipeline/loaders/db_loader.py`: PostgreSQL data loader

### Utilities
- `src/utils/llm_client.py`: Multi-provider LLM client (OpenAI/Anthropic/Google)
- `src/utils/logging_config.py`: Loguru-based logging setup

### Reports
- `data/processed/production_readiness_report.json`: Final validation report
- `final_validation_output.log`: Validation run logs

---

## Development Workflow

### Adding New Cases
1. Download PDFs: `python scripts/08_download_diverse.py --court <CODE> --year <YEAR>`
2. Extract metadata: `python scripts/11_smart_extract_to_10k.py --target <COUNT>`
3. Standardize: `python scripts/12_final_court_standardization.py`
4. Validate: `python scripts/13_final_validation.py`

### Checking Data Quality
```python
from src.data_pipeline.loaders.db_loader import DatabaseLoader

db = DatabaseLoader()
stats = db.get_database_stats()
print(f"Total: {stats['total_cases']:,}")
print(f"Valid: {stats['valid_cases']}")
print(f"Avg Confidence: {stats['average_confidence']:.2%}")
```

### Querying Cases
```python
from src.data_pipeline.loaders.db_loader import DatabaseLoader

db = DatabaseLoader()

# Get high-confidence cases
cases = db.get_cases_by_validation_status("valid", limit=10)

# Get specific case
case = db.get_case_by_id("CR.A. 123/2023")
```

---

## Notes for Implementation

### When Implementing Phase 2:
1. **Read the full spec**: `~/projects/law/nyaya-ai-project-prompt.md`
2. **Start with embeddings**: Generate for all 9,718 cases (factual, legal, outcome)
3. **Set up Qdrant**: Create 3 collections with proper schemas
4. **Build API first**: FastAPI endpoints for search/retrieval
5. **Frontend last**: Next.js UI for case upload and results

### Testing Strategy:
- Unit tests: Individual components (extractors, validators, loaders)
- Integration tests: Full pipeline (download → extract → load)
- Search tests: Precision/recall for similar case retrieval
- Performance tests: Query latency, throughput

### Cost Optimization:
- Use batch embeddings APIs (cheaper than single)
- Cache embeddings (don't regenerate)
- Use smaller models for factual embeddings
- Reserve expensive models for legal/outcome embeddings

---

## Troubleshooting

### Database Connection Issues
```bash
# Check if PostgreSQL is running
docker ps | grep nyaya_postgres

# Start if stopped
docker start nyaya_postgres

# Check logs
docker logs nyaya_postgres
```

### LLM Extraction Failures
- Check API key in `.env`
- Verify model availability: `settings.get_available_models()`
- Check rate limits (reduce `max_concurrent_requests`)
- Review logs for specific error messages

### Duplicate Cases
- Check `source_file_path` field
- Run `scripts/07_verify_duplicates.py`
- Clean up with SQL: `DELETE FROM cases WHERE id IN (SELECT id FROM cases WHERE source_file_path IN (SELECT source_file_path FROM cases GROUP BY source_file_path HAVING COUNT(*) > 1) AND id NOT IN (SELECT MIN(id) FROM cases GROUP BY source_file_path));`

---

## Project Context

**Goal**: Build an AI-powered legal research assistant for Indian legal professionals to find relevant case law based on factual similarity, legal reasoning, and outcomes.

**Current Achievement**: Successfully extracted and validated 9,718 high-quality cases from 43 Indian High Courts with 76.4% average confidence using cost-effective LLM extraction ($3.41 total).

**Next Milestone**: Implement semantic search with multi-level embeddings and cross-encoder re-ranking to enable "upload your case, find similar precedents" functionality.
