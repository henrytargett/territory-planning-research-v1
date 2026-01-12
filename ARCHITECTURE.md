# Territory Planner - Architecture Documentation

## Current State Analysis (as of Jan 12, 2026)

### Overview
Territory Planner is an AI-powered company research tool that uses web search (Tavily) and LLM analysis (Crusoe Cloud) to rank companies by their GPU infrastructure needs for sales prospecting.

---

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────┐
│                      User Browser                        │
└─────────────────────────┬───────────────────────────────┘
                          │
                          │ HTTP/REST
                          │
┌─────────────────────────▼───────────────────────────────┐
│              Frontend (React + Vite)                     │
│  - UI Components (App.jsx)                               │
│  - Real-time polling (3 sec intervals)                   │
│  - Served by Nginx in production                         │
└─────────────────────────┬───────────────────────────────┘
                          │
                          │ /api/* requests
                          │
┌─────────────────────────▼───────────────────────────────┐
│            Backend (FastAPI + Python)                    │
│  ┌─────────────────────────────────────────────────┐    │
│  │  API Routes (/api/jobs/*)                       │    │
│  │  - Upload CSV, Start/Stop jobs                  │    │
│  │  - Get job status, Export results               │    │
│  └─────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Research Pipeline (Async)                      │    │
│  │  - Orchestrates search + LLM analysis           │    │
│  │  - Processes companies sequentially              │    │
│  │  - 1 second rate limiting between companies     │    │
│  └─────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Services                                        │    │
│  │  - SearchService: Tavily API integration        │    │
│  │  - LLMService: Crusoe Cloud API integration     │    │
│  └─────────────────────────────────────────────────┘    │
└──────────────────┬──────────────────────────────────────┘
                   │
                   │ SQLAlchemy ORM
                   │
┌──────────────────▼──────────────────────────────────────┐
│            SQLite Database                               │
│  - research_jobs table                                   │
│  - companies table (with scores, analysis results)       │
└──────────────────────────────────────────────────────────┘

External APIs:
├─ Tavily API (Web Search)
└─ Crusoe Cloud API (LLM - Llama 3.3 70B)
```

---

## Current Infrastructure

### Local Development Environment
**Location:** `/Users/htargett/Desktop/Territory Planning Research APp`

**Issues:**
- ❌ Not a git repository yet
- ❌ Contains production data (`backend/data/territory_planner.db` - 1,498 companies)
- ❌ Space name has spaces (makes CLI operations harder)
- ✅ Clean structure with proper Dockerfiles
- ✅ Proper `.gitignore` in place

### Production Server
**IP:** `204.52.22.55` (Crusoe Cloud VM)
**Location:** `/opt/territory-planner`

**Running Services:**
```
Container: territory-planner-backend (FastAPI)
  - Status: Up 4 days (healthy)
  - Image: deploy-backend
  - Ports: 8000 (internal only)

Container: territory-planner-frontend (Nginx)
  - Status: Up 4 days
  - Image: deploy-frontend
  - Ports: 80 → 80 (public)
```

**Storage:**
- **Primary disk:** `/dev/vda1` (128GB) - 4.5GB used (ephemeral)
- **Attached disk:** `/dev/vdb` (20GB) - **NOT MOUNTED** ⚠️
- **Database location:** `/var/lib/docker/volumes/deploy_app-data/_data/` (8.5MB)
- **Current issue:** Data is stored on ephemeral disk, not the persistent 20GB volume

---

## Issues & Technical Debt

### 1. **Data Storage on Ephemeral Disk** 🚨 CRITICAL
- Database is stored in Docker volume on `/dev/vda1` (ephemeral)
- The 20GB persistent disk (`/dev/vdb`) is attached but **NOT mounted**
- If VM reboots, all data will be lost

### 2. **No Git Repository**
- Code is not version controlled
- No commit history
- Cannot track changes or collaborate effectively

### 3. **Inconsistent Docker Compose Files**
- `docker-compose.yml` (root) - uses `./data:/app/data` mount
- `docker-compose.prod.yml` (deploy/) - uses named volume `app-data`
- `docker-compose.dev.yml` - another variant
- **Confusion about which file to use when**

### 4. **Environment Variable Management**
- `.env` file stored in root directory
- Deployment script copies it to server
- Not clear if server has correct values
- No example `.env.example` file for reference

### 5. **Slow LLM Performance**
- LLM API calls sometimes take 10+ minutes with retries
- No timeout configuration
- No circuit breaker pattern
- Job with 1,062 companies will take 4-6 hours

### 6. **Limited Observability**
- No structured logging
- No metrics collection
- Hard to debug issues without SSH access
- Frontend only shows high-level job status

### 7. **Single-Threaded Processing**
- Companies processed sequentially (one at a time)
- Could parallelize with proper async/await patterns
- Rate limiting is appropriate but could be smarter

### 8. **No Backup Strategy**
- Database has valuable research data
- No automated backups configured
- Manual backup requires SSH + Docker commands

---

## Recommended Architecture (Clean State)

### Directory Structure
```
territory-planner/
├── .github/
│   └── workflows/
│       └── deploy.yml              # CI/CD pipeline
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI app
│   │   ├── config.py               # Settings
│   │   ├── database.py             # DB connection
│   │   ├── models.py               # SQLAlchemy models
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   └── jobs.py            # Job endpoints
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── research.py        # Research pipeline
│   │       ├── search.py          # Tavily integration
│   │       └── llm.py             # Crusoe Cloud integration
│   ├── tests/                      # Unit tests
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── index.css
│   ├── public/
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── package.json
│   └── vite.config.js
├── infrastructure/                 # Deployment configs
│   ├── docker-compose.yml         # Local development
│   ├── docker-compose.prod.yml    # Production
│   ├── deploy.sh                  # Deployment script
│   └── setup-server.sh            # Server initialization
├── docs/
│   ├── ARCHITECTURE.md            # This file
│   ├── DEPLOYMENT.md              # Deployment guide
│   └── API.md                     # API documentation
├── .env.example                    # Template for .env
├── .gitignore
├── README.md
└── docker-compose.yml             # Default: points to infrastructure/
```

### Persistent Storage Solution

**Server Configuration:**
```bash
# Mount persistent disk at /mnt/data
/dev/vdb → /mnt/data (ext4)

# Store data on persistent disk
/mnt/data/
├── territory-planner/
│   ├── database/
│   │   └── territory_planner.db
│   ├── backups/                   # Automated backups
│   └── uploads/                   # Uploaded CSVs (if needed)
```

**Docker Compose Volume Mapping:**
```yaml
volumes:
  - /mnt/data/territory-planner/database:/app/data
```

---

## Performance Improvements

### 1. **Timeout Configuration**
Add timeouts to LLM calls to prevent 10+ minute hangs:
```python
# In llm.py
response = await client.chat.completions.create(
    timeout=60.0,  # 60 second timeout
    ...
)
```

### 2. **Retry Strategy**
Implement exponential backoff with max retries:
```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
```

### 3. **Parallel Processing (Optional)**
Process multiple companies in parallel with rate limiting:
```python
async def process_batch(companies, max_concurrent=5):
    semaphore = asyncio.Semaphore(max_concurrent)
    tasks = [process_with_limit(company, semaphore) for company in companies]
    await asyncio.gather(*tasks)
```

### 4. **Caching**
Cache search results to avoid duplicate API calls:
- Use company name as cache key
- TTL: 7 days
- Store in database or Redis

---

## Git Strategy

### Branch Structure
```
main               # Production-ready code
├── develop        # Integration branch
└── feature/*      # Feature branches
```

### Commit Conventions
Use conventional commits:
- `feat:` New features
- `fix:` Bug fixes
- `refactor:` Code restructuring
- `docs:` Documentation
- `chore:` Maintenance tasks

### Example:
```bash
git commit -m "feat(backend): add timeout to LLM API calls"
git commit -m "fix(frontend): correct company status display"
git commit -m "docs: update deployment guide for persistent disk"
```

---

## Deployment Strategy

### 1. **Initial Setup (One-time)**
```bash
# Mount persistent disk
sudo mkfs.ext4 /dev/vdb
sudo mkdir -p /mnt/data
sudo mount /dev/vdb /mnt/data
echo '/dev/vdb /mnt/data ext4 defaults 0 0' | sudo tee -a /etc/fstab

# Create directory structure
sudo mkdir -p /mnt/data/territory-planner/database
sudo chown -R ubuntu:ubuntu /mnt/data/territory-planner
```

### 2. **Update Docker Compose**
Modify `infrastructure/docker-compose.prod.yml`:
```yaml
volumes:
  - /mnt/data/territory-planner/database:/app/data
```

### 3. **Migrate Existing Data**
```bash
# Copy current database to persistent disk
docker cp territory-planner-backend:/app/data/territory_planner.db \
  /mnt/data/territory-planner/database/
```

### 4. **Deploy from Git**
```bash
# On local machine
git push origin main

# On server
cd /opt/territory-planner
git pull origin main
docker-compose -f infrastructure/docker-compose.prod.yml up -d --build
```

---

## Monitoring & Operations

### Health Checks
- **Backend:** `GET /api/health`
- **Frontend:** `GET /` (Nginx)
- **Database:** Check file exists and is writable

### Backup Strategy
```bash
# Daily automated backup (cron job)
0 2 * * * docker exec territory-planner-backend \
  sqlite3 /app/data/territory_planner.db ".backup '/app/data/backup-$(date +\%Y\%m\%d).db'"

# Weekly backup to S3 (optional)
0 3 * * 0 aws s3 cp /mnt/data/territory-planner/database/ \
  s3://territory-planner-backups/ --recursive
```

### Logs
```bash
# View logs
docker logs -f territory-planner-backend
docker logs -f territory-planner-frontend

# Export logs for analysis
docker logs territory-planner-backend > backend-logs.txt
```

---

## Security Considerations

### 1. **Environment Variables**
- Never commit `.env` file to git
- Use secrets management in production (e.g., Vault, AWS Secrets Manager)
- Rotate API keys regularly

### 2. **CORS Configuration**
Current: `allow_origins=["*"]` (too permissive)
Should: `allow_origins=["http://204.52.22.55"]`

### 3. **Rate Limiting**
Add rate limiting to prevent API abuse:
```python
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)

@app.post("/api/jobs/upload")
@limiter.limit("10/hour")
async def upload_csv(...):
```

---

## Migration Checklist

- [ ] Initialize Git repository
- [ ] Create `.env.example` file
- [ ] Reorganize directory structure
- [ ] Mount persistent disk on server
- [ ] Update Docker Compose files
- [ ] Migrate existing database
- [ ] Test deployment
- [ ] Set up automated backups
- [ ] Update documentation
- [ ] Add CI/CD pipeline (optional)

---

## Cost Optimization

### Current Costs (estimated)
- **Tavily API:** ~$10 per 1,000 companies
- **Crusoe Cloud LLM:** ~$2-3 per 1,000 companies
- **VM Hosting:** ~$20-40/month (estimate)
- **Total:** ~$12-15 per 1,000 companies + hosting

### Optimization Opportunities
1. **Cache search results** → Save ~50% on Tavily costs for reruns
2. **Batch LLM requests** → Potential token savings
3. **Use smaller VM** → Current usage is low, could downsize
4. **Implement smart retry logic** → Reduce wasted API calls

---

## Future Enhancements

### Short-term
- [ ] Add timeout and retry configuration
- [ ] Implement proper error handling
- [ ] Add progress indicators for individual companies
- [ ] Export failed companies for manual review

### Medium-term
- [ ] Parallel processing with rate limiting
- [ ] Search result caching
- [ ] User authentication
- [ ] Multiple job types (single lookup, batch, scheduled)

### Long-term
- [ ] Multi-tenancy support
- [ ] Custom scoring models per user
- [ ] Integration with CRM systems (Salesforce, HubSpot)
- [ ] Real-time notifications (webhooks, email)
