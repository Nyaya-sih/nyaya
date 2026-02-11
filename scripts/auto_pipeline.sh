#!/bin/bash
# Auto-run full pipeline: download → extract → load to DB

set -e

cd /home/psycho/projects/law/nyaya-ai
source ../venv/bin/activate

echo "=========================================="
echo "🚀 NYAYA-AI AUTO PIPELINE"
echo "=========================================="
echo ""
echo "This will:"
echo "1. ⏳ Wait for download to complete"
echo "2. 🤖 Run LLM extraction on all PDFs"
echo "3. 📊 Load results to database"
echo "4. 📈 Generate final statistics"
echo ""
echo "Estimated time: 5-8 hours for ~8000 cases"
echo ""
echo "=========================================="
echo ""

# Monitor download progress
echo "📥 Monitoring download progress..."
target_pdfs=8000
check_interval=30

while true; do
    current_count=$(ls data/raw/sample_pdfs/*.pdf 2>/dev/null | wc -l || echo 0)

    echo "$(date '+%H:%M:%S') - PDFs downloaded: $current_count / ~$target_pdfs"

    # Check if download task is still running
    if ! ps aux | grep -v grep | grep -q "download_large_dataset.py"; then
        echo "✅ Download process completed"
        break
    fi

    # If we've hit target, assume download is done
    if [ $current_count -ge $((target_pdfs - 100)) ]; then
        echo "✅ Target reached: $current_count PDFs"
        sleep 30  # Give it time to finish
        break
    fi

    sleep $check_interval
done

final_count=$(ls data/raw/sample_pdfs/*.pdf 2>/dev/null | wc -l || echo 0)
echo ""
echo "=========================================="
echo "✅ DOWNLOAD COMPLETE: $final_count PDFs"
echo "=========================================="
echo ""

# Run extraction pipeline
echo "🤖 Starting LLM extraction pipeline..."
echo "This will take several hours..."
echo ""

python scripts/run_extraction_simple.py

echo ""
echo "=========================================="
echo "✅ PIPELINE COMPLETE!"
echo "=========================================="
echo ""

# Show final stats
python -c "
from src.data_pipeline.loaders.db_loader import DatabaseLoader
from src.database.models import Case
from sqlalchemy import func

db = DatabaseLoader()
session = db.SessionLocal()

stats = session.query(
    func.count(Case.id).label('total'),
    func.avg(Case.average_confidence).label('avg_conf')
).first()

print('📊 FINAL DATABASE STATS:')
print(f'  Total Cases: {stats.total}')
print(f'  Avg Confidence: {stats.avg_conf:.2%}')

session.close()
"

echo ""
echo "🎉 All done! Check data/processed/extraction_results.json for details"
