#!/bin/bash
# Automated Phase 1.5 completion script
# Monitors extraction, runs validation, and notifies when complete

set -e

PROJECT_DIR="/home/psycho/projects/law/nyaya-ai"
LOG_FILE="$PROJECT_DIR/phase_1_5_auto_complete.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "========================================"
log "Phase 1.5 Auto-Completion Script Started"
log "========================================"

# Step 1: Wait for extraction to complete
log "Step 1: Monitoring extraction process..."

EXTRACTION_PID=$(pgrep -f "09_extract_diverse.py" || echo "")

if [ -z "$EXTRACTION_PID" ]; then
    log "ERROR: Extraction process not found!"
    log "Please start extraction manually: python scripts/09_extract_diverse.py"
    exit 1
fi

log "Extraction process found (PID: $EXTRACTION_PID)"
log "Waiting for extraction to complete..."
log "(This will take approximately 2.5 hours)"

# Wait for the process to finish
while kill -0 "$EXTRACTION_PID" 2>/dev/null; do
    # Log progress every 10 minutes
    sleep 600

    # Check extraction log for progress
    PROGRESS=$(tail -1 "$PROJECT_DIR/diverse_extraction_fixed.log" | grep -oP '\d+%' | head -1 || echo "Processing...")
    log "Extraction progress: $PROGRESS"
done

log "✅ Extraction process completed!"

# Give it a moment to write final logs
sleep 10

# Step 2: Check extraction results
log ""
log "Step 2: Checking extraction results..."

cd "$PROJECT_DIR"

EXTRACTION_SUCCESS=$(tail -50 "$PROJECT_DIR/diverse_extraction_fixed.log" | grep -c "EXTRACTION COMPLETE" || echo "0")

if [ "$EXTRACTION_SUCCESS" -eq "0" ]; then
    log "⚠️  WARNING: Extraction may have failed - 'EXTRACTION COMPLETE' not found in log"
    log "Check diverse_extraction_fixed.log for errors"
    bash notify_me.sh "⚠️ NyayaAI Phase 1.5: Extraction completed but may have errors. Check logs."
    exit 1
fi

# Check database stats
log "Checking database statistics..."

DB_STATS=$(python -c "
from src.data_pipeline.loaders.db_loader import DatabaseLoader
db = DatabaseLoader()
stats = db.get_database_stats()
print(f\"Total: {stats['total_cases']}, Invalid: {stats['invalid_cases']}, Avg: {stats['average_confidence']:.1%}\")
" 2>&1)

log "Database stats: $DB_STATS"

TOTAL_CASES=$(echo "$DB_STATS" | grep -oP 'Total: \K\d+' || echo "0")

if [ "$TOTAL_CASES" -lt "10000" ]; then
    log "⚠️  WARNING: Expected at least 10,000 cases but got $TOTAL_CASES"
    log "Continuing with validation anyway..."
fi

# Step 3: Run final validation
log ""
log "Step 3: Running final production readiness validation..."

python scripts/10_final_validation.py 2>&1 | tee -a "$LOG_FILE"

VALIDATION_EXIT_CODE=$?

if [ $VALIDATION_EXIT_CODE -ne 0 ]; then
    log "❌ ERROR: Final validation script failed with exit code $VALIDATION_EXIT_CODE"
    bash notify_me.sh "❌ NyayaAI Phase 1.5: Final validation failed. Check logs."
    exit 1
fi

log "✅ Final validation completed!"

# Step 4: Check if production ready
log ""
log "Step 4: Checking production readiness..."

REPORT_FILE="$PROJECT_DIR/data/processed/production_readiness_report.json"

if [ ! -f "$REPORT_FILE" ]; then
    log "⚠️  WARNING: Production readiness report not found at $REPORT_FILE"
    PRODUCTION_READY="UNKNOWN"
else
    PRODUCTION_READY=$(python -c "
import json
with open('$REPORT_FILE', 'r') as f:
    report = json.load(f)
    print('YES' if report.get('production_ready', False) else 'NO')
" 2>&1)
fi

log "Production ready: $PRODUCTION_READY"

# Step 5: Generate final summary
log ""
log "========================================"
log "PHASE 1.5 COMPLETION SUMMARY"
log "========================================"
log "Total Cases: $TOTAL_CASES"
log "Production Ready: $PRODUCTION_READY"
log "Report: $REPORT_FILE"
log "========================================"

# Step 6: Notify user
log ""
log "Step 6: Sending notification..."

if [ "$PRODUCTION_READY" = "YES" ]; then
    bash notify_me.sh "🎉 NyayaAI Phase 1.5 COMPLETE! Dataset is production-ready with $TOTAL_CASES cases. Ready for Phase 2!"
    log "✅ SUCCESS: Phase 1.5 complete and production-ready!"
elif [ "$PRODUCTION_READY" = "NO" ]; then
    bash notify_me.sh "⚠️ NyayaAI Phase 1.5 Complete but NOT production-ready. Review validation report."
    log "⚠️  Phase 1.5 complete but not production-ready. Review report."
else
    bash notify_me.sh "ℹ️ NyayaAI Phase 1.5 extraction and validation complete. Status: $PRODUCTION_READY"
    log "ℹ️ Phase 1.5 processing complete."
fi

log ""
log "========================================"
log "Auto-completion script finished"
log "Full log: $LOG_FILE"
log "========================================"

exit 0
