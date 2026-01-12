# Deployment Guide - Territory Planner

## Server Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 1 core | 2 cores |
| RAM | 2 GB | 4 GB |
| Storage | 10 GB | 20 GB |
| OS | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |

## Quick Start

### 1. Provision a VM on Crusoe Cloud

Create a VM with:
- 2 vCPU, 4GB RAM
- 20GB block storage
- Ubuntu 22.04 LTS
- Open port 80 (HTTP) in firewall

### 2. SSH into the server and run setup

```bash
ssh ubuntu@YOUR_SERVER_IP

# Download and run setup script (or copy it manually)
curl -O https://raw.githubusercontent.com/YOUR_REPO/deploy/setup-server.sh
chmod +x setup-server.sh
./setup-server.sh

# Log out and back in for docker group
exit
ssh ubuntu@YOUR_SERVER_IP
```

### 3. Deploy from your local machine

```bash
cd deploy
./deploy.sh ubuntu@YOUR_SERVER_IP
```

This will:
- Sync all app files to the server
- Copy your `.env` file with API keys
- Build Docker containers
- Start the app

### 4. Access the app

Open `http://YOUR_SERVER_IP` in your browser.

---

## Manual Deployment (Alternative)

If you prefer to deploy manually:

```bash
# On server
cd /opt/territory-planner

# Create .env file
cat > .env << 'EOF'
CRUSOE_API_KEY=your_key_here
CRUSOE_API_BASE_URL=https://api.crusoe.ai/v1/
CRUSOE_MODEL=meta-llama/Llama-3.3-70B-Instruct
TAVILY_API_KEY=your_tavily_key_here
DATABASE_URL=sqlite:///./data/territory_planner.db
APP_ENV=production
LOG_LEVEL=INFO
EOF

# Build and start
cd deploy
docker compose -f docker-compose.prod.yml up -d --build

# Check status
docker ps
docker logs territory-planner-backend
```

---

## Managing the App

### View logs
```bash
docker logs -f territory-planner-backend
docker logs -f territory-planner-frontend
```

### Restart
```bash
cd /opt/territory-planner/deploy
docker compose -f docker-compose.prod.yml restart
```

### Stop
```bash
docker compose -f docker-compose.prod.yml down
```

### Update
```bash
# From local machine
./deploy.sh ubuntu@YOUR_SERVER_IP
```

### Backup database
```bash
# On server
docker cp territory-planner-backend:/app/data/territory_planner.db ./backup_$(date +%Y%m%d).db
```

---

## Background Jobs

Jobs run **inside the Docker container** on the server. They will continue running even when:
- Your local machine is offline
- You close your browser
- You disconnect from SSH

The only way to stop a job is:
1. Use the Cancel button in the UI
2. Restart the backend container

---

## Troubleshooting

### App not loading
```bash
# Check containers are running
docker ps

# Check logs
docker logs territory-planner-backend
docker logs territory-planner-frontend
```

### Database errors
```bash
# Reset database (WARNING: deletes all data)
docker exec territory-planner-backend rm -f /app/data/territory_planner.db
docker compose -f docker-compose.prod.yml restart backend
```

### API errors
```bash
# Check .env file is correct
cat /opt/territory-planner/.env

# Test Crusoe API
curl https://api.crusoe.ai/v1/models -H "Authorization: Bearer YOUR_KEY"
```



