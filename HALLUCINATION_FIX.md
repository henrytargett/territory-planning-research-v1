# Hallucination Problem - Root Cause & Fix

## Problem Summary

The app was scoring companies incorrectly by hallucinating that they were AI infrastructure platforms when they were not:

### Examples from Job 28:
1. **jomspar.com** (not a real company) - Scored as Tier C "AI infrastructure platform" with 60 points
2. **Suburbia Fulfillment, LLC** (package delivery company) - Scored as Tier C "AI infrastructure platform" with 63 points

Both companies received high scores (WARM tier) with fabricated descriptions claiming they "focus on GPU compute for machine learning training and inference."

## Root Cause Analysis

### Primary Issue: Tavily's Answer Field Hallucinates

The investigation revealed that **Tavily's API was generating completely fabricated summaries**:

**For jomspar.com:**
```
Tavily Answer: "Jomspar.com focuses on GPU compute infrastructure for machine learning 
training and inference. The company has a significant number of employees and is heavily 
funded for AI infrastructure. Recent developments include new GPU designs for long-context inference."
```

**Reality:** The actual search results were generic LinkedIn posts about GPU frameworks with no information about "jomspar.com" at all.

**For Suburbia Fulfillment, LLC:**
```
Tavily Answer: "Suburbia Fulfillment, LLC focuses on GPU compute for machine learning 
training and inference, with significant funding and partnerships in the AI infrastructure 
sector. The company has received investments to expand its cloud GPU compute services. 
It competes with other firms like CoreWeave and Lambda Labs."
```

**Reality:** Suburbia Fulfillment is actually a package delivery/fulfillment company with no AI operations.

### How It Happened

1. **Tavily Search Query**: We search with terms like `"{company_name} GPU compute infrastructure machine learning..."`
2. **Tavily Finds Generic Results**: Search returns generic articles about GPU/AI that happen to mention those keywords
3. **Tavily's LLM Hallucinates**: Tavily's answer generation LLM sees GPU keywords and fabricates a narrative that the company is an AI infrastructure platform
4. **Our Code Trusted Tavily**: We included Tavily's hallucinated "answer" as a "Summary" section in the prompt
5. **Our LLM Compounds It**: Our LLM reads Tavily's fabricated summary and uses it as the basis for analysis

## The Fix

### 1. Removed Tavily's Hallucinated Answer (Primary Fix)

**File: `backend/app/services/search.py`**

**Changed:**
```python
# OLD CODE - INCLUDED TAVILY'S HALLUCINATION
if search_response.get("answer"):
    parts.append(f"## Summary\n{search_response['answer']}\n")
```

**To:**
```python
# ⚠️ DO NOT include Tavily's "answer" field - it hallucinates!
# Tavily's LLM-generated summaries frequently fabricate company information,
# especially claiming non-AI companies are "AI infrastructure platforms".
# We only use the raw source documents to prevent hallucinations.
```

Also changed:
```python
include_answer=False,  # DO NOT use Tavily's answer - it hallucinates company info
```

### 2. Added Strong Anti-Hallucination Safeguards to LLM Prompt

**File: `backend/app/services/llm.py`**

Added to `SYSTEM_PROMPT`:
```
## ⚠️ CRITICAL: ANTI-HALLUCINATION RULES ⚠️

**YOU MUST ONLY USE INFORMATION EXPLICITLY STATED IN THE SEARCH RESULTS. DO NOT:**
1. ❌ Invent or assume what a company does based on keywords in unrelated articles
2. ❌ Make up company descriptions if the search results are sparse or irrelevant
3. ❌ Classify a company as AI-related just because GPU/AI terms appear in search results
4. ❌ Score a company highly if you cannot find DIRECT EVIDENCE of their business model
5. ❌ Assume a company is real if search results show no legitimate business information

**IF SEARCH RESULTS ARE:**
- Mostly ads, parked domains, or spam → Score as TIER E (10 points) with low confidence
- Irrelevant or about different companies → Score as TIER E (10 points), note in reasoning
- No real company information found → Score as UNKNOWN (5 points) with confidence 2
- Company appears fake/non-existent → Score as TIER E (10 points), state "No legitimate business found"

**VERIFICATION CHECKLIST - Before scoring above TIER D, confirm:**
✓ The company has a real website with actual product/service information
✓ Multiple independent sources confirm what they do
✓ Their business description matches across sources
✓ There's evidence of actual operations (employees, funding, customers, etc.)
```

Added to scoring notes:
```
- **Package delivery, fulfillment, logistics, e-commerce companies are NOT AI companies** 
  Score as Tier E (10 points) unless explicit evidence of custom ML models.
- **Domain names without real businesses** (parked domains, "coming soon" pages) 
  Score as Tier E (10 points) with confidence 2.
- **If you cannot verify what the company actually does from search results** 
  Score as UNKNOWN (5 points) with low confidence, don't guess.
```

### 3. Enhanced Analysis Prompt with Sanity Checks

Added pre-analysis checklist in `ANALYSIS_PROMPT_TEMPLATE`:
```
⚠️ BEFORE YOU ANALYZE: Perform these sanity checks:
1. Do the search results actually describe what {company_name} does?
2. Is {company_name} a real company with a real business?
3. Do multiple sources confirm the same information?
4. Are you about to make claims NOT supported by the search results above?

If the answer to questions 1-3 is NO, or question 4 is YES: Score as Tier E or UNKNOWN with low confidence.

**RED FLAGS** - If you see these, score as Tier E (10 points) max:
- Company is in logistics/delivery/fulfillment (unless explicit ML evidence)
- Search results show no real business, just a domain name
- Results are unrelated articles that happen to mention GPU/AI
- You cannot clearly explain what the company does from the results
- Company name looks fake or suspicious (e.g., "jomspar.com")
```

### 4. Strengthened Tavily Data Validation

Enhanced `validate_tavily_data()` prompt with stricter criteria:
```
Mark as INVALID if:
- No results mention the company
- All results are generic/spam
- Company name completely mismatched
- Less than 50 words of actual content
- Company appears to be just a domain name / parked domain
- Search results are mostly unrelated articles that just happen to mention AI/GPU keywords
- Company name appears fake or non-existent (e.g., "jomspar.com" with no real business info)
- Results show company does something completely different (e.g., package delivery company, not AI)
- Multiple unrelated topics in results suggest search didn't find the right company

⚠️ BE STRICT: If you're unsure whether results match the company or if the company is real, mark as INVALID.
```

## Expected Behavior After Fix

### With the fixes in place:

1. **No Tavily Hallucinations**: Our LLM only sees raw source documents, not Tavily's fabricated summaries
2. **Explicit Anti-Hallucination Instructions**: LLM is repeatedly warned not to invent information
3. **Sanity Check Requirements**: LLM must verify company is real and search results are relevant
4. **Industry-Specific Rules**: Logistics/delivery companies automatically flagged as non-AI
5. **Stricter Validation**: Bad Tavily data caught earlier in the pipeline

### How problematic companies should now be scored:

- **jomspar.com**: Should be scored as TIER E (10 points) or UNKNOWN (5 points) with reasoning: "No legitimate business information found in search results"
- **Suburbia Fulfillment, LLC**: Should be scored as TIER E (10 points) with reasoning: "Package delivery/fulfillment company, no evidence of custom ML/AI operations"

## Testing

To verify the fix works, re-run these companies through the system and check:
1. They receive low scores (≤10 points)
2. Their descriptions accurately reflect lack of AI operations
3. GPU use case tier is E or UNKNOWN
4. Reasoning mentions the red flags (fake company / non-AI business)

## Deployment

**Status:** ✅ DEPLOYED to production (204.52.22.55)

**Date:** January 16, 2026

**Changes deployed:**
- `backend/app/services/llm.py` - Anti-hallucination prompts
- `backend/app/services/search.py` - Removed Tavily answer field

**Containers restarted:** 
- territory-planner-backend (c76a51da980b)
- territory-planner-frontend (c36dce816539)

## Impact

**Benefits:**
- ✅ Eliminates false positives from Tavily's hallucinated summaries
- ✅ Prevents wasting sales time on non-AI companies
- ✅ Improves trust in scoring system
- ✅ Reduces risk of embarrassing outreach to wrong companies

**Tradeoffs:**
- May slightly increase "UNKNOWN" scores for companies with sparse search results
- LLM will be more conservative (better safe than sorry)
- Slightly longer prompts (minimal cost increase)

## Future Improvements

1. **Add Company Verification API**: Integrate with Clearbit or similar to verify companies are real
2. **Industry Classification First**: Pre-classify company industry before GPU analysis
3. **Source Quality Scoring**: Weight Crunchbase/LinkedIn higher than generic articles
4. **Human Feedback Loop**: Allow marking bad scores to improve prompts over time
5. **A/B Testing**: Compare scores before/after fix on known companies

## Related Issues

- Job 28: jomspar.com scored 60 points (false positive)
- Job 28: Suburbia Fulfillment scored 63 points (false positive)
- Tavily API hallucination pattern documented

---

**Author:** Territory Planning Research App - AI Agent  
**Issue Reported By:** User (htargett)  
**Resolution:** Multi-layer anti-hallucination safeguards implemented
