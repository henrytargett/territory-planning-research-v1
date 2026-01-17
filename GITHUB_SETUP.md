# GitHub Setup Instructions

## Your Repository is Ready to Push!

All files have been committed locally. Now you need to create the GitHub repository and push.

### Option 1: Create Repository via GitHub Web Interface (Recommended)

1. **Go to GitHub:**
   - Visit: https://github.com/new
   - Or go to: https://github.com/htargett and click "New" repository

2. **Configure Repository:**
   ```
   Repository name: territory-planning-research
   Description: AI-powered company research for GPU infrastructure sales
   Visibility: Public (or Private if you prefer)
   
   ⚠️ IMPORTANT: Do NOT initialize with README, .gitignore, or license
   (We already have these files)
   ```

3. **Create the Repository:**
   - Click "Create repository"

4. **Push Your Code:**
   ```bash
   cd "/Users/htargett/Desktop/Territory Planning Research APp"
   git push -u origin main
   ```

### Option 2: Install GitHub CLI and Create from Terminal

```bash
# Install GitHub CLI
brew install gh

# Login to GitHub
gh auth login

# Create repository
cd "/Users/htargett/Desktop/Territory Planning Research APp"
gh repo create territory-planning-research --public --source=. --remote=origin --push

# This will:
# - Create the repo on GitHub
# - Set up the remote
# - Push your code automatically
```

---

## What Has Been Committed

✅ **36 files committed** including:

**Backend:**
- FastAPI application (`backend/app/`)
- Research pipeline with async processing
- Tavily search integration
- Crusoe Cloud LLM integration
- SQLite database models
- Docker configuration

**Frontend:**
- React application with Vite
- Real-time job monitoring UI
- Company details and scoring display
- Docker + Nginx configuration

**Documentation:**
- README.md (project overview)
- ARCHITECTURE.md (complete system architecture)
- CLEANUP_PLAN.md (deployment & cleanup guide)
- .env.example (configuration template)

**Deployment:**
- docker-compose.yml (development)
- docker-compose.prod.yml (production)
- deploy.sh (automated deployment script)
- setup-server.sh (server initialization)

**Sample Data:**
- sample_companies.csv
- test_companies.csv

---

## After Pushing to GitHub

### Update Your Server Deployment

Once the code is on GitHub, update your production server:

```bash
# SSH into server
ssh -i ~/.ssh/crusoe_key ubuntu@204.52.22.55

# Navigate to app directory
cd /opt/territory-planner

# Initialize git (if not already)
git init

# Add remote
git remote add origin git@github.com:htargett/territory-planning-research.git

# Pull latest code
git pull origin main

# Or clone fresh (recommended)
cd /opt
sudo rm -rf territory-planner
git clone git@github.com:htargett/territory-planning-research.git
cd territory-planning-research

# Copy your .env file back
cp ~/.env .env

# Deploy
cd deploy
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d --build
```

---

## Future Workflow

Once set up, making changes is simple:

```bash
# 1. Make changes locally
vim backend/app/services/llm.py

# 2. Test locally
docker-compose up

# 3. Commit and push
git add .
git commit -m "fix: add timeout to LLM calls"
git push origin main

# 4. Deploy to server
ssh -i ~/.ssh/crusoe_key ubuntu@204.52.22.55 \
  "cd /opt/territory-planning-research && git pull && \
   cd deploy && docker-compose -f docker-compose.prod.yml up -d --build"
```

---

## Repository URL

Once created, your repository will be at:
**https://github.com/htargett/territory-planning-research**

Clone URL (SSH): `git@github.com:htargett/territory-planning-research.git`
Clone URL (HTTPS): `https://github.com/htargett/territory-planning-research.git`
