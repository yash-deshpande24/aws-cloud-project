#!/bin/bash
# ============================================================
#  EC2 Instance Bootstrap & Setup Script
#  Project: Cloud Hosting & Networking
# ============================================================

set -euo pipefail

PROJECT_NAME="${1:-cloud-hosting-project}"
ENVIRONMENT="${2:-production}"
S3_BUCKET="${3:-}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# ─── System Update ────────────────────────────────────────────────────────
log "Updating system packages..."
sudo yum update -y

# ─── Install Dependencies ─────────────────────────────────────────────────
log "Installing dependencies..."
sudo yum install -y \
  httpd \
  aws-cli \
  jq \
  htop \
  curl \
  wget \
  git \
  python3 \
  python3-pip

# ─── Configure Apache ─────────────────────────────────────────────────────
log "Configuring Apache..."
sudo systemctl start httpd
sudo systemctl enable httpd

# Virtual host config
sudo tee /etc/httpd/conf.d/app.conf > /dev/null <<'EOF'
<VirtualHost *:80>
    ServerName localhost
    DocumentRoot /var/www/html

    <Directory /var/www/html>
        AllowOverride All
        Require all granted
    </Directory>

    # Health check endpoint
    Alias /health /var/www/html/health

    # Logging
    ErrorLog /var/log/httpd/app_error.log
    CustomLog /var/log/httpd/app_access.log combined
</VirtualHost>
EOF

# ─── Deploy Health Check ───────────────────────────────────────────────────
log "Setting up health check endpoint..."
INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
AZ=$(curl -s http://169.254.169.254/latest/meta-data/placement/availability-zone)

sudo tee /var/www/html/health > /dev/null <<EOF
{
  "status": "healthy",
  "project": "${PROJECT_NAME}",
  "environment": "${ENVIRONMENT}",
  "instance_id": "${INSTANCE_ID}",
  "availability_zone": "${AZ}",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

# ─── Pull App from S3 ─────────────────────────────────────────────────────
if [ -n "$S3_BUCKET" ]; then
  log "Syncing application from S3 bucket: $S3_BUCKET"
  aws s3 sync "s3://${S3_BUCKET}/app/" /var/www/html/ --delete
fi

# ─── Restart Services ─────────────────────────────────────────────────────
log "Restarting Apache..."
sudo systemctl restart httpd

log "EC2 setup complete."
