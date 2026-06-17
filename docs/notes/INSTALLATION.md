# Installation Guide

## System Requirements

- **Python**: 3.10 or higher
- **Docker**: Latest version with Docker Compose
- **RAM**: Minimum 4GB (8GB recommended)
- **Storage**: 5GB free space
- **OS**: Linux, macOS, or Windows with WSL2

## Step-by-Step Installation

### 1. Verify Prerequisites

```bash
# Check Python version (should be 3.10+)
python --version

# Check Docker
docker --version
docker-compose --version
```

### 2. Set Up Python Environment

```bash
# Navigate to project directory
cd nyaya-ai

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/Mac:
source venv/bin/activate

# On Windows:
venv\Scripts\activate

# Upgrade pip
pip install --upgrade pip
```

### 3. Install Python Dependencies

```bash
# Install all required packages
pip install -r requirements.txt

# This installs:
# - PDF processing (PyPDF2, pdfplumber)
# - Database (sqlalchemy, psycopg2-binary)
# - LLM clients (openai, anthropic, google-generativeai)
# - Data tools (pandas, numpy)
# - Utilities (tqdm, loguru, tenacity)
# - Testing (pytest)
# - Jupyter notebooks
```

### 4. Configure Environment Variables

```bash
# Copy template to create .env file
cp .env.template .env

# Edit .env file and add your API key
nano .env  # or use any text editor

# At minimum, add ONE of these:
OPENAI_API_KEY=sk-your-key-here
# ANTHROPIC_API_KEY=sk-ant-your-key-here
# GEMINI_API_KEY=your-key-here
```

**Getting API Keys:**

- **OpenAI**: https://platform.openai.com/api-keys
  - Sign up → API keys → Create new secret key
  - Cost: ~$0.01 per case with GPT-4o-mini

- **Anthropic**: https://console.anthropic.com/
  - Sign up → Get API keys → Create key
  - Cost: Similar to OpenAI

- **Google**: https://makersuite.google.com/app/apikey
  - Sign up → Get API key
  - Free tier available

### 5. Start Infrastructure

```bash
# Start all services (PostgreSQL, Redis, Qdrant, PgAdmin)
docker-compose up -d

# Check that services are running
docker-compose ps

# Should show 4 services running:
# - nyaya_postgres
# - nyaya_redis
# - nyaya_qdrant
# - nyaya_pgadmin
```

### 6. Verify Installation

```bash
# Test Python imports
python -c "from src.config.settings import settings; print('✓ Settings loaded')"

# Test database connection
docker exec nyaya_postgres pg_isready -U nyaya_user

# Should output: accepting connections
```

### 7. Run Your First Pipeline

```bash
# Download sample data (100 cases)
python scripts/01_download_sample.py

# This will:
# - Connect to public S3 bucket
# - Download 100 High Court judgment PDFs
# - Save to data/raw/high_courts/
# - Takes 2-5 minutes depending on connection
```

### 8. Extract and Load Data

```bash
# Run the complete extraction pipeline
python scripts/03_run_extraction.py

# This will:
# 1. Extract text from PDFs (pdfplumber/PyPDF2)
# 2. Use LLM to extract structured metadata
# 3. Validate extracted data
# 4. Load to PostgreSQL
# 5. Show detailed statistics

# Cost: ~$1-2 for 100 cases with GPT-4o-mini
# Time: ~5-15 minutes depending on API speed
```

### 9. Validate Results

```bash
# Check extraction quality
python scripts/04_validate_quality.py

# Expected output:
# - Total cases: 100
# - Valid cases: 80+ (>80%)
# - Average confidence: 0.75+ (>75%)
```

### 10. Explore Data

```bash
# Option 1: Jupyter Notebook
jupyter notebook notebooks/data_exploration.ipynb

# Option 2: PgAdmin (Web UI)
# Open http://localhost:5050
# Login: admin@nyaya.ai / admin

# Option 3: Direct SQL
docker exec -it nyaya_postgres psql -U nyaya_user -d nyaya_ai
```

## Troubleshooting Installation

### Problem: "ModuleNotFoundError"

**Solution:**
```bash
# Make sure virtual environment is activated
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Reinstall requirements
pip install -r requirements.txt
```

### Problem: "Docker not running"

**Solution:**
```bash
# Start Docker Desktop (GUI)
# Or on Linux:
sudo systemctl start docker

# Verify:
docker ps
```

### Problem: "Port already in use"

**Solution:**
```bash
# Check what's using the port
lsof -i :5432  # PostgreSQL port
lsof -i :6379  # Redis port

# Stop conflicting service or change port in docker-compose.yml
```

### Problem: "Permission denied" on scripts

**Solution:**
```bash
# Make scripts executable
chmod +x scripts/*.py
```

### Problem: "LLM API rate limit exceeded"

**Solution:**
```bash
# Edit .env to reduce concurrent requests
MAX_CONCURRENT_REQUESTS=2  # Default is 5

# Or add delays between requests
RETRY_DELAY=5  # Default is 2
```

### Problem: "Out of memory"

**Solution:**
```bash
# Process fewer cases at a time
BATCH_SIZE=5  # Default is 10

# Or increase Docker memory limit
# Docker Desktop → Settings → Resources → Memory
```

## Verifying Installation

Run these commands to verify everything is working:

```bash
# 1. Python packages
python -c "import pdfplumber, openai, sqlalchemy, pandas; print('✓ All packages installed')"

# 2. Database connection
docker exec nyaya_postgres psql -U nyaya_user -d nyaya_ai -c "SELECT version();"

# 3. Project structure
python -c "from src.config.settings import settings; print('✓ Project structure OK')"

# 4. Download test
python scripts/01_download_sample.py

# 5. Run tests
pytest tests/ -v
```

## Post-Installation

### Recommended: Set Up Git

```bash
# Initialize git repository
git init

# Add all files
git add .

# First commit
git commit -m "Initial commit: NyayaAI Phase 1 complete"
```

### Recommended: Create Backup

```bash
# Backup database
docker exec nyaya_postgres pg_dump -U nyaya_user nyaya_ai > backup.sql

# Backup processed data
tar -czf data_backup.tar.gz data/
```

### Optional: Set Up Jupyter

```bash
# Install Jupyter kernel for your venv
python -m ipykernel install --user --name=nyaya-ai --display-name="NyayaAI"

# Start Jupyter
jupyter notebook
```

## Uninstallation

If you need to remove everything:

```bash
# Stop and remove Docker containers
docker-compose down -v

# Deactivate virtual environment
deactivate

# Remove virtual environment
rm -rf venv/

# Remove downloaded data (optional)
rm -rf data/raw/*
rm -rf data/processed/*
```

## Next Steps

After successful installation:

1. ✅ Read **QUICKSTART.md** for a 5-minute tutorial
2. ✅ Read **README.md** for complete documentation
3. ✅ Read **PROJECT_SUMMARY.md** to understand what was built
4. ✅ Run the pipeline and explore the data!

## Support

- **Documentation**: README.md, QUICKSTART.md
- **Logs**: Check `data/logs/pipeline.log`
- **Tests**: Run `pytest tests/ -v`
- **Database**: Access via PgAdmin at http://localhost:5050

---

**Installation complete! 🎉**
