#!/bin/bash
set -euo pipefail

# ============================================================================
# CFTC Comment Analyzer — Server Setup Script
# Run this on a fresh Ubuntu 24.04 DigitalOcean droplet ($12/mo, 2GB RAM)
# ============================================================================

echo "=== CFTC Comment Analyzer — Server Setup ==="

# 1. Update system
echo "[1/6] Updating system..."
apt-get update && apt-get upgrade -y

# 2. Install Docker
echo "[2/6] Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

# 3. Install Docker Compose plugin
echo "[3/6] Installing Docker Compose..."
if ! docker compose version &> /dev/null; then
    apt-get install -y docker-compose-plugin
fi

# 4. Create app directory
echo "[4/6] Setting up application..."
APP_DIR=/opt/cftc-analyzer
mkdir -p $APP_DIR
cd $APP_DIR

# 5. Check for required files
echo "[5/6] Checking files..."
REQUIRED_FILES=("docker-compose.yml" "Caddyfile" ".env" "cftc-comment-system" "cftc-frontend")
for f in "${REQUIRED_FILES[@]}"; do
    if [ ! -e "$APP_DIR/$f" ]; then
        echo "ERROR: Missing $f in $APP_DIR"
        echo ""
        echo "Upload your files first:"
        echo "  scp -r deploy/* root@YOUR_SERVER_IP:/opt/cftc-analyzer/"
        echo "  scp -r cftc-comment-system root@YOUR_SERVER_IP:/opt/cftc-analyzer/"
        echo "  scp -r cftc-frontend root@YOUR_SERVER_IP:/opt/cftc-analyzer/"
        echo ""
        echo "Then copy and edit .env:"
        echo "  cp .env.example .env"
        echo "  nano .env"
        echo ""
        echo "Then re-run this script."
        exit 1
    fi
done

# Verify .env has real values
if grep -q "CHANGE_ME" .env; then
    echo "ERROR: .env still has placeholder values. Edit it first:"
    echo "  nano $APP_DIR/.env"
    exit 1
fi

# 6. Build and start
echo "[6/6] Building and starting services..."
docker compose build
docker compose up -d

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Services starting up. Check status with:"
echo "  cd $APP_DIR && docker compose ps"
echo "  docker compose logs -f"
echo ""
echo "Your app will be available at:"
source .env
echo "  https://$DOMAIN"
echo ""
echo "Caddy will automatically provision HTTPS via Let's Encrypt."
echo "Make sure your DNS A record points $DOMAIN to this server's IP."
