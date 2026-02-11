#!/bin/bash
# Quick status check for all running processes

echo "======================================================================"
echo "NYAYA-AI PIPELINE STATUS"
echo "======================================================================"
echo ""

# Check quality improvement
echo "📊 QUALITY IMPROVEMENT:"
if ps aux | grep -v grep | grep -q "06_improve_quality.py"; then
    echo "  Status: ✅ RUNNING"
    if [ -f quality_improvement.log ]; then
        progress=$(grep -o "[0-9]*%" quality_improvement.log | tail -1)
        echo "  Progress: $progress"
        echo "  Latest: $(tail -1 quality_improvement.log | cut -c1-80)"
    fi
else
    echo "  Status: ⏹️  NOT RUNNING"
    if [ -f quality_improvement.log ]; then
        last_line=$(tail -1 quality_improvement.log)
        if echo "$last_line" | grep -q "COMPLETE"; then
            echo "  Result: ✅ COMPLETE"
        fi
    fi
fi
echo ""

# Check diverse download
echo "📥 DIVERSE CASE DOWNLOAD:"
if ps aux | grep -v grep | grep -q "08_download_diverse.py"; then
    echo "  Status: ✅ RUNNING"
    if [ -f diverse_download.log ]; then
        downloaded=$(grep -o "[0-9]*/[0-9]* downloaded" diverse_download.log | tail -1)
        echo "  Progress: $downloaded"
        court=$(grep "DOWNLOADING FROM" diverse_download.log | tail -1 | cut -d' ' -f4-)
        echo "  Current: $court"
    fi
else
    echo "  Status: ⏹️  NOT RUNNING"
    if [ -f diverse_download.log ]; then
        last_line=$(tail -1 diverse_download.log)
        if echo "$last_line" | grep -q "COMPLETE"; then
            echo "  Result: ✅ COMPLETE"
        fi
    fi
fi
echo ""

# Check database stats
echo "🗄️  DATABASE STATUS:"
cd /home/psycho/projects/law/nyaya-ai
source ../venv/bin/activate 2>/dev/null

python -c "
from src.data_pipeline.loaders.db_loader import DatabaseLoader
from src.database.models import Case
from sqlalchemy import func
import sys

try:
    db = DatabaseLoader()
    session = db.SessionLocal()

    total = session.query(func.count(Case.id)).scalar()
    invalid = session.query(func.count(Case.id)).filter(Case.validation_status == 'invalid').scalar()
    low_conf = session.query(func.count(Case.id)).filter(Case.average_confidence < 0.6).scalar()
    avg_conf = session.query(func.avg(Case.average_confidence)).scalar()

    print(f'  Total cases: {total:,}')
    print(f'  Invalid: {invalid} ({invalid/total*100:.1f}%)')
    print(f'  Low confidence: {low_conf} ({low_conf/total*100:.1f}%)')
    print(f'  Avg confidence: {avg_conf:.2%}')

    session.close()
except Exception as e:
    print(f'  Error: {e}')
    sys.exit(1)
" 2>/dev/null

echo ""

# Check disk usage
echo "💾 DISK USAGE:"
if [ -d data/raw ]; then
    raw_size=$(du -sh data/raw 2>/dev/null | cut -f1)
    echo "  Raw PDFs: $raw_size"
fi
if [ -d data/raw/diverse_courts ]; then
    diverse_size=$(du -sh data/raw/diverse_courts 2>/dev/null | cut -f1)
    diverse_count=$(find data/raw/diverse_courts -name "*.pdf" 2>/dev/null | wc -l)
    echo "  Diverse PDFs: $diverse_size ($diverse_count files)"
fi

echo ""
echo "======================================================================"
echo "Run this script anytime: bash scripts/check_status.sh"
echo "======================================================================"
