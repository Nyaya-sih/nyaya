# NyayaAI - AI-Powered Legal Research System

**Current Phase:** Phase 1.5 - Data Cleanup & Diversification 🔄

AI-powered data pipeline for extracting and structuring Indian High Court judgments.

## Project Status

- ✅ **Phase 1:** Data Foundation (8,020 cases extracted)
- 🔄 **Phase 1.5:** Data Cleanup & Diversification (In Progress)
  - ✅ Phase A: Cleanup Complete (standardization, deduplication)
  - 🔄 Phase B: Diversification In Progress (adding 3,500 cases)
  - ⏳ Phase C: Final Validation (pending)
- ⏳ **Phase 2:** Similar Case Retrieval (Next)
- ⏳ **Phase 3:** RAG-Powered Q&A System
- ⏳ **Phase 4:** Simulated Courtroom

## Overview

NyayaAI is a comprehensive legal research system built on a robust, production-ready data cleaning pipeline that downloads, extracts, and structures Indian court case documents from public AWS S3 data.

### Phase 1: Initial Data Collection ✅

Built the foundational pipeline with 8,020 cases from Indian High Courts.

### Key Features

- ✅ **S3 Downloader**: Downloads High Court judgments from public AWS bucket (no credentials needed)
- ✅ **PDF Text Extraction**: Extracts clean text from legal PDFs with multiple fallback strategies
- ✅ **LLM-Powered Metadata Extraction**: Uses GPT-4o-mini/Claude/Gemini to extract structured case metadata
- ✅ **Data Validation**: Validates extracted data against known legal references
- ✅ **PostgreSQL Storage**: Stores clean, structured data with proper indexing
- ✅ **Quality Metrics**: Tracks confidence scores and extraction quality
- ✅ **Data Cleanup Pipeline**: Standardization, deduplication, quality improvement
- ✅ **Diversification System**: Multi-court balanced dataset construction

### Phase 1.5: Data Cleanup & Diversification 🔄

**Goal:** Transform initial dataset into production-ready legal research database.

**Phase A - Cleanup (COMPLETE ✅):**
- ✅ Standardized 20 court name variations → 6 canonical names
- ✅ Removed 321 duplicate cases
- ✅ Reprocessing 822 invalid/low-confidence cases (in progress)
- ✅ Improved average confidence: 75.3% → 78.0% (→ 80% target)

**Phase B - Diversification (IN PROGRESS 🔄):**
- 🔄 Downloading 3,500 diverse cases from 7+ major High Courts
- ⏳ Target: Reduce Patna HC dominance from 85% to <60%
- ⏳ Add Delhi, Bombay, Karnataka, Madras, Calcutta HCs

**Phase C - Validation (PENDING ⏳):**
- ⏳ Comprehensive production readiness validation
- ⏳ Target: 10,000+ cases, <30% any court, 80%+ confidence

**Progress:** See `PHASE_1_5_CLEANUP_SUMMARY.md` for detailed status.

**Monitor:** Run `bash scripts/check_status.sh` anytime.

## Project Structure

```
nyaya-ai/
├── src/
│   ├── config/
│   │   └── settings.py          # Pydantic settings management
│   ├── data_pipeline/
│   │   ├── downloaders/
│   │   │   └── hc_downloader.py  # S3 downloader
│   │   ├── extractors/
│   │   │   ├── pdf_extractor.py  # PDF text extraction
│   │   │   └── metadata_extractor.py  # LLM-powered extraction
│   │   ├── validators/
│   │   │   └── data_validator.py  # Data validation
│   │   └── loaders/
│   │       └── db_loader.py      # PostgreSQL loader
│   ├── database/
│   │   ├── models.py            # SQLAlchemy models
│   │   └── schemas.py           # Pydantic schemas
│   └── utils/
│       ├── logging_config.py    # Structured logging
│       └── llm_client.py        # Unified LLM interface
├── scripts/
│   ├── 01_download_sample.py        # Download cases
│   ├── 02_inspect_data.py           # Inspect downloaded data
│   ├── 03_run_extraction.py         # Run extraction pipeline
│   ├── 04_validate_quality.py       # Quality validation
│   ├── 05_standardize_courts.py     # [Phase 1.5] Court name standardization
│   ├── 06_improve_quality.py        # [Phase 1.5] Re-extract invalid/low-confidence
│   ├── 07_verify_duplicates.py      # [Phase 1.5] Find and remove duplicates
│   ├── 08_download_diverse.py       # [Phase 1.5] Download diverse courts
│   ├── 09_extract_diverse.py        # [Phase 1.5] Extract diverse cases
│   ├── 10_final_validation.py       # [Phase 1.5] Production readiness check
│   └── check_status.sh              # [Phase 1.5] Status monitoring
├── notebooks/
│   └── data_exploration.ipynb   # Data analysis
├── tests/
│   └── test_pipeline.py         # Tests
├── data/                         # Downloaded and processed data
├── docker-compose.yml           # Infrastructure setup
├── requirements.txt             # Python dependencies
└── .env                         # Configuration (create from .env.template)
```

## Quick Start

### 1. Prerequisites

- Python 3.10+
- Docker & Docker Compose
- At least one LLM API key (OpenAI, Anthropic, or Google)

### 2. Installation

```bash
# Clone or navigate to project directory
cd nyaya-ai

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

Edit `.env` file and add your API key:

```bash
# Add at least one of these:
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...

# Other settings (optional)
EXTRACTION_MODEL=gpt-4o-mini
DOWNLOAD_MAX_CASES=100
TARGET_COURTS=DL_HC,BH_HC
TARGET_YEARS=2024,2023
```

### 4. Start Infrastructure

```bash
# Start PostgreSQL, Redis, Qdrant
docker-compose up -d

# Verify services are running
docker-compose ps
```

### 5. Run the Pipeline

```bash
# Step 1: Download sample cases (100 cases across courts)
python scripts/01_download_sample.py

# Step 2: Inspect downloaded data
python scripts/02_inspect_data.py

# Step 3: Run extraction pipeline (requires LLM API key)
python scripts/03_run_extraction.py

# Step 4: Validate extraction quality
python scripts/04_validate_quality.py
```

## Pipeline Workflow

### 1. Download (`01_download_sample.py`)

Downloads PDFs and metadata from public S3 bucket:
- Source: `s3://indian-high-court-judgments`
- No AWS credentials needed (public bucket)
- Downloads specified courts and years
- Saves to `data/raw/high_courts/`

### 2. Inspect (`02_inspect_data.py`)

Analyzes downloaded data:
- Counts files by court
- Extracts sample text
- Checks for scanned PDFs
- Shows metadata structure

### 3. Extract (`03_run_extraction.py`)

**Most critical step** - runs the complete pipeline:

1. **PDF Text Extraction**
   - Tries pdfplumber first (best for formatted docs)
   - Falls back to PyPDF2 if needed
   - Cleans and normalizes text

2. **LLM Metadata Extraction**
   - Sends judgment text to LLM (GPT-4o-mini by default)
   - Extracts structured fields with confidence scores
   - Handles rate limiting and retries

3. **Validation**
   - Validates dates, court names, statutes
   - Cross-references against known legal entities
   - Flags low-confidence extractions

4. **Database Loading**
   - Saves to PostgreSQL with proper relationships
   - Creates statute and precedent records
   - Indexes filterable fields

### 4. Validate (`04_validate_quality.py`)

Reviews extraction quality:
- Shows cases needing review
- Identifies common errors
- Analyzes field completeness
- Provides recommendations

## Database Schema

### Cases Table

Primary table storing case information:

- **Identifiers**: case_id, case_title
- **Court Info**: court, bench, date_of_judgment
- **Classification**: case_type (Criminal/Civil/etc.)
- **Parties**: petitioner, respondent
- **Legal Elements**: sections_invoked, charges, statutes_cited
- **Outcome**: verdict, sentence
- **Content**: key_arguments, court_reasoning, headnotes, full_text
- **Metadata**: confidence_scores, validation_status

### Related Tables

- **Statutes**: Referenced legal statutes (IPC, CrPC, etc.)
- **Precedents**: Cited previous cases
- **Junction Tables**: Many-to-many relationships

## Extracted Fields

The LLM extracts these structured fields:

| Field | Description | Example |
|-------|-------------|---------|
| case_id | Unique identifier | HC-2024-001 |
| case_title | Full case name | State of Maharashtra v. XYZ |
| court | Court name | Bombay High Court |
| bench | Judge names | ["Justice A", "Justice B"] |
| date_of_judgment | Date | 2024-01-15 |
| case_type | Type of case | Criminal |
| petitioner | Petitioner(s) | ["State of Maharashtra"] |
| respondent | Respondent(s) | ["John Doe"] |
| statutes_cited | Statutes referenced | ["IPC", "CrPC"] |
| sections_invoked | Specific sections | ["IPC Section 302"] |
| charges | Criminal charges | ["Murder under IPC 302"] |
| verdict | Outcome | Convicted |
| sentence | Sentence details | 7 years imprisonment |
| key_arguments_petitioner | Summary | "Prosecution argued..." |
| key_arguments_respondent | Summary | "Defense claimed..." |
| court_reasoning | Court's logic | "The court found..." |
| precedents_cited | Previous cases | [{"case_name": "...", "citation": "..."}] |
| headnotes | Legal principles | ["Right to self-defense"] |

Each field includes a **confidence score** (0.0-1.0).

## API Cost Estimates

Using GPT-4o-mini (cheapest option):

- **Per case**: ~$0.01 - $0.02
- **100 cases**: ~$1 - $2
- **1,000 cases**: ~$10 - $20

Costs vary based on document length and complexity.

## Accessing the Database

### Using PgAdmin

1. Open http://localhost:5050
2. Login: admin@nyaya.ai / admin
3. Add server:
   - Host: postgres
   - Port: 5432
   - Database: nyaya_ai
   - User: nyaya_user
   - Password: nyaya_password

### Using Python

```python
from src.data_pipeline.loaders.db_loader import DatabaseLoader

db = DatabaseLoader()

# Get statistics
stats = db.get_database_stats()
print(f"Total cases: {stats['total_cases']}")

# Get cases needing review
cases = db.get_cases_by_validation_status("needs_review")
for case in cases:
    print(f"{case.case_title} - {case.average_confidence:.2f}")
```

### Using SQL

```bash
# Connect to database
docker exec -it nyaya_postgres psql -U nyaya_user -d nyaya_ai

# Sample queries
SELECT COUNT(*) FROM cases;
SELECT court, COUNT(*) FROM cases GROUP BY court;
SELECT * FROM cases WHERE validation_status = 'needs_review';
```

## Configuration Options

Edit `.env` to customize:

```bash
# LLM Configuration
EXTRACTION_MODEL=gpt-4o-mini        # Or claude-3-haiku, gemini-pro
EXTRACTION_TEMPERATURE=0.1          # Lower = more deterministic
MAX_RETRIES=3                       # API retry attempts

# Download Configuration
DOWNLOAD_MAX_CASES=100              # Max cases per session
TARGET_COURTS=DL_HC,BH_HC           # Court codes
TARGET_YEARS=2024,2023              # Years to download

# Processing
BATCH_SIZE=10                       # Cases per batch
MAX_CONCURRENT_REQUESTS=5           # Parallel LLM requests

# Database
DATABASE_URL=postgresql://...       # PostgreSQL connection
```

## Troubleshooting

### Issue: "No LLM API key configured"

**Solution**: Add API key to `.env` file:
```bash
OPENAI_API_KEY=sk-your-key-here
```

### Issue: "Failed to initialize database"

**Solution**: Start PostgreSQL:
```bash
docker-compose up -d postgres
docker-compose ps  # Verify it's running
```

### Issue: "Download failed from S3"

**Solution**:
- Check internet connection
- Verify boto3 is installed: `pip install boto3`
- The bucket is public, no AWS credentials needed

### Issue: "PDF extraction returning empty text"

**Solution**:
- File might be scanned (needs OCR)
- Run `scripts/02_inspect_data.py` to check
- OCR support coming in future phase

### Issue: "LLM extraction too expensive"

**Solutions**:
- Use cheaper model: `EXTRACTION_MODEL=gpt-4o-mini`
- Process fewer cases: `DOWNLOAD_MAX_CASES=10`
- Use local model (future feature)

## Development

### Running Tests

```bash
pytest tests/
```

### Adding Custom Validators

Edit `src/data_pipeline/validators/data_validator.py`:

```python
def _validate_custom_field(self, value: str) -> List[str]:
    warnings = []
    # Add your validation logic
    return warnings
```

### Using Different LLM Providers

The system supports multiple providers:

```python
from src.utils.llm_client import LLMClient

# OpenAI
client = LLMClient(provider="openai", model="gpt-4o-mini")

# Anthropic
client = LLMClient(provider="anthropic", model="claude-3-haiku-20240307")

# Google
client = LLMClient(provider="google", model="gemini-pro")
```

## Next Steps (Future Phases)

- **Phase 2**: Similar Case Retrieval (semantic search)
- **Phase 3**: Legal Research Assistant (RAG-powered)
- **Phase 4**: Simulated Courtroom (multi-model deliberation)
- **Phase 5**: Outcome Tendency Analyzer (statistical insights)

## Success Criteria

After running the pipeline, you should have:

- ✅ 100 cases downloaded from S3
- ✅ Text extracted from all PDFs
- ✅ Structured metadata extracted with >75% avg confidence
- ✅ >80% cases passing validation
- ✅ All data in PostgreSQL with proper relationships
- ✅ Clear logs showing what succeeded/failed

## Contributing

This is Phase 1 of the NyayaAI project. Focus areas for improvement:

1. **Extraction Prompt Engineering**: Improve LLM prompts for better accuracy
2. **Validation Rules**: Add more Indian legal statute references
3. **OCR Support**: Add support for scanned PDFs
4. **Performance**: Optimize for large-scale processing

## License

This project is for educational and research purposes.

## Contact

For questions or issues, please open a GitHub issue.

---

**Note**: This is a decision support tool, not a replacement for legal expertise. All outputs should be reviewed by qualified legal professionals.
