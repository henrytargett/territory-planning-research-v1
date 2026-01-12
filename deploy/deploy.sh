#!/bin/bash
# Deploy script - run from local machine to deploy to server
# Usage: ./deploy.sh user@server-ip

set -e

if [ -z "$1" ]; then
    echo "Usage: ./deploy.sh user@server-ip"
    echo "Example: ./deploy.sh ubuntu@123.45.67.89"
    exit 1
fi

SERVER=$1
APP_DIR="/opt/territory-planner"

echo "=== Deploying Territory Planner to $SERVER ==="

SSH_KEY="${SSH_KEY:-$HOME/.ssh/crusoe_key}"

# Get the directory containing this script (deploy/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Get the parent directory (project root)
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Sync files to server (excluding unnecessary files)
echo "Syncing files from $PROJECT_ROOT..."
rsync -avz --progress -e "ssh -i $SSH_KEY" \
    --exclude 'node_modules' \
    --exclude 'venv' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.git' \
    --exclude 'data/*.db' \
    --exclude '.env' \
    "$PROJECT_ROOT/" $SERVER:$APP_DIR/

# Copy .env file separately (it might be in .gitignore)
echo "Copying .env file..."
scp -i $SSH_KEY "$PROJECT_ROOT/.env" $SERVER:$APP_DIR/.env

# Build and start containers on server
echo "Building and starting containers..."
ssh -i $SSH_KEY $SERVER "cd $APP_DIR/deploy && docker compose -f docker-compose.prod.yml down 2>/dev/null || true"
ssh -i $SSH_KEY $SERVER "cd $APP_DIR/deploy && docker compose -f docker-compose.prod.yml build"
ssh -i $SSH_KEY $SERVER "cd $APP_DIR/deploy && docker compose -f docker-compose.prod.yml up -d"

# Show status
echo ""
echo "=== Deployment Complete ==="
ssh -i $SSH_KEY $SERVER "docker ps"
echo ""
echo "App should be available at: http://$(echo $SERVER | cut -d@ -f2)"

