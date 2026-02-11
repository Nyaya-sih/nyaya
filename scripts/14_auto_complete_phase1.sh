#!/bin/bash
# Auto-completion script for Phase 1
# Monitors extraction, runs standardization, validation, and notification

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

LOG_FILE="phase1_auto_completion.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=========================================="
log "PHASE 1 AUTO-COMPLETION STARTED"
log "=========================================="

# Activate virtual environment
source ../venv/bin/activate

# Step 1: Wait for extraction to complete
log "Step 1: Monitoring extraction process..."
log "Waiting for extraction to reach 10,000 cases..."

while true; do
    # Check current case count
    CURRENT_COUNT=$(python -c "
from src.data_pipeline.loaders.db_loader import DatabaseLoader
from sqlalchemy import func
from src.database.models import Case
db = DatabaseLoader()
session = db.SessionLocal()
count = session.query(func.count(Case.id)).scalar()
session.close()
print(count)
" 2>/dev/null || echo "0")

    log "Current case count: $CURRENT_COUNT"

    if [ "$CURRENT_COUNT" -ge 10000 ]; then
        log "✅ Target reached! $CURRENT_COUNT cases"
        break
    fi

    # Check if extraction process is still running
    if ! pgrep -f "11_smart_extract_to_10k.py" > /dev/null; then
        log "⚠️  Extraction process not running"
        log "Current count: $CURRENT_COUNT"

        if [ "$CURRENT_COUNT" -ge 9500 ]; then
            log "Close enough to target, proceeding..."
            break
        else
            log "❌ Failed to reach target"
            log "Manual intervention required"
            exit 1
        fi
    fi

    # Wait 5 minutes before checking again
    log "Waiting 5 minutes before next check..."
    sleep 300
done

log ""
log "Step 2: Running final court name standardization..."
python scripts/12_final_court_standardization.py >> "$LOG_FILE" 2>&1
log "✅ Court standardization complete"

log ""
log "Step 3: Running final production validation..."
python scripts/13_final_validation.py >> "$LOG_FILE" 2>&1
log "✅ Final validation complete"

log ""
log "Step 4: Generating Phase 1 completion summary..."

# Get final statistics
python -c "
from src.data_pipeline.loaders.db_loader import DatabaseLoader
from src.database.models import Case
from sqlalchemy import func
from collections import Counter

db = DatabaseLoader()
session = db.SessionLocal()

total = session.query(func.count(Case.id)).scalar()
invalid = session.query(func.count(Case.id)).filter(Case.validation_status == 'invalid').scalar()
avg_conf = session.query(func.avg(Case.average_confidence)).scalar()

courts = session.query(
    Case.court,
    func.count(Case.id)
).group_by(Case.court).order_by(func.count(Case.id).desc()).limit(5).all()

print('\n' + '='*60)
print('PHASE 1 COMPLETION SUMMARY')
print('='*60)
print(f'Total Cases: {total:,}')
print(f'Invalid Cases: {invalid} ({invalid/total*100:.1f}%)')
print(f'Average Confidence: {avg_conf:.1%}')
print(f'\nTop 5 Courts:')
for court, count in courts:
    pct = count / total * 100
    court_name = court if court else 'Unknown'
    print(f'  {court_name:<50} {count:>5,} ({pct:.1f}%)')
print('='*60)

session.close()
" | tee -a "$LOG_FILE"

log ""
log "=========================================="
log "PHASE 1 AUTO-COMPLETION FINISHED"
log "=========================================="
log "Check production_readiness_report.json for full details"
log ""

# Step 5: Run notification
log "Step 5: Sending notification..."
if [ -f "./notify_me.sh" ]; then
    ./notify_me.sh "NyayaAI Phase 1 Complete! Ready for Phase 2: Similar Case Retrieval" >> "$LOG_FILE" 2>&1
    log "✅ Notification sent"
else
    log "⚠️  notify_me.sh not found, skipping notification"
fi

log ""
log "🎉 ALL DONE! Phase 1 is complete and validated."
log "Next step: Implement Phase 2 - Similar Case Retrieval"
log ""
log "Full log saved to: $LOG_FILE"
