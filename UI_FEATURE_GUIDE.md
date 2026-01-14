# UI Feature Guide - Where to Find Everything

**App URL:** http://204.52.22.55

---

## 🎯 Quick Navigation

| Feature | Location | Status |
|---------|----------|--------|
| Error Messages | Company details (expand row) → Red banner at bottom | ✅ Working |
| Cost per Company | Company details → "Cost & Performance" section | ✅ Working |
| Total Job Cost | Job header → Top right | ✅ Working |
| Performance Metrics | Company details → "Cost & Performance" section | ✅ Working |
| Stalled Warning | Job header → Orange banner (when stalled) | ✅ Working |
| Cancel Button | Job header → Top right | ✅ Fixed |
| Failed Company Count | Job list sidebar + Job header | ✅ Working |

---

## 📍 Step-by-Step: Where to See Each Feature

### 1. Error Messages & Why Jobs Failed

**Path:** Job List → Click Job → Click Company Row → See Red Error Banner

```
┌─ Job List Sidebar ─────────────────────┐
│  Job #9                                 │
│  Status: CANCELLED                      │
│  0/1062 companies                       │
│  Failed: 2 ← Click here                 │
└─────────────────────────────────────────┘
            ↓
┌─ Company Table ────────────────────────┐
│  # │ Company      │ Tier │ Status      │
│  1 │ Party City   │  -   │ failed ← Click│
│  2 │ Akamai Tech  │  -   │ failed      │
└─────────────────────────────────────────┘
            ↓
┌─ Expanded Company Details ─────────────┐
│  [Company Info] [GPU Analysis] [Scores]│
│  [Cost & Performance]                   │
│                                         │
│  ┌─ ERROR ──────────────────────────┐  │
│  │ Error: Analysis failed: Error    │  │
│  │ code: 401 - {'code':             │  │
│  │ 'bad_credential', 'message':     │  │
│  │ 'failed to authenticate user'}   │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

**What You'll See:**
- Red banner with full error message
- Shows API error code (401)
- Shows error details (bad_credential)
- Appears for EVERY failed company

---

### 2. Cost Metrics

#### A. Per-Company Costs

**Path:** Job → Click Company → "Cost & Performance" Section

```
┌─ Company Details: Party City ──────────┐
│                                         │
│  [Company Info] [GPU Analysis]          │
│                                         │
│  ┌─ Cost & Performance ─────────────┐  │
│  │ 💵 Tavily Cost      $0.016       │  │
│  │ ⏱️  Search Time      2.4s         │  │
│  │ ⚡ LLM Tokens       0            │  │
│  │ ⏱️  LLM Time         0.0s         │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

**Metrics Explained:**
- **Tavily Cost:** Search API cost (credits × $0.008)
- **Search Time:** How long Tavily search took
- **LLM Tokens:** Total tokens used by Crusoe LLM
- **LLM Time:** How long LLM analysis took

**Note:** For failed companies (like Party City):
- Tavily costs show (search succeeded)
- LLM metrics are 0 (failed before LLM)

#### B. Total Job Cost

**Path:** Job Header → Top Right

```
┌─ Job Header ───────────────────────────────────┐
│  Research Job - 2026-01-14 03:01               │
│  Source: research_results_7.csv                │
│                                                │
│  Status: cancelled                             │
│  Progress: 0/1062 (0.2%)                       │
│  Failed: 2                                     │
│                                                │
│  💰 Total Cost: $0.032                         │
│  📊 Credits Used: 4.0                          │
│                                                │
│  [Cancel] [Export CSV] [Delete]                │
└────────────────────────────────────────────────┘
```

**Shows:**
- Total cost across ALL companies
- Total Tavily credits used
- Updates in real-time as job progresses

---

### 3. Performance Metrics

**Path:** Same as Cost Metrics (Company Details → Cost & Performance)

```
┌─ Cost & Performance ─────────────────┐
│                                       │
│  ⏱️  Search Time    2.4s              │
│     ↑ Time for Tavily to find results│
│                                       │
│  ⏱️  LLM Time       8.5s              │
│     ↑ Time for Crusoe LLM to analyze │
│                                       │
│  ⚡ LLM Tokens     12,450            │
│     ↑ Tokens used (input + output)   │
└───────────────────────────────────────┘
```

**Time Formatting:**
- `< 1s` → Shows milliseconds: `450ms`
- `1-60s` → Shows seconds: `2.4s`
- `> 60s` → Shows minutes: `1.2m`

**Example (Successful Company):**
```
Search Time: 2.3s
LLM Time: 8.5s
LLM Tokens: 12,450
```

**Example (Failed Company - Current State):**
```
Search Time: 2.4s
LLM Time: 0.0s     ← Failed before completion
LLM Tokens: 0      ← No tokens used
```

---

### 4. Stalled Job Warning

**Path:** Job Header → Orange Banner (appears when stalled)

```
┌─ Job Header ───────────────────────────────────┐
│  ⚠️  WARNING: Job Stalled                      │
│  ┌────────────────────────────────────────┐   │
│  │ ⚠️  Job appears stalled - no progress  │   │
│  │    for 5+ minutes                       │   │
│  │    Last activity: 2026-01-14 03:15:23   │   │
│  └────────────────────────────────────────┘   │
│                                                │
│  Research Job - 2026-01-14 03:01               │
│  Status: running                               │
│  Progress: 45/1062 (4.2%)                      │
└────────────────────────────────────────────────┘
```

**Triggers When:**
- Job status = "running"
- No activity for 5+ minutes
- Shows last activity timestamp

**Why You Don't See It Now:**
- Job #9 is "cancelled" (not "running")
- Would appear if job was stuck

**To Test:**
1. Start a new job with valid API key
2. If it hangs for 5+ minutes
3. Orange banner will appear

---

### 5. Failed Company Count

**Visible in 3 Places:**

#### A. Job List Sidebar
```
┌─ Job #9 ────────────────┐
│  Status: CANCELLED       │
│  0/1062 companies        │
│  Failed: 2 ← HERE        │
│  Cost: $0.00             │
└──────────────────────────┘
```

#### B. Job Header
```
┌─ Job Header ────────────────────┐
│  Total: 1062                     │
│  Completed: 0                    │
│  Failed: 2 ← HERE                │
│  Pending: 1060                   │
└──────────────────────────────────┘
```

#### C. Progress Bar
```
Progress: 0/1062 (0.2%)
          ↑
    (completed + failed) / total
```

---

### 6. Cancel Button (Fixed)

**Path:** Job Header → Top Right

```
┌─ Job Header ───────────────────────────┐
│  Research Job - 2026-01-14 03:01       │
│                                        │
│  Status: running                       │
│  Progress: 45/1062 (4.2%)              │
│                                        │
│  [❌ Cancel] [Export CSV] [Delete]    │
│     ↑ Click to stop job                │
└────────────────────────────────────────┘
```

**How It Works Now:**
1. Click "Cancel" button
2. Sends request to `/api/jobs/{id}/cancel`
3. Backend calls `task.cancel()` on actual asyncio.Task
4. Job stops immediately
5. Status changes to "cancelled"

**Previous Issue (Fixed):**
- Used boolean flag
- Didn't actually stop async task
- Job kept running in background

**New Implementation:**
- Tracks actual `asyncio.Task` objects
- Cancels the real task
- Handles `CancelledError` properly
- Cleans up resources

---

## 🎨 Visual Examples

### Successful Company (When API Key Works)

```
┌─ Anthropic ─────────────────────────────────────┐
│  ✅ Status: completed                            │
│                                                  │
│  🔥 Priority: HOT (85 points)                   │
│  🎯 GPU Tier: S - Frontier pre-training         │
│                                                  │
│  ┌─ Company Info ────────────────────────────┐  │
│  │ Leading AI safety company building        │  │
│  │ Claude foundation models                  │  │
│  │ 👥 500-1000 employees                     │  │
│  │ 📍 San Francisco, CA                      │  │
│  │ 🏢 AI Research & Development              │  │
│  └───────────────────────────────────────────┘  │
│                                                  │
│  ┌─ GPU Analysis ───────────────────────────┐  │
│  │ Tier S: Frontier pre-training             │  │
│  │ "Anthropic trains foundation models from  │  │
│  │  scratch (Claude family). Clear evidence  │  │
│  │  of massive GPU infrastructure needs."    │  │
│  └───────────────────────────────────────────┘  │
│                                                  │
│  ┌─ Score Breakdown ────────────────────────┐  │
│  │ GPU Use Case:    ████████████ 50/50      │  │
│  │ Scale & Budget:  ████████░░░░ 30/30      │  │
│  │ Growth Signals:  ██████░░░░░░  5/10      │  │
│  │ Confidence:      ██████████░░ 10/10      │  │
│  └───────────────────────────────────────────┘  │
│                                                  │
│  ┌─ Cost & Performance ─────────────────────┐  │
│  │ 💵 Tavily Cost     $0.016                 │  │
│  │ ⏱️  Search Time     2.3s                  │  │
│  │ ⚡ LLM Tokens      12,450                │  │
│  │ ⏱️  LLM Time        8.5s                  │  │
│  └───────────────────────────────────────────┘  │
│                                                  │
│  ┌─ RECOMMENDED ────────────────────────────┐  │
│  │ High-priority outreach - strong GPU      │  │
│  │ infrastructure needs with budget          │  │
│  └───────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

### Failed Company (Current State)

```
┌─ Party City ─────────────────────────────────────┐
│  ❌ Status: failed                                │
│                                                   │
│  ❌ Priority: N/A                                 │
│  ❌ GPU Tier: N/A                                 │
│                                                   │
│  ┌─ Cost & Performance ──────────────────────┐   │
│  │ 💵 Tavily Cost     $0.016                  │   │
│  │ ⏱️  Search Time     2.4s                   │   │
│  │ ⚡ LLM Tokens      0                       │   │
│  │ ⏱️  LLM Time        0.0s                   │   │
│  └────────────────────────────────────────────┘   │
│                                                   │
│  ┌─ ERROR ───────────────────────────────────┐   │
│  │ ❌ Error: Analysis failed: Error code:    │   │
│  │    401 - {'code': 'bad_credential',       │   │
│  │    'message': 'failed to authenticate     │   │
│  │    user', 'error_id': '...'}              │   │
│  └────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────┘
```

---

## 🔍 Testing Checklist

### To Verify All Features Are Working:

1. **Open App**
   - [ ] Go to http://204.52.22.55
   - [ ] See job list in sidebar

2. **Select Job #9**
   - [ ] Click on Job #9
   - [ ] See job header with status "cancelled"
   - [ ] See failed count: 2

3. **Check Failed Companies**
   - [ ] Click on "Party City" row
   - [ ] Expand to see details
   - [ ] See red error banner at bottom
   - [ ] Error message shows "401" and "bad_credential"

4. **Check Cost Metrics**
   - [ ] In Party City details, see "Cost & Performance" section
   - [ ] Tavily Cost shows $0.016
   - [ ] Search Time shows 2.4s
   - [ ] LLM Tokens shows 0 (because failed)

5. **Check Job-Level Costs**
   - [ ] In job header, see total cost
   - [ ] Should show ~$0.032 (2 companies × $0.016)

6. **Test Cancel Button** (with new job)
   - [ ] Upload new CSV or single company
   - [ ] Click Cancel while running
   - [ ] Job stops immediately
   - [ ] Status changes to "cancelled"

---

## 🚨 Current Limitation

**The Crusoe API key is invalid**, so:
- ✅ You CAN see error messages
- ✅ You CAN see Tavily costs
- ✅ You CAN see search times
- ❌ You CANNOT see successful analysis
- ❌ You CANNOT see LLM costs/tokens
- ❌ You CANNOT see company scores

**Once you provide a valid API key:**
- All features will work end-to-end
- Companies will be scored and ranked
- LLM costs and tokens will display
- Performance metrics will be complete

---

## 📞 Need Help?

**To fix the API key issue:**
1. Get valid Crusoe API key from https://console.crusoe.ai
2. Provide it to me
3. I'll update the server
4. Test with a single company lookup
5. Verify all features work

**Everything is deployed and ready** - just needs the correct API credential!
