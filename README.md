# Territory Planner

AI-powered company research and ranking tool for identifying GPU infrastructure sales prospects.

## Overview

This application:
1. Ingests a CSV list of company names
2. Researches each company using web search (Tavily) and AI analysis (Crusoe Cloud LLM)
3. Classifies companies by their GPU infrastructure needs
4. Ranks and prioritizes companies for sales outreach

## Tech Stack

- **Backend**: Python + FastAPI
- **Frontend**: React + Vite
- **Database**: SQLite
- **AI**: Crusoe Cloud (Llama-3.3-70B-Instruct)
- **Search**: Tavily API

## Quick Start (Local Development)

### 1. Set up environment

Create a `.env` file in the project root:

```bash
# Crusoe Cloud Inference API
CRUSOE_API_KEY=your_crusoe_api_key
CRUSOE_API_BASE_URL=https://api.crusoe.ai/v1/
CRUSOE_MODEL=meta-llama/Llama-3.3-70B-Instruct

# Tavily Search API
TAVILY_API_KEY=your_tavily_api_key

# Database
DATABASE_URL=sqlite:///./data/territory_planner.db

# App Settings
APP_ENV=development
LOG_LEVEL=INFO
```

### 2. Start the backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 3. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

### 4. Open the app

Navigate to http://localhost:3000

## Usage

1. **Upload CSV**: Click "Upload CSV" and select a file with company names
   - CSV should have a column named `company_name`, `name`, or `Company`
   - Or be a single-column CSV with company names

2. **Monitor Progress**: Watch as companies are researched one by one

3. **View Results**: Companies are ranked by GPU infrastructure need score
   - **HOT (70-100)**: High priority - actively training models or serving at scale
   - **WARM (50-69)**: Worth qualifying - potential GPU needs
   - **WATCH (30-49)**: Future potential - may develop needs
   - **COLD (0-29)**: Low priority - API wrappers, minimal GPU needs

4. **Export**: Download results as CSV for your CRM

## Scoring System

### GPU Use Case Tiers

| Tier | Description | Points |
|------|-------------|--------|
| S | Frontier pre-training (Anthropic, Mistral) | 40 |
| A | Post-training at scale (Cursor, Character.ai) | 35 |
| B | Massive inference (Perplexity) | 30 |
| C | AI infrastructure platform (Together AI) | 30 |
| D | Specialized model training (Harvey, Abridge) | 20 |
| E | Fine-tuning / API wrappers | 5 |

### Additional Scoring

- **Scale & Budget** (0-30): Based on funding amount
- **Timing Signals** (0-20): Recent raises, ML hiring, scaling news
- **Confidence** (0-10): Quality of data found

## Production Deployment (Crusoe Cloud)

### Using Docker Compose

```bash
# Build and run both services
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Manual Deployment

1. Provision a VM on Crusoe Cloud (Ubuntu recommended)
2. Install Docker and Docker Compose
3. Clone the repository
4. Create `.env` file with production credentials
5. Run `docker-compose up -d`

### Recommended VM Specs

- **CPU**: 2+ cores
- **RAM**: 4GB+
- **Storage**: 20GB+ (for database)

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/jobs/upload` | Upload CSV, start job |
| GET | `/api/jobs/` | List all jobs |
| GET | `/api/jobs/{id}` | Get job details with companies |
| GET | `/api/jobs/{id}/progress` | Get job progress (polling) |
| POST | `/api/jobs/{id}/cancel` | Cancel running job |
| DELETE | `/api/jobs/{id}` | Delete job |
| GET | `/api/jobs/{id}/export` | Export results as CSV |

## Sample CSV

```csv
company_name
Cursor
Perplexity
Together AI
Fireworks AI
Anthropic
Cohere
Mistral AI
Character.ai
Harvey AI
Jasper
Notion
Linear
```

## Cost Estimates

For 1000 companies:
- **Tavily Search**: ~$10 (1000 searches at $0.01/search)
- **Crusoe LLM**: ~$2-3 (based on token usage)
- **Total**: ~$12-15 per 1000 companies

## Troubleshooting

### Backend won't start
- Check `.env` file exists and has correct values
- Ensure `data/` directory exists
- Check API keys are valid

### Search failing
- Verify Tavily API key
- Check rate limits (1000/month on free tier)

### LLM analysis failing
- Verify Crusoe API key
- Check model name is correct
- Review logs for specific error messages

## License

MIT



