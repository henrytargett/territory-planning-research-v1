# Territory Planning Research Application - Complete Description

## Application Overview

The Territory Planning Research Application is an AI-powered sales prospecting tool designed to identify and rank companies based on their potential need for GPU infrastructure services. The system operates as a two-phase research pipeline that combines web search intelligence with large language model analysis to classify companies into actionable sales tiers. Built on a modern microservices architecture, the application processes batch CSV uploads containing company names and produces detailed research reports with scoring, classification, and prioritization recommendations.

The application serves two distinct sales use cases through separate research workflows: IaaS Targets (companies that need to purchase and operate their own GPU infrastructure) and Managed Inference Targets (companies that purchase reserved inference capacity through managed providers like Fireworks AI, Baseten, or Together.ai). Each workflow uses specialized search queries, LLM prompts, and scoring criteria tailored to identify the specific buyer persona and infrastructure needs.

## System Architecture

The application consists of three primary components: a React-based frontend, a FastAPI backend service, and a SQLite database. The frontend provides a web interface for uploading CSV files, monitoring job progress in real-time, viewing detailed company research results, and exporting data. The backend orchestrates the research pipeline, integrating with external APIs for web search (Tavily) and AI analysis (Crusoe Cloud's Llama-3.3-70B-Instruct model). The database stores all research jobs, company records, raw search results, LLM responses, and computed scores.

The research pipeline follows a sequential workflow: when a user uploads a CSV file, the backend creates a research job and processes each company through four stages. First, it performs a web search using Tavily API with domain-filtered queries targeting business and technology sources like Crunchbase, LinkedIn, TechCrunch, and VentureBeat. The search returns up to 10 results per company, including full-page content (raw_content) rather than just snippets, providing comprehensive context for analysis. Second, the search results are formatted into a structured prompt, filtering results by relevance score (minimum 0.2) and sorting by quality. Third, the formatted results are sent to the Crusoe Cloud LLM with a specialized system prompt that defines the analysis framework and anti-hallucination rules. Fourth, the LLM's JSON response is parsed and stored in the database, including company information, GPU use case classification, scoring breakdowns, and final priority tier assignment.

## Managed Inference Workflow - Detailed Process

The Managed Inference workflow is specifically designed to identify companies that are likely to purchase reserved inference capacity through managed providers rather than building their own GPU infrastructure. This workflow differs fundamentally from the IaaS workflow in its search strategy, analysis criteria, and scoring methodology.

### Search Phase

The Managed Inference search query uses a broad, general approach: "{company_name} AI features machine learning inference API deployment model serving scale". This intentionally casts a wide net to find any company with AI features, rather than searching for specific infrastructure terms. The philosophy is "search broad, filter with LLM" - Tavily finds general AI content, and the LLM identifies managed inference signals from that content. This approach successfully captures companies like Gong, Notion, and Cursor that use managed inference but don't publicly blog about specific providers or infrastructure details.

The search returns up to 10 results with full-page content, filtered to include only results with relevance scores above 0.2. Results are sorted by score (highest first) and formatted into a structured prompt that includes source URLs, titles, relevance scores, and complete content. The system explicitly excludes Tavily's AI-generated "answer" field to prevent hallucinations, using only raw source documents.

### LLM Analysis Phase

The Managed Inference analysis uses a specialized system prompt that defines the analyst's role as identifying companies likely to purchase reserved inference capacity. The prompt emphasizes critical distinctions: managed inference targets use providers like Fireworks, Baseten, Together.ai, or Anyscale rather than running their own Kubernetes clusters or GPU fleets. Infrastructure providers themselves are explicitly excluded from being targets.

The analysis prompt requests structured JSON output containing company research data (description, funding, employees, industry) and GPU analysis with a specific focus on inference scale and managed platform adoption. The scoring system uses four dimensions: gpu_use_case (representing inference scale tier), scale_budget (representing managed platform adoption), growth_signals (user growth, hiring, funding), and confidence (data quality).

### Classification Tiers

Managed Inference companies are classified into five tiers based on their inference scale and managed platform usage. Tier S (Enterprise-scale) represents massive user bases with AI as core functionality and clear signals of reserved capacity or dedicated endpoints, scoring 50 points. Tier A (High-volume) indicates strong product usage with likely reserved capacity and some evidence of managed inference usage, scoring 45 points. Tier B (Production) represents live AI products at scale but not massive, or partial evidence of managed inference usage, scoring 35 points. Tier C (Small-scale/Experimental) indicates early adoption or low volume with weak scale signals, scoring 25 points. Tier D (API Wrapper/Low Scale) represents basic API usage without scale needs, scoring 10 points. Companies that cannot be determined from available information are classified as UNKNOWN with 5 points.

### Scoring Methodology

The gpu_use_case score (0-50 points) represents inference scale and maps directly to the tier system. The scale_budget score (0-30 points) represents managed platform adoption: 30 points for confirmed managed provider usage, 20 points for strong hints of managed endpoints or reserved capacity, 10 points for possible but unclear managed usage, and 0 points for no evidence. Growth signals (0-10 points) add points for rapid user growth (+4), active hiring of AI/ML roles (+3), and recent funding or expansion (+3). Confidence (0-10 points) reflects data quality: 10 for high confidence with multiple sources and clear evidence, 5 for medium confidence with some information found, and 2 for low confidence with little information.

The total score determines the final priority tier: HOT (70-100 points) labeled as "ENTERPRISE" for Managed Inference, WARM (50-69 points) labeled as "HIGH-VOLUME", WATCH (30-49 points) labeled as "PRODUCTION", and COLD (0-29 points) labeled as "SMALL-SCALE". These labels differ from the IaaS workflow to reflect the different buyer persona and sales approach.

### Key Signals and Indicators

The LLM identifies positive signals indicating managed inference usage: mentions of managed inference providers (Fireworks, Baseten, Together.ai, Anyscale), references to "dedicated endpoints", "reserved capacity", or "provisioned throughput", engineering blogs about scaling inference without managing GPUs, high-volume AI product usage (coding assistants, productivity AI, real-time AI), and open-weights models served via managed APIs (Llama 3, Mistral, Qwen).

Negative signals suggesting low or no managed inference usage include: running own Kubernetes or GPU fleet (these are IaaS targets, not managed inference targets), pure API wrappers with no scale, and no evidence of managed inference usage. The system is designed to distinguish between companies that use managed inference platforms versus those that build their own infrastructure, as these represent different sales opportunities.

### Data Caching and Validation

The system includes a sophisticated caching mechanism to reduce costs and improve performance. Before performing a Tavily search, the system checks if cached, verified data exists for the company name across any previous job. If cached data is found and validated, it skips the Tavily API call entirely, saving $0.016 per company and approximately 3 seconds of processing time. When new Tavily data is retrieved, it undergoes lightweight LLM validation to ensure quality before caching. The validation checks for relevance, data quality, and potential issues like fake companies or irrelevant results. Only validated data is cached for future use.

### Cost and Performance

The Managed Inference workflow costs approximately $0.019 per company: $0.016 for Tavily search (2 credits at $0.008 per credit) and $0.003 for LLM analysis (approximately 40,000 tokens at Crusoe Cloud's pricing). Processing time averages 10-15 seconds per company: 2-3 seconds for Tavily search, 1-2 seconds for validation (if enabled), and 6-10 seconds for LLM analysis. The system processes companies in parallel batches to optimize throughput, with configurable batch sizes and delays between batches to respect API rate limits.

### Output and Export

The frontend displays Managed Inference results with specialized labels and visual indicators. Companies are sorted by total score, with color-coded tier badges showing "ENTERPRISE", "HIGH-VOLUME", "PRODUCTION", or "SMALL-SCALE" instead of the IaaS labels. The detailed company view shows inference scale tier, managed platform adoption score, growth signals, and confidence level. Users can export results as CSV with columns specific to Managed Inference targets, including inference_scale_tier, inference_scale_label, score_inference_scale, and score_managed_platform_adoption fields.

The application successfully processes large batches (100+ companies) with high accuracy, identifying companies like Notion, Cursor, Retool, and Gong as strong Managed Inference targets based on their AI product usage patterns and infrastructure choices. The broad search query combined with intelligent LLM filtering ensures that companies using managed inference platforms are correctly identified even when they don't publicly disclose their infrastructure providers.
