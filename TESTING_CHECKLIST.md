# Testing Checklist - Territory Planner v1.0

## Pre-Testing Setup

1. **Create .env file** (if not exists):
   ```bash
   cp .env.example .env
   # Edit .env and add your actual API keys
   ```

2. **Start the development environment**:
   ```bash
   # Option A: Docker Compose (recommended)
   docker-compose -f docker-compose.dev.yml up --build

   # Option B: Local development
   cd backend
   pip install -r requirements.txt
   uvicorn app.main:app --reload --port 8000

   # In another terminal:
   cd frontend
   npm install
   npm run dev
   ```

3. **Verify health check**:
   ```bash
   curl http://localhost:8000/api/health
   # Should return: {"status":"healthy","services":{"database":"connected","api":"running"}}
   ```

---

## Test Suite

### 1. Database Migrations ✅
**Purpose**: Verify new columns are added automatically

**Steps**:
1. Check backend logs on startup
2. Should see: "Running X database migrations..." or "Database schema is up to date"
3. Verify no migration errors

**Expected Result**:
- New columns added: `total_tavily_credits`, `total_cost_usd`, `last_activity_at`, `stalled` (jobs table)
- New columns added: `tavily_credits_used`, `tavily_response_time`, `llm_tokens_used`, `llm_response_time` (companies table)

---

### 2. CSV Upload 📤
**Purpose**: Test CSV job creation and background processing

**Test File**: Create `test_upload.csv`
```csv
company_name
Anthropic
OpenAI
Mistral AI
```

**Steps**:
1. Open http://localhost:3000
2. Enter your name in "Your Name" field
3. Click "Upload CSV" tab
4. Select test CSV file
5. Click "Upload CSV"

**Expected Result**:
- Job appears in sidebar immediately with "pending" status
- Status changes to "running" within 1-2 seconds
- Progress bar updates in real-time
- Companies process one by one (1 second delay between each)
- Cost appears in job sidebar as companies complete
- Final status shows "completed" with total cost

**Verify**:
- [ ] Job created successfully
- [ ] Background processing starts automatically
- [ ] Progress bar updates in real-time
- [ ] Job sidebar shows total cost
- [ ] No errors in browser console
- [ ] No errors in backend logs

---

### 3. Single Company Lookup 🔍
**Purpose**: Test single company research

**Steps**:
1. Click "Single Lookup" tab
2. Enter your name (optional)
3. Enter company name: "Cohere"
4. Click "Research Company"

**Expected Result**:
- Job created with 1 company
- Processing starts immediately
- Company analyzed within 30-90 seconds
- Results displayed with cost information

**Verify**:
- [ ] Single lookup works
- [ ] Costs displayed correctly
- [ ] Company details show all 4 sections (Info, GPU Analysis, Score Breakdown, Cost & Performance)

---

### 4. Cancel Functionality ❌
**Purpose**: Test job cancellation (CRITICAL FIX)

**Steps**:
1. Upload CSV with 10+ companies
2. Wait for 2-3 companies to complete
3. Click "Cancel" button in job header

**Expected Result**:
- Backend logs show "Cancellation requested for job X"
- Job status changes to "cancelled" within 1-2 seconds
- Current company finishes, but no new companies start
- Progress bar stops updating
- Backend logs show "Job X was cancelled"

**Verify**:
- [ ] Cancel button stops the job
- [ ] Job status changes to "cancelled"
- [ ] No new companies are processed after cancel
- [ ] No errors in logs

**If Cancel Doesn't Work**:
- Check backend logs for "Cannot cancel job X: not running"
- This means task wasn't registered properly - report this issue

---

### 5. Cost Tracking 💰
**Purpose**: Verify Tavily and LLM cost tracking

**Steps**:
1. Research 2-3 companies
2. Expand a completed company row
3. Check "Cost & Performance" section

**Expected Result**:
- Tavily Cost shows ~$0.016 per company (2 credits × $0.008)
- Search Time shows 2-5 seconds typically
- LLM Tokens shows 1000-3000 tokens typically
- LLM Time shows 3-10 seconds typically

**Verify**:
- [ ] Tavily credits tracked (should be 2.0 per company for advanced search)
- [ ] Tavily cost calculated correctly (~$0.016/company)
- [ ] LLM tokens tracked (non-zero)
- [ ] Response times tracked for both APIs
- [ ] Job total cost = sum of all company costs
- [ ] Costs displayed in job sidebar and header

---

### 6. Retry Logic 🔄
**Purpose**: Test retry behavior on API failures

**Simulate Failure** (optional, advanced):
1. Temporarily block Tavily API in firewall/hosts
2. Try to research a company
3. Check backend logs

**Expected Log Output**:
```
WARNING - Attempt 1/4 failed for _perform_search: [error]. Retrying in 2.0s...
WARNING - Attempt 2/4 failed for _perform_search: [error]. Retrying in 4.0s...
WARNING - Attempt 3/4 failed for _perform_search: [error]. Retrying in 8.0s...
ERROR - All 3 retry attempts failed for _perform_search: [error]
```

**Verify**:
- [ ] Retries happen with exponential backoff (2s, 4s, 8s)
- [ ] After 3 retries, company marked as "failed"
- [ ] Error message stored in database
- [ ] Job continues with next company

---

### 7. Error Handling 🚨
**Purpose**: Test graceful error handling

**Steps**:
1. Research a fake company: "ThisCompanyDoesNotExistXYZ123"
2. Wait for completion
3. Expand the company row

**Expected Result**:
- Company status shows "failed" or "completed" with low scores
- Error message displayed in red banner (if failed)
- Job continues processing other companies
- No application crash

**Verify**:
- [ ] Failed companies don't stop the job
- [ ] Error messages displayed prominently
- [ ] Job shows X completed + Y failed counts

---

### 8. Health Monitoring ⚠️
**Purpose**: Test stalled job detection

**Steps**:
1. Start a job with multiple companies
2. Wait 5+ minutes without activity (simulated stall)
3. Refresh page or wait for polling

**Expected Result**:
- Orange warning banner appears above progress bar
- Message: "Job appears stalled - no activity for X minutes. Last activity: [timestamp]"
- AlertTriangle icon displayed

**Verify**:
- [ ] Stalled job warning appears after 5 minutes of inactivity
- [ ] Last activity timestamp displayed
- [ ] Warning banner has orange styling

**Note**: In normal operation, this shouldn't happen unless there's an actual problem

---

### 9. Delete Functionality 🗑️
**Purpose**: Test job deletion

**Steps**:
1. Complete a job fully
2. Click trash icon in job header
3. Confirm deletion

**Expected Result**:
- Job removed from sidebar
- All associated companies deleted
- Database cleaned up

**Verify**:
- [ ] Can't delete running jobs (disabled button)
- [ ] Can delete completed/failed jobs
- [ ] Job removed from list after deletion

---

### 10. CSV Export 📥
**Purpose**: Test results export

**Steps**:
1. Complete a job with multiple companies
2. Click "Export CSV" button

**Expected Result**:
- CSV file downloads: `research_results_X.csv`
- Contains all company data including:
  - Rank, Company Name, Priority Tier, Total Score
  - GPU tiers and scores
  - Funding information
  - Cost data (NEW)
  - Submitted by name

**Verify**:
- [ ] CSV downloads successfully
- [ ] All companies included
- [ ] Cost columns present (though cost export not yet added to CSV - future enhancement)
- [ ] Data formatted correctly

---

### 11. Frontend UI - Cost Display 💵
**Purpose**: Verify all cost displays work

**Check These Locations**:
1. **Job Sidebar** - Shows cost per job with DollarSign icon
2. **Job Header** - Shows "Total Cost: $X.XXX (Y credits)"
3. **Company Details** - Shows 4-row cost breakdown section
4. **Error Messages** - Red banner for failed companies

**Verify**:
- [ ] formatCost() displays correctly (< $0.001 for tiny amounts, $X.XXX format)
- [ ] formatDuration() displays correctly (ms/s/m/h)
- [ ] Icons display properly (DollarSign, Clock, Zap, AlertTriangle)
- [ ] Stalled job warning appears when appropriate

---

### 12. Performance Testing 🚀
**Purpose**: Verify timeouts and performance

**Test Scenarios**:

**A. Normal Operation**:
- Research 10 companies
- Track total time (should be ~20-40 seconds per company)
- Verify no timeouts

**B. Timeout Handling**:
- If using a slow network, some requests may timeout
- Should retry 3 times then mark as failed
- Job should continue

**Verify**:
- [ ] LLM calls timeout after 60 seconds
- [ ] Tavily calls timeout after 30 seconds
- [ ] No indefinite hangs
- [ ] Retries work correctly

---

## Known Issues / Limitations

1. **Cancel button**: Now properly cancels tasks - this was the main fix
2. **Persistent storage**: Production deployment needs persistent disk mounted
3. **Frontend polling**: Uses 3-second interval (could be optimized with WebSockets)
4. **No authentication**: Anyone can create jobs (by design for now)
5. **Rate limiting**: 1 second delay between companies (hardcoded, could be configurable)

---

## Regression Testing

After all tests pass, verify these haven't broken:

- [ ] User name field works (optional, stored as "Anonymous" if empty)
- [ ] Tier filtering works (HOT/WARM/WATCH/COLD buttons)
- [ ] Company expansion works (click row to expand/collapse)
- [ ] Scoring system unchanged (0-100 points)
- [ ] Priority tier calculation unchanged (75+ HOT, 55-74 WARM, etc.)
- [ ] Search quality unchanged (Tavily advanced search with 8 results)

---

## Success Criteria ✅

All features working if:
- ✅ Jobs run in background regardless of user session
- ✅ Cancel button stops jobs properly
- ✅ Costs tracked accurately for both Tavily and LLM
- ✅ Stalled job warnings appear when appropriate
- ✅ Error messages displayed clearly
- ✅ All UI elements display correctly
- ✅ No console errors
- ✅ Database migrations work automatically
- ✅ Retry logic works for transient failures
- ✅ Persistent disk configured for production

---

## Troubleshooting

**If tests fail, check**:

1. **Backend logs**:
   ```bash
   docker logs -f territory-planner-backend-dev
   # OR
   # Check terminal running uvicorn
   ```

2. **Frontend console**:
   - Open browser DevTools (F12)
   - Check Console tab for errors
   - Check Network tab for failed API calls

3. **Database**:
   ```bash
   # Check if migrations ran
   sqlite3 backend/data/territory_planner.db ".schema"
   ```

4. **API Keys**:
   - Verify CRUSOE_API_KEY is valid
   - Verify TAVILY_API_KEY is valid
   - Check backend logs for "Invalid API key" errors

---

## Next Steps After Testing

1. **If tests pass**: Deploy to production with persistent disk configured
2. **If cancel button fails**: Check backend logs and report issue
3. **If costs don't track**: Verify Tavily API returns usage data
4. **If UI issues**: Check browser console for errors

---

**Testing completed by**: _____________
**Date**: _____________
**All tests passed**: ☐ Yes  ☐ No (see notes below)

**Notes**:
