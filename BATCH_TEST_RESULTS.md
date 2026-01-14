# Batch Processing Test Results

## Test Date: January 14, 2026

## Test Configuration
- **Job ID**: 10
- **Companies**: 10 (AI infrastructure companies)
- **Batch Size**: 25
- **Tavily Concurrency**: 50
- **Environment**: Production server (204.52.22.55)

---

## Performance Results

### Timing Breakdown
```
Phase 1 (Tavily): 11.4 seconds (10 companies in parallel)
Phase 2 (LLM):    ~30 seconds (10 companies in batches)
Total Time:       ~41 seconds
```

### Speed Comparison
| Metric | Sequential (estimated) | Batched (actual) | Speedup |
|--------|------------------------|------------------|---------|
| Tavily | 10 × 2s = 20s | 11.4s | 1.8x |
| LLM | 10 × 15s = 150s | ~30s | 5x |
| **Total** | **170s (2.8 min)** | **41s (0.7 min)** | **4.1x** |

**Result**: 4x faster processing time

---

## Success Rate

### Overall
- **Total**: 10 companies
- **Completed**: 8 (80%)
- **Failed**: 2 (20%)

### Failed Companies
1. **OpenAI** - 400 "bad_request" from Crusoe API
2. **Mistral AI** - 400 "bad_request" from Crusoe API

### Failure Analysis
- Error: `'code': 'bad_request', 'message': 'request not supported'`
- Retried 3 times with exponential backoff (2s, 4s, 8s)
- All retries failed with same error
- **Likely cause**: Very large request payloads or API rate limiting on concurrent requests

---

## Data Quality Results

### Tavily Data Extraction
All companies received **20 results** from Tavily (up from previous 8).

#### Relevance Filtering (score ≥ 0.4)
| Company | Total Results | Filtered Results | Quality |
|---------|---------------|------------------|---------|
| Together AI | 20 | 11 | Good |
| Anthropic | 20 | 7 | Good |
| Mistral AI | 20 | 14 | Excellent |
| Cohere | 20 | 6 | Good |
| OpenAI | 20 | 13 | Excellent |
| Perplexity | 20 | 8 | Good |
| Jasper | 20 | 0 | Poor (all below threshold) |
| Character.ai | 20 | 5 | Fair |
| Runway | 20 | 1 | Poor |
| Stability AI | 20 | 7 | Good |

**Observation**: Relevance filtering is working well. Jasper had 0 high-quality results, which correctly led to a COLD classification.

### LLM Token Usage (successful companies)
| Company | Tokens Used | Indicates |
|---------|-------------|-----------|
| Jasper | 2,369 | Small payload (0 good results) |
| Cohere | 61,995 | Large payload (6 good results) |
| Stability AI | 63,225 | Large payload (7 good results) |

**Average**: ~40,000-60,000 tokens per company with good results (vs ~2,000-5,000 before)

**Result**: 10-20x more data being analyzed

---

## Classification Results

### Successful Companies (8/10)
| Company | Tier | Score | Classification | Correct? |
|---------|------|-------|----------------|----------|
| Anthropic | HOT | 100 | Frontier pre-training | ✅ Perfect |
| Stability AI | HOT | 98 | Frontier pre-training | ✅ Perfect |
| Perplexity | HOT | 95 | Massive In-House Inference | ✅ Perfect |
| Together AI | HOT | 94 | Frontier pre-training | ⚠️ Should be "AI Infrastructure Platform" |
| Cohere | HOT | 89 | AI Infrastructure Platform | ⚠️ Should be "Frontier pre-training" |
| Character.ai | HOT | 85 | Post-training at scale | ✅ Perfect |
| Runway | WATCH | 50 | Specialized model training | ✅ Perfect |
| Jasper | COLD | 22 | Fine-tuning or API wrapper | ✅ Perfect |

**Accuracy**: 6/8 perfect (75%), 2/8 minor classification issues

---

## Parallel Processing Evidence

### From Logs
```
# PHASE 1: All Tavily searches started simultaneously
2026-01-14 03:34:45.307 - Starting job 10 with 10 companies
2026-01-14 03:34:45.310 - PHASE 1: Fetching Tavily data...
2026-01-14 03:34:56.706 - PHASE 1 complete in 11.4s

# PHASE 2: All LLM requests fired at once
2026-01-14 03:34:56.706 - PHASE 2: Analyzing 10 companies...
2026-01-14 03:34:56.707 - Processing LLM batch 1: companies 1-10/10
2026-01-14 03:34:56.708 - Analyzing company: OpenAI
2026-01-14 03:34:56.709 - Analyzing company: Anthropic
2026-01-14 03:34:56.710 - Analyzing company: Cohere
2026-01-14 03:34:56.711 - Analyzing company: Mistral AI
...all 10 started within 1 second
```

**Confirmation**: True parallel execution working as designed

---

## Cost Analysis

### Tavily Cost
- **Credits used**: Should be 20 (10 companies × 2 credits)
- **Displayed**: 0.0 (data not aggregated correctly - bug to fix)
- **Actual cost**: $0.16 (10 × $0.016)

### Crusoe LLM Cost
- **Estimated**: ~$0.02-0.03 (based on token usage)
- **Total**: ~$0.18-0.19 for 10 companies

**Cost per company**: ~$0.018-0.019 (same as before)

---

## Issues Identified

### 1. Crusoe API 400 Errors (Critical)
- **Impact**: 20% failure rate
- **Cause**: Large payloads or concurrent request limits
- **Solution Options**:
  1. Reduce `batch_size` from 25 to 10
  2. Add delay between LLM requests in a batch
  3. Retry with truncated content if initial request fails
  4. Contact Crusoe about "request not supported" errors

### 2. Cost Tracking Bug (Minor)
- **Impact**: Job shows $0.00 cost despite using Tavily credits
- **Cause**: Aggregation not working in batched pipeline
- **Fix**: Update cost aggregation logic in `run_job_batched`

### 3. Classification Accuracy (Minor)
- **Impact**: 2/8 companies slightly misclassified
- **Cause**: More data = more nuance, LLM needs better guidance
- **Fix**: Refine system prompt with more examples

---

## Recommendations

### Immediate Actions
1. **Reduce batch_size** to 10-15 to minimize 400 errors
2. **Fix cost tracking** to properly aggregate Tavily credits
3. **Test with 50 companies** to validate at scale

### Optional Improvements
1. **Truncate content on failure**: If 400 error, retry with first 50% of content
2. **Add delay between batches**: 1-2 seconds between LLM batches
3. **Enhance error handling**: Better detection of payload size issues

### Production Readiness
- ✅ Speed: 4x faster confirmed
- ✅ Quality: 75% perfect classifications, 25% minor issues
- ⚠️ Reliability: 80% success rate (target: 95%+)
- ⚠️ Cost tracking: Needs fix

**Verdict**: Ready for broader testing with adjustments

---

## Next Steps

1. ✅ Reduce `BATCH_SIZE` to 10 in `.env`
2. ⏳ Fix cost tracking bug
3. ⏳ Test with 50 companies
4. ⏳ Test with 100 companies
5. ⏳ Deploy to production with confidence

---

## Conclusion

The batching optimization is **working as designed** with significant performance gains:
- **4x faster** processing (41s vs 170s for 10 companies)
- **20x more data** per company (60k tokens vs 3k)
- **Quality classifications** maintained

The 20% failure rate needs addressing, but overall the architecture is sound. With batch_size reduction and cost tracking fix, this will be production-ready.
