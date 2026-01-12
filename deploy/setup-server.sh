#!/bin/bash
# Server setup script for Ubuntu 22.04
# Run this on a fresh Crusoe Cloud VM

set -e

echo "=== Territory Planner Server Setup ==="

# Update system
echo "Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# Install Docker
echo "Installing Docker..."
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add current user to docker group
sudo usermod -aG docker $USER

# Install useful tools
echo "Installing utilities..."
sudo apt-get install -y git htop vim

# Create app directory
echo "Creating app directory..."
sudo mkdir -p /opt/territory-planner
sudo chown $USER:$USER /opt/territory-planner

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Log out and back in (for docker group)"
echo "2. Clone or copy your app to /opt/territory-planner"
echo "3. Create .env file with your API keys"
echo "4. Run: cd /opt/territory-planner/deploy && docker compose -f docker-compose.prod.yml up -d"
echo ""



