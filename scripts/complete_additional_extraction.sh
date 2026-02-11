#!/bin/bash
# Monitor additional extraction and complete Phase 1.5

PROJECT_DIR="/home/psycho/projects/law/nyaya-ai"
LOG_FILE="$PROJECT_DIR/additional_completion.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "========================================"
log "Additional Extraction Auto-Completion"
log "========================================"

# Wait for extraction to complete
EXTRACTION_PID=$(ps aux | grep "python.*09_extract_new_only" | grep -v grep | awk '{print $2}' | head -1)

if [ -z "$EXTRACTION_PID" ]; then
    log "ERROR: Extraction process not found!"
    log "Checking if already completed..."
    if grep -q "EXTRACTION COMPLETE" "$PROJECT_DIR/additional_extraction.log" 2>/dev/null; then
        log "Extraction already completed."
    else
        log "Extraction not running and not completed. Exiting."
        exit 1
    fi
else
    log "Extraction running (PID: $EXTRACTION_PID)"
    log "Waiting for completion (~9 hours)..."
    
    while kill -0 "$EXTRACTION_PID" 2>/dev/null; do
        sleep 600  # Log every 10 minutes
        PROGRESS=$(tail -10 "$PROJECT_DIR/additional_extraction.log" | grep -oP '\d+%' | tail -1 || echo "Processing...")
        log "Progress: $PROGRESS"
    done
    
    log "✅ Extraction completed!"
    sleep 10
fi

# Check results
log ""
log "Checking extraction results..."

cd "$PROJECT_DIR"

DB_STATS=$(python -c "
from src.data_pipeline.loaders.db_loader import DatabaseLoader
db = DatabaseLoader()
stats = db.get_database_stats()
print(f\"Total: {stats['total_cases']}, Invalid: {stats['invalid_cases']}, Avg: {stats['average_confidence']:.1%}\")
" 2>&1)

log "Database stats: $DB_STATS"

TOTAL_CASES=$(echo "$DB_STATS" | grep -oP 'Total: \K\d+' || echo "0")
log "Total cases: $TOTAL_CASES"

# Standardize new court names
log ""
log "Running court name standardization..."
echo "yes" | python scripts/05_standardize_courts.py 2>&1 | grep -E "Updated|Total cases updated" | tee -a "$LOG_FILE"

# Run final validation
log ""
log "Running final validation..."
python scripts/10_final_validation.py 2>&1 | tee -a "$LOG_FILE"

# Check production readiness
REPORT_FILE="$PROJECT_DIR/data/processed/production_readiness_report.json"

if [ ! -f "$REPORT_FILE" ]; then
    log "⚠️  Report not found"
    PRODUCTION_READY="UNKNOWN"
else
    PRODUCTION_READY=$(python -c "
import json
with open('$REPORT_FILE') as f:
    report = json.load(f)
    print('YES' if report.get('production_ready', False) else 'NO')
" 2>&1)
fi

log ""
log "========================================"
log "PHASE 1.5 COMPLETION SUMMARY"
log "========================================"
log "Total Cases: $TOTAL_CASES"
log "Production Ready: $PRODUCTION_READY"
log "========================================"

# Send notification
log ""
log "Sending notification..."

if [ "$PRODUCTION_READY" = "YES" ]; then
    bash "$PROJECT_DIR/notify_me.sh" "🎉 NyayaAI Phase 1.5 COMPLETE! Production-ready with $TOTAL_CASES cases!"
    log "✅ SUCCESS: Production ready!"
elif [ "$PRODUCTION_READY" = "NO" ]; then
    bash "$PROJECT_DIR/notify_me.sh" "⚠️ NyayaAI Phase 1.5: Extraction complete but not production-ready. $TOTAL_CASES cases."
    log "⚠️  Not production ready yet."
else
    bash "$PROJECT_DIR/notify_me.sh" "ℹ️ NyayaAI Phase 1.5 extraction complete. $TOTAL_CASES cases. Check status."
    log "ℹ️ Completed with status: $PRODUCTION_READY"
fi

log ""
log "Auto-completion finished!"

exit 0
