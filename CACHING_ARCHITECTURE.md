# Tavily Caching & Validation Architecture

## Overview

This document outlines the enhanced 3-phase research pipeline with Tavily data caching, validation, and intelligent reuse.

---

## Current Problems

1. **No data validation**: Tavily might return bad/irrelevant data, but we run expensive LLM analysis anyway
2. **No caching**: If a company is researched twice, we hit Tavily API again ($0.016 wasted)
3. **No verification**: We don't check if Tavily data was actually received before LLM processing
4. **Wasted LLM tokens**: Running full analysis on bad data wastes time and potentially costs money

---

## New 3-Phase Architecture

```
┌────────────────────────────────────────────────────────────────┐
│ PHASE 1: Tavily Data Fetching & Validation (with Caching)     │
├────────────────────────────────────────────────────────────────┤
│ For each company:                                               │
│   1. Check cache: Do we have verified Tavily data already?     │
│      YES → Skip to Phase 2 (saved $0.016!)                     │
│      NO  → Continue to step 2                                  │
│                                                                 │
│   2. Fetch from Tavily API                                     │
│      - Get 20 results with raw_content                         │
│      - Store raw response                                      │
│      - Track credits used                                      │
│                                                                 │
│   3. Lightweight LLM Validation (~200 tokens, ~1s)             │
│      Question: "Is this data valid for {company_name}?"        │
│      Checks:                                                    │
│        - Does data mention the company?                        │
│        - Is it business/tech info (not spam)?                  │
│        - At least 1 quality source?                            │
│        - Data not obviously wrong?                             │
│                                                                 │
│   4. Decision:                                                  │
│      VALID (confidence ≥ 0.6):                                 │
│        → Cache data in database                                │
│        → Mark as verified                                      │
│        → Proceed to Phase 2                                    │
│                                                                 │
│      INVALID (confidence < 0.6):                               │
│        → Log issues                                            │
│        → Retry fetch (up to 2 times)                           │
│        → If still invalid: mark as failed, skip Phase 2        │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│ PHASE 2: Full LLM Analysis & Scoring (Only on Verified Data)  │
├────────────────────────────────────────────────────────────────┤
│ For each company with verified data:                           │
│   1. Run full LLM analysis (~40k-60k tokens, ~15-30s)         │
│   2. Extract company info, GPU analysis, scores                │
│   3. Store results in database                                 │
│   4. Mark as completed                                         │
│                                                                 │
│ Skip companies with invalid/missing data                       │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│ PHASE 3: Results & Reporting                                   │
├────────────────────────────────────────────────────────────────┤
│ - Aggregate costs (accounting for cache hits)                  │
│ - Calculate savings from caching                               │
│ - Return ranked companies                                      │
└────────────────────────────────────────────────────────────────┘
```

---

## Database Schema Changes

### New fields in `Company` model:

```python
# Tavily data caching & verification
tavily_data_cached = Column(Boolean, default=False)
  # Whether we have cached Tavily data

tavily_data_verified = Column(Boolean, default=False)
  # Whether data passed validation

tavily_cached_at = Column(DateTime, nullable=True)
  # Timestamp of when data was cached

tavily_validation_message = Column(Text, nullable=True)
  # Validation result message

tavily_formatted_results = Column(Text, nullable=True)
  # Cached formatted results ready for LLM
```

---

## Benefits

### 1. Cost Savings
- **Cache hit**: $0.016 saved per company
- **Example**: Research 1,000 companies, 200 are repeats
  - Savings: 200 × $0.016 = **$3.20 saved**
- Over time with multiple jobs: **significant savings**

### 2. Speed Improvements
- **Cache hit**: Skip Tavily (~3s) + validation (~1s) = **4s faster per company**
- **Example**: 200 cached companies = **13 minutes saved**

### 3. Quality Improvements
- **Validation catches bad data**: Prevents wasting LLM analysis on garbage
- **Retry logic**: Gets better data if first fetch is poor
- **Cost per quality**: Only run expensive LLM on verified good data

### 4. Debugging & Transparency
- **Validation messages**: See why data failed
- **Cache tracking**: Know which companies are cached
- **Audit trail**: When data was cached, validation results

---

## Implementation Details

### Phase 1: Fetch & Validate

```python
async def fetch_and_validate_tavily_data(company, max_retries=2):
    # Check cache first
    if company.tavily_data_cached and company.tavily_data_verified:
        logger.info(f"Cache HIT: {company.name}")
        return company.tavily_formatted_results
    
    # Fetch from Tavily
    for attempt in range(max_retries):
        search_results = await search_service.search_company(company.name)
        formatted_results = format_for_llm(search_results)
        
        # Lightweight validation
        validation = await llm_service.validate_tavily_data(
            company.name,
            formatted_results
        )
        
        if validation['is_valid'] and validation['confidence'] >= 0.6:
            # VALID - cache it
            company.tavily_data_cached = True
            company.tavily_data_verified = True
            company.tavily_cached_at = datetime.utcnow()
            company.tavily_formatted_results = formatted_results
            company.tavily_validation_message = validation['message']
            db.commit()
            return formatted_results
        else:
            # INVALID - retry
            logger.warning(f"Invalid data for {company.name}, retrying...")
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
    
    # Max retries reached
    return None
```

### Phase 2: Full LLM Analysis

```python
async def run_full_llm_analysis(company, formatted_results):
    if formatted_results is None:
        company.status = CompanyStatus.FAILED
        company.error_message = "No valid Tavily data"
        return
    
    # Run expensive full analysis
    analysis = await llm_service.analyze_company(
        company.name,
        formatted_results
    )
    
    # Store results
    store_analysis_results(company, analysis)
    company.status = CompanyStatus.COMPLETED
    db.commit()
```

---

## Validation Logic

### Lightweight LLM Prompt

```
You are validating search results for: {company_name}

Search Results:
{first 2000 chars of results}

Is this data valid for analyzing GPU infrastructure needs?

Respond with JSON:
{
  "is_valid": true/false,
  "confidence": 0.0-1.0,
  "message": "Brief explanation",
  "issues": ["list", "of", "problems"]
}

Mark INVALID if:
- No results mention the company
- All results are spam/generic
- Company name completely wrong
- Less than 50 words of content
```

### Validation Thresholds

- **confidence ≥ 0.6**: Data is valid, cache and proceed
- **confidence < 0.6**: Data is invalid, retry or fail

### Retry Strategy

- **Attempt 1**: Immediate fetch
- **Attempt 2** (if invalid): Wait 2s, retry
- **Attempt 3** (if invalid): Wait 4s, retry
- **After 3 attempts**: Mark as failed, skip to next company

---

## Cache Strategy

### When to Use Cache

Always check cache first:
```python
if company.tavily_data_cached and company.tavily_data_verified:
    # Use cached data
    return company.tavily_formatted_results
```

### When to Invalidate Cache

Current approach: Never invalidate (data doesn't change much)

Future options:
- Age-based: Invalidate after 30 days
- Manual: Admin endpoint to clear cache
- Event-based: Company raises new funding, clear cache

### Cache Storage

- **Location**: SQLite database (same as everything else)
- **Size**: ~60k chars per company = ~60 KB
- **1,000 companies**: ~60 MB (negligible)

---

## Example: Job with Caching

### Scenario: 100 companies, 30 already researched before

```
PHASE 1: Tavily Fetching & Validation
  Checking cache...
  - 30 cache HITS (saved $0.48, 2 minutes)
  - 70 cache MISSES
  
  Fetching 70 companies from Tavily...
  - 65 fetches: valid data (cached for future)
  - 3 fetches: invalid, retried, then valid
  - 2 fetches: invalid after 3 attempts (failed)
  
  Phase 1 complete: 95 valid, 5 failed
  Time: ~15 seconds (vs ~3 minutes without caching)
  Cost: 70 × $0.016 = $1.12 (vs $1.60 without caching)

PHASE 2: Full LLM Analysis
  Analyzing 95 companies in batches of 10...
  Batch 1 (10 companies): 45s
  Batch 2 (10 companies): 42s
  ...
  Batch 10 (5 companies): 28s
  
  Phase 2 complete: 92 analyzed, 3 LLM failures
  Time: ~6 minutes

TOTAL:
  Time: 6.25 minutes (vs 15 minutes without caching)
  Cost: $1.12 Tavily + ~$1.80 LLM = ~$2.92
  Savings: $0.48 (16% on Tavily)
  Success: 92/100 (92%)
```

---

## Migration Plan

### Step 1: Add Database Fields ✅
- Add new columns to `Company` model
- Run migration to update schema

### Step 2: Implement Validation Function ✅
- Add `validate_tavily_data()` to LLM service
- Test with known good/bad data

### Step 3: Update Research Pipeline
- Replace `run_job_batched()` with caching version
- Add cache checking logic
- Add retry logic for invalid data

### Step 4: Test Thoroughly
- Test with 10 companies (no cache)
- Test with same 10 companies (cache hits)
- Test with companies that have bad data
- Verify validation catches issues

### Step 5: Deploy & Monitor
- Deploy to server
- Monitor validation failure rate
- Monitor cache hit rate
- Tune confidence threshold if needed

---

## Testing Strategy

### Test 1: Cache Miss → Cache Hit
```
1. Research "Anthropic" (first time)
   - Should fetch from Tavily
   - Should validate data
   - Should cache results
   
2. Research "Anthropic" again (second time)
   - Should use cache (no Tavily call)
   - Should skip validation
   - Should proceed directly to LLM
   
Expected:
  - First run: Tavily call logged
  - Second run: "Cache HIT" logged
  - Second run saves $0.016 and ~3 seconds
```

### Test 2: Invalid Data Retry
```
1. Research company with ambiguous name (e.g., "Foundry")
   - May return results for wrong company
   - Validation should catch mismatch
   - Should retry with better query
   
Expected:
  - First attempt: "Data INVALID" logged
  - Retry logged
  - Eventually succeeds or fails after 3 attempts
```

### Test 3: Batch with Mixed Cache
```
1. Upload CSV with 50 companies
   - 20 previously researched (cached)
   - 30 new companies
   
Expected:
  - 20 cache hits logged
  - 30 Tavily fetches
  - Total time: ~2 minutes (vs ~4 minutes)
  - Cost: $0.48 (vs $0.80)
```

---

## Configuration

### New Environment Variables

```bash
# Tavily Caching
ENABLE_TAVILY_CACHING=true         # Use cache when available
TAVILY_VALIDATION_THRESHOLD=0.6    # Min confidence to accept data
TAVILY_MAX_RETRIES=2               # Retry invalid fetches

# Cache Management
TAVILY_CACHE_TTL_DAYS=30          # Days before cache expires (future)
```

---

## Monitoring & Metrics

### Key Metrics to Track

1. **Cache Hit Rate**
   - `cache_hits / (cache_hits + cache_misses)`
   - Target: >20% after initial population

2. **Validation Failure Rate**
   - `invalid_validations / total_validations`
   - Target: <5%

3. **Retry Success Rate**
   - `successful_retries / total_retries`
   - Target: >80%

4. **Cost Savings**
   - `cache_hits × $0.016`
   - Track cumulative savings

5. **Time Savings**
   - `cache_hits × 4 seconds`
   - Track cumulative time saved

### Dashboard (Future)

```
Tavily Caching Stats (Last 30 Days)
=====================================
Total Companies Researched: 2,450
Cache Hits:                   540 (22%)
Cache Misses:               1,910 (78%)

Cost Savings:    $8.64
Time Savings:    36 minutes

Validation Stats:
  Valid:         1,850 (97%)
  Invalid:          60 (3%)
  Retries:          45
  Retry Success:    38 (84%)
```

---

## Future Enhancements

### 1. Smart Cache Invalidation
- Track company funding events
- Auto-refresh cache on major news
- Allow manual cache refresh

### 2. Cache Sharing
- Share cache across users/jobs
- Build global company knowledge base
- Reduce redundant Tavily calls

### 3. Incremental Updates
- Update only changed fields
- Keep historical cache versions
- Track data staleness

### 4. Validation Tuning
- A/B test confidence thresholds
- Machine learning to improve validation
- Custom validation per industry

---

## Rollback Plan

If caching causes issues:

```bash
# Disable caching
ENABLE_TAVILY_CACHING=false

# Clear all caches (if needed)
UPDATE companies SET tavily_data_cached = 0, tavily_data_verified = 0;
```

System falls back to always fetching fresh data.

---

## Summary

The 3-phase architecture with Tavily caching provides:

✅ **Cost savings**: 16-30% on Tavily (depending on cache hit rate)
✅ **Speed improvements**: 4 seconds per cached company
✅ **Quality improvements**: Validate before expensive LLM analysis
✅ **Retry logic**: Get better data if first fetch is bad
✅ **Transparency**: Clear logging and validation messages

**Next Steps:**
1. Review this architecture
2. Approve implementation plan
3. Test with small dataset
4. Deploy to production
5. Monitor and tune

---

**Status**: Design complete, partial implementation done
**Estimated effort**: 4-6 hours to complete and test
**Risk**: Low (can disable caching if issues arise)
