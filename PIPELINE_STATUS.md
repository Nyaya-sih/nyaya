# NyayaAI Pipeline Status - February 7, 2026

## 🚀 AUTOMATED PIPELINE RUNNING

**Started:** 19:21, February 7, 2026
**Status:** Extracting metadata from 8,020 cases
**Expected Completion:** ~9:00-10:00 AM, February 8, 2026

---

## ✅ Phase 1: Download - COMPLETE

**Results:**
- **Downloaded:** 6,500 new PDFs
- **Total PDFs:** 8,020
- **Success rate:** 100%
- **Failed:** 0

**Dataset Coverage:**
- **Years:** 2013-2023 (11 years)
- **Courts:** 4+ High Courts
  - Court 10_8: 4,980 cases
  - Court 11_24: 995 cases
  - Court 14_25: 453 cases
  - Court 16_20: 72 cases

**Download completed:** ~19:15

---

## 🤖 Phase 2: LLM Extraction - IN PROGRESS

**Configuration:**
- **Model:** GPT-4o-mini
- **Total cases:** 8,020
- **Processing rate:** ~550 cases/hour
- **Estimated time:** 14-15 hours

**Cost Estimate:**
- **Per case:** $0.0003
- **Total estimated:** $2.40
- (Note: Script shows $80 but that's using wrong estimate)

**Started:** 19:21
**Expected finish:** 09:00-10:00 (Feb 8)

---

## 📊 What's Being Extracted (per case):

- ✅ Case title and citation
- ✅ Court name
- ✅ Judge/bench details
- ✅ Date of judgment
- ✅ Petitioner and respondent names
- ✅ Case type (criminal/civil/etc.)
- ✅ Legal statutes cited
- ✅ Precedents referenced
- ✅ Key arguments (petitioner & respondent)
- ✅ Court reasoning
- ✅ Verdict/decision
- ✅ Full judgment text
- ✅ Confidence scores per field

---

## 📁 Monitor Progress:

### Check Extraction Progress
```bash
cd /home/psycho/projects/law/nyaya-ai

# Watch live progress
tail -f pipeline_auto.log

# Check detailed logs
tail -f data/logs/pipeline.log

# Count processed cases (check how many extraction calls)
grep "Extracting metadata" data/logs/pipeline.log | wc -l
```

### Check Processing Speed
```bash
# Cases processed in last minute
grep "Extracting metadata" data/logs/pipeline.log | tail -60 | wc -l
```

### Estimated Completion Time
```bash
# Get current progress
current=$(grep "Extracting metadata" data/logs/pipeline.log | wc -l)
remaining=$((8020 - current))
hours_left=$(echo "scale=1; $remaining / 550" | bc)
echo "Progress: $current / 8020 cases"
echo "Estimated hours remaining: $hours_left"
```

---

## 📈 When Complete, Check Results:

### 1. View Final Statistics
```bash
cat data/processed/extraction_results.json | jq '.stats'
cat data/processed/extraction_results.json | jq '.llm_stats'
cat data/processed/extraction_results.json | jq '.db_stats'
```

### 2. Database Statistics
```bash
sudo docker exec nyaya_postgres psql -U nyaya_user -d nyaya_ai -c "
SELECT
  COUNT(*) as total_cases,
  COUNT(DISTINCT court) as unique_courts,
  MIN(date_of_judgment) as earliest_case,
  MAX(date_of_judgment) as latest_case,
  ROUND(AVG(average_confidence)::numeric, 3) as avg_confidence,
  COUNT(CASE WHEN validation_status = 'valid' THEN 1 END) as valid_cases,
  COUNT(CASE WHEN validation_status = 'needs_review' THEN 1 END) as needs_review,
  COUNT(CASE WHEN validation_status = 'invalid' THEN 1 END) as invalid_cases
FROM cases;
"
```

### 3. Sample Cases
```bash
sudo docker exec nyaya_postgres psql -U nyaya_user -d nyaya_ai -c "
SELECT case_title, court, date_of_judgment, verdict, average_confidence
FROM cases
ORDER BY average_confidence DESC
LIMIT 10;
"
```

### 4. Court Distribution
```bash
sudo docker exec nyaya_postgres psql -U nyaya_user -d nyaya_ai -c "
SELECT court, COUNT(*) as case_count
FROM cases
GROUP BY court
ORDER BY case_count DESC;
"
```

---

## 🎯 Expected Final Dataset:

Based on current extraction rate and previous runs:

- **Total Cases:** ~7,500-7,800 (some duplicates/invalid may be filtered)
- **Success Rate:** ~95-98%
- **Average Confidence:** ~75-80%
- **Valid Cases:** ~7,000+
- **Years Covered:** 2013-2023
- **Courts:** 4+ Indian High Courts
- **Total Cost:** ~$2.40

---

## 🚨 If Something Goes Wrong:

### Check if Pipeline is Still Running
```bash
ps aux | grep python | grep run_extraction
```

### Check for Errors
```bash
grep -i error data/logs/pipeline.log | tail -20
tail -100 pipeline_auto.log
```

### Restart Extraction (if needed)
```bash
cd /home/psycho/projects/law/nyaya-ai
source ../venv/bin/activate
python scripts/run_extraction_simple.py
```

### Check Database Connection
```bash
sudo docker ps | grep postgres
sudo docker exec nyaya_postgres psql -U nyaya_user -d nyaya_ai -c "SELECT COUNT(*) FROM cases;"
```

---

## ✅ Next Steps (After Completion):

### 1. Validate Quality
Review confidence scores and validation status to ensure data quality.

### 2. Explore the Data
Use Jupyter notebooks or SQL queries to explore the cases.

### 3. Export Data
Export specific subsets for analysis or external use.

### 4. Phase 2: Similar Case Retrieval
Once satisfied with Phase 1:
- Generate embeddings for all cases
- Build vector search index
- Implement similarity search
- Find related cases based on facts/law

### 5. Phase 3: RAG System
- Build question-answering system
- Conversation with case documents
- Legal reasoning capabilities

---

## 📞 Quick Reference

**Pipeline logs:** `tail -f pipeline_auto.log`
**Extraction logs:** `tail -f data/logs/pipeline.log`
**Results file:** `data/processed/extraction_results.json`
**Database:** `sudo docker exec -it nyaya_postgres psql -U nyaya_user -d nyaya_ai`

**Estimated completion:** February 8, 2026 ~9:00-10:00 AM

---

**Status last updated:** February 7, 2026 at 19:22

🚀 Pipeline running automatically. No action needed.
