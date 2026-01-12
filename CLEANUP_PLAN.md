# Territory Planner - Cleanup & Standardization Plan

## Executive Summary

This document outlines the step-by-step plan to:
1. ✅ Move data to persistent disk (prevent data loss)
2. ✅ Initialize Git repository and push to GitHub
3. ✅ Standardize project structure
4. ✅ Clean up Docker configuration
5. ✅ Establish proper deployment workflow

**Estimated Time:** 2-3 hours
**Risk Level:** Low (with proper backups)
**Downtime Required:** ~5 minutes

---

## Phase 1: Critical - Fix Data Storage (IMMEDIATE)

### Problem
Database is stored on ephemeral disk. If VM reboots, all data is lost.

### Solution
Mount the 20GB persistent disk and move database there.

### Steps

#### 1.1 Backup Current Database
```bash
# SSH into server
ssh -i ~/.ssh/crusoe_key ubuntu@204.52.22.55

# Create backup
docker exec territory-planner-backend \
  sqlite3 /app/data/territory_planner.db \
  ".backup '/app/data/backup-$(date +%Y%m%d-%H%M%S).db'"

# Copy backup to home directory (safety)
docker cp territory-planner-backend:/app/data/backup-*.db ~/
```

#### 1.2 Mount Persistent Disk
```bash
# Check if disk has filesystem (should be empty)
sudo blkid /dev/vdb

# Create filesystem if needed
sudo mkfs.ext4 /dev/vdb

# Create mount point
sudo mkdir -p /mnt/data

# Mount the disk
sudo mount /dev/vdb /mnt/data

# Make it permanent (survives reboots)
echo '/dev/vdb /mnt/data ext4 defaults,nofail 0 2' | sudo tee -a /etc/fstab

# Verify mount
df -h /mnt/data
```

#### 1.3 Create Directory Structure
```bash
# Create app directories on persistent disk
sudo mkdir -p /mnt/data/territory-planner/database
sudo mkdir -p /mnt/data/territory-planner/backups
sudo mkdir -p /mnt/data/territory-planner/uploads

# Set ownership
sudo chown -R ubuntu:ubuntu /mnt/data/territory-planner

# Verify
ls -la /mnt/data/territory-planner/
```

#### 1.4 Migrate Database
```bash
# Copy current database to persistent disk
docker cp territory-planner-backend:/app/data/territory_planner.db \
  /mnt/data/territory-planner/database/

# Verify file integrity
ls -lh /mnt/data/territory-planner/database/territory_planner.db
```

#### 1.5 Update Docker Compose
```bash
cd /opt/territory-planner/deploy

# Edit docker-compose.prod.yml
# Change volume from:
#   volumes:
#     - app-data:/app/data
# To:
#   volumes:
#     - /mnt/data/territory-planner/database:/app/data
```

#### 1.6 Restart with New Configuration
```bash
# Stop containers
docker-compose -f docker-compose.prod.yml down

# Remove old volume (optional, to clean up)
docker volume rm deploy_app-data

# Start with new configuration
docker-compose -f docker-compose.prod.yml up -d

# Verify database is accessible
docker exec territory-planner-backend ls -lh /app/data/
docker exec territory-planner-backend sqlite3 /app/data/territory_planner.db "SELECT COUNT(*) FROM research_jobs;"
```

**Expected downtime:** ~2-3 minutes

---

## Phase 2: Initialize Git Repository

### 2.1 Prepare Local Repository
```bash
cd "/Users/htargett/Desktop/Territory Planning Research APp"

# Create .env.example (template)
cat > .env.example << 'EOF'
# Crusoe Cloud Inference API
CRUSOE_API_KEY=your_crusoe_api_key_here
CRUSOE_API_BASE_URL=https://api.crusoe.ai/v1/
CRUSOE_MODEL=meta-llama/Llama-3.3-70B-Instruct

# Tavily Search API
TAVILY_API_KEY=your_tavily_api_key_here

# Database
DATABASE_URL=sqlite:///./data/territory_planner.db

# App Settings
APP_ENV=development
LOG_LEVEL=INFO
EOF

# Remove local database (it's in .gitignore anyway)
rm -f backend/data/territory_planner.db

# Initialize git
git init

# Add all files
git add .

# Initial commit
git commit -m "Initial commit: Territory Planner v1.0

- FastAPI backend with async research pipeline
- React frontend with real-time job monitoring
- Tavily API integration for web search
- Crusoe Cloud LLM integration (Llama 3.3 70B)
- SQLite database with job and company tracking
- Docker Compose configuration for deployment
- GPU use case classification (Tier S-E)
- Priority scoring system (HOT/WARM/WATCH/COLD)"
```

### 2.2 Create GitHub Repository
```bash
# Create repo on GitHub (use gh CLI or web interface)
gh repo create territory-planner --public --source=. --remote=origin

# Or manually:
# 1. Go to github.com/new
# 2. Name: territory-planner
# 3. Description: AI-powered company research for GPU infrastructure sales
# 4. Public/Private: Choose based on preference
# 5. Don't initialize with README (we have one)

# Add remote (if created manually)
git remote add origin git@github.com:YOUR_USERNAME/territory-planner.git

# Push to GitHub
git branch -M main
git push -u origin main
```

---

## Phase 3: Reorganize Project Structure

### 3.1 Create Clean Directory Structure
```bash
cd "/Users/htargett/Desktop/Territory Planning Research APp"

# Create new structure
mkdir -p infrastructure
mkdir -p docs

# Move deployment files
mv deploy/* infrastructure/
rmdir deploy

# Move docker compose files
mv docker-compose.yml infrastructure/docker-compose.dev.yml
mv docker-compose.dev.yml infrastructure/  # if different
mv infrastructure/docker-compose.prod.yml infrastructure/

# Create symlink for convenience (optional)
ln -s infrastructure/docker-compose.dev.yml docker-compose.yml

# Move documentation
mv ARCHITECTURE.md docs/
mv CLEANUP_PLAN.md docs/

# Commit changes
git add .
git commit -m "refactor: reorganize project structure

- Move deployment configs to infrastructure/
- Move documentation to docs/
- Create .env.example template"

git push origin main
```

### 3.2 Update Deployment Script
Update paths in `infrastructure/deploy.sh`:
```bash
# Change APP_DIR to point to correct docker-compose file
# Update all paths from deploy/ to infrastructure/
```

---

## Phase 4: Standardize Docker Configuration

### 4.1 Create Master Docker Compose File
Create `infrastructure/docker-compose.yml`:
```yaml
# Master configuration - DO NOT EDIT
# For dev: docker-compose -f infrastructure/docker-compose.dev.yml up
# For prod: Use deploy.sh script

# This file documents the common structure
```

### 4.2 Update Production Config
Edit `infrastructure/docker-compose.prod.yml`:
```yaml
version: '3.8'

services:
  backend:
    build:
      context: ../backend
      dockerfile: Dockerfile
    container_name: territory-planner-backend
    restart: always
    volumes:
      - /mnt/data/territory-planner/database:/app/data  # PERSISTENT DISK
      - ../.env:/app/.env:ro
    environment:
      - APP_ENV=production
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - app-network

  frontend:
    build:
      context: ../frontend
      dockerfile: Dockerfile
    container_name: territory-planner-frontend
    restart: always
    ports:
      - "80:80"
    depends_on:
      - backend
    networks:
      - app-network

networks:
  app-network:
    driver: bridge
```

### 4.3 Update Development Config
Edit `infrastructure/docker-compose.dev.yml`:
```yaml
version: '3.8'

services:
  backend:
    build: ../backend
    container_name: territory-planner-backend-dev
    ports:
      - "8000:8000"
    volumes:
      - ../backend:/app  # Mount source for hot reload
      - ../data:/app/data
      - ../.env:/app/.env:ro
    environment:
      - APP_ENV=development
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  frontend:
    build: ../frontend
    container_name: territory-planner-frontend-dev
    ports:
      - "3000:3000"
    volumes:
      - ../frontend/src:/app/src  # Mount source for hot reload
    depends_on:
      - backend
```

---

## Phase 5: Update Server Deployment

### 5.1 Update Server Repository
```bash
# SSH into server
ssh -i ~/.ssh/crusoe_key ubuntu@204.52.22.55

cd /opt/territory-planner

# Add git remote (if not already)
git init
git remote add origin git@github.com:YOUR_USERNAME/territory-planner.git

# Or just clone fresh
cd /opt
sudo rm -rf territory-planner
git clone git@github.com:YOUR_USERNAME/territory-planner.git
cd territory-planner

# Copy .env file
cp ~/backup-.env .env  # or recreate it

# Deploy with new structure
cd infrastructure
docker-compose -f docker-compose.prod.yml up -d --build
```

### 5.2 Verify Deployment
```bash
# Check containers
docker ps

# Check database
docker exec territory-planner-backend ls -lh /app/data/

# Check app is working
curl http://localhost/api/health
curl http://204.52.22.55/api/health

# Check logs
docker logs -f territory-planner-backend
```

---

## Phase 6: Establish Deployment Workflow

### 6.1 Create Deployment Script
Update `infrastructure/deploy.sh`:
```bash
#!/bin/bash
set -e

if [ -z "$1" ]; then
    echo "Usage: ./deploy.sh user@server-ip"
    exit 1
fi

SERVER=$1
SSH_KEY="${SSH_KEY:-$HOME/.ssh/crusoe_key}"
APP_DIR="/opt/territory-planner"

echo "=== Deploying Territory Planner ==="

# Pull latest code on server
echo "Pulling latest code..."
ssh -i $SSH_KEY $SERVER "cd $APP_DIR && git pull origin main"

# Rebuild and restart
echo "Rebuilding containers..."
ssh -i $SSH_KEY $SERVER "cd $APP_DIR/infrastructure && docker-compose -f docker-compose.prod.yml up -d --build"

# Show status
echo ""
echo "=== Deployment Complete ==="
ssh -i $SSH_KEY $SERVER "docker ps"

# Health check
echo ""
echo "=== Health Check ==="
sleep 5
ssh -i $SSH_KEY $SERVER "curl -f http://localhost/api/health"
```

### 6.2 Deployment Process
```bash
# On local machine

# 1. Make changes
vim backend/app/services/llm.py

# 2. Test locally
docker-compose -f infrastructure/docker-compose.dev.yml up

# 3. Commit and push
git add .
git commit -m "fix: add timeout to LLM API calls"
git push origin main

# 4. Deploy to production
cd infrastructure
./deploy.sh ubuntu@204.52.22.55

# 5. Verify
open http://204.52.22.55
```

---

## Phase 7: Set Up Automated Backups

### 7.1 Create Backup Script
```bash
# On server
cat > /opt/territory-planner/infrastructure/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/mnt/data/territory-planner/backups"
DATE=$(date +%Y%m%d-%H%M%S)

# Create backup
docker exec territory-planner-backend \
  sqlite3 /app/data/territory_planner.db \
  ".backup '/app/data/backup-${DATE}.db'"

# Copy to backup directory
docker cp territory-planner-backend:/app/data/backup-${DATE}.db \
  ${BACKUP_DIR}/backup-${DATE}.db

# Remove backup from container
docker exec territory-planner-backend rm /app/data/backup-${DATE}.db

# Keep only last 30 days of backups
find ${BACKUP_DIR} -name "backup-*.db" -mtime +30 -delete

echo "Backup complete: backup-${DATE}.db"
EOF

chmod +x /opt/territory-planner/infrastructure/backup.sh
```

### 7.2 Schedule Daily Backups
```bash
# Add to crontab
crontab -e

# Add this line (runs daily at 2 AM)
0 2 * * * /opt/territory-planner/infrastructure/backup.sh >> /var/log/territory-planner-backup.log 2>&1
```

---

## Phase 8: Documentation Updates

### 8.1 Update README.md
Add sections:
- Link to GitHub repository
- Deployment instructions using new structure
- Development workflow
- Contribution guidelines

### 8.2 Create Additional Docs
- `docs/DEPLOYMENT.md` - Detailed deployment guide
- `docs/API.md` - API documentation
- `docs/DEVELOPMENT.md` - Local development setup
- `docs/TROUBLESHOOTING.md` - Common issues and solutions

---

## Validation Checklist

After completing all phases:

### Infrastructure
- [ ] Persistent disk mounted at `/mnt/data`
- [ ] Database stored on persistent disk
- [ ] Automatic mounting configured in `/etc/fstab`
- [ ] Daily backups scheduled

### Git Repository
- [ ] Repository initialized locally
- [ ] Pushed to GitHub
- [ ] `.env` is in `.gitignore` (not committed)
- [ ] `.env.example` exists for reference
- [ ] Clean commit history

### Project Structure
- [ ] Deployment files in `infrastructure/`
- [ ] Documentation in `docs/`
- [ ] No duplicate docker-compose files
- [ ] Clear naming conventions

### Deployment
- [ ] Server can pull from GitHub
- [ ] Deployment script works
- [ ] Containers start successfully
- [ ] Database accessible
- [ ] App responds to health checks
- [ ] Frontend loads correctly

### Operations
- [ ] Backup script runs successfully
- [ ] Cron job scheduled
- [ ] Logs accessible via `docker logs`
- [ ] Clear process for making changes

---

## Rollback Plan

If something goes wrong:

### Database Issues
```bash
# Restore from backup
docker exec territory-planner-backend \
  cp /app/data/backup-YYYYMMDD-HHMMSS.db /app/data/territory_planner.db

# Or from home directory
docker cp ~/backup-YYYYMMDD-HHMMSS.db \
  territory-planner-backend:/app/data/territory_planner.db
```

### Deployment Issues
```bash
# Revert to previous commit
git log  # Find commit hash
git revert <commit-hash>
git push origin main

# Redeploy
./deploy.sh ubuntu@204.52.22.55
```

### Container Issues
```bash
# Stop and remove containers
docker-compose -f infrastructure/docker-compose.prod.yml down

# Rebuild from scratch
docker-compose -f infrastructure/docker-compose.prod.yml up -d --build --force-recreate
```

---

## Next Steps After Cleanup

1. **Performance improvements**
   - Add LLM timeout configuration
   - Implement retry strategy
   - Consider parallel processing

2. **Monitoring**
   - Set up health monitoring
   - Add metrics collection
   - Configure alerts

3. **Security**
   - Add authentication
   - Implement rate limiting
   - Review CORS settings

4. **Features**
   - Export failed companies
   - Bulk operations
   - Custom scoring models

---

## Contact & Support

For issues during migration:
- Check logs: `docker logs territory-planner-backend`
- Review GitHub issues: `https://github.com/YOUR_USERNAME/territory-planner/issues`
- Server access: `ssh -i ~/.ssh/crusoe_key ubuntu@204.52.22.55`
