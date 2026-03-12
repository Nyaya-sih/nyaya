# NyayaAI - Quick Start Guide

Get up and running in 5 minutes!

## Prerequisites

- Python 3.10+ installed
- Docker Desktop running
- OpenAI API key (or Anthropic/Google)

## Setup (5 steps)

### 1. Install Python Dependencies

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install packages
pip install -r requirements.txt
```

### 2. Configure API Key

Edit `.env` file and add your OpenAI API key:

```bash
OPENAI_API_KEY=sk-your-actual-key-here
```

**Where to get API keys:**
- OpenAI: https://platform.openai.com/api-keys
- Anthropic: https://console.anthropic.com/
- Google: https://makersuite.google.com/app/apikey

### 3. Start Database

```bash
docker-compose up -d postgres
```

Verify it's running:
```bash
docker-compose ps
```

### 4. Download Sample Data

```bash
python scripts/01_download_sample.py
```

This downloads ~100 High Court judgments (takes 2-5 minutes).

### 5. Run Extraction Pipeline

```bash
python scripts/03_run_extraction.py
```

This will:
- Extract text from PDFs
- Use GPT-4o-mini to extract metadata
- Validate the data
- Load to PostgreSQL

**Cost:** ~$1-2 for 100 cases

## What You Get

After running the pipeline:

✅ **100 cases** downloaded from public S3 bucket
✅ **Structured metadata** extracted (parties, statutes, verdict, etc.)
✅ **PostgreSQL database** with searchable case data
✅ **Quality metrics** showing extraction confidence

## Quick Commands

```bash
# View extraction quality
python scripts/04_validate_quality.py

# Check data statistics
python scripts/02_inspect_data.py

# Access database via PgAdmin
# Open http://localhost:5050
# Login: admin@nyaya.ai / admin
```

## Explore the Data

### Option 1: Jupyter Notebook

```bash
jupyter notebook notebooks/data_exploration.ipynb
```

### Option 2: Direct SQL

```bash
docker exec -it nyaya_postgres psql -U nyaya_user -d nyaya_ai

# Try these queries:
SELECT COUNT(*) FROM cases;
SELECT court, COUNT(*) FROM cases GROUP BY court;
SELECT * FROM cases WHERE validation_status = 'valid' LIMIT 5;
```

### Option 3: Python

```python
from src.data_pipeline.loaders.db_loader import DatabaseLoader

db = DatabaseLoader()
stats = db.get_database_stats()
print(stats)
```

## Troubleshooting

**"No LLM API key configured"**
→ Add `OPENAI_API_KEY=sk-...` to `.env` file

**"Failed to initialize database"**
→ Run `docker-compose up -d postgres`

**"No PDF files found"**
→ Run `python scripts/01_download_sample.py` first

## What's Next?

1. ✅ You now have clean, structured case data!
2. 📊 Explore the data in Jupyter notebook
3. 🔍 Review cases needing manual validation
4. 🚀 Ready for Phase 2: Similar Case Retrieval

## Cost Estimates

- GPT-4o-mini: ~$0.01 per case
- 100 cases: ~$1-2
- 1,000 cases: ~$10-20

Use cheaper model in `.env`:
```bash
EXTRACTION_MODEL=gpt-4o-mini  # Cheapest
# EXTRACTION_MODEL=claude-3-haiku-20240307
# EXTRACTION_MODEL=gemini-pro
```

## Support

- Read full documentation: `README.md`
- Check logs: `data/logs/pipeline.log`
- Run tests: `pytest tests/`

---

**Happy coding! 🎉**
