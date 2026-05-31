#!/bin/bash
# ── Initial EC2 setup — run ONCE after launching a fresh Amazon Linux 2023 instance ──
# Usage: bash setup_server.sh
# Requires: sudo privileges (run as ec2-user)

set -euo pipefail
APP_DIR="/opt/csalgotrader"
REPO="https://github.com/chiragsindhwani/CSAlgoTraderApp.git"

echo "=== [1/7] System update & packages ==="
sudo dnf update -y
sudo dnf install -y git nginx python3.11 python3.11-pip python3-pip

echo "=== [2/7] Clone repository ==="
sudo mkdir -p "$APP_DIR"
sudo chown ec2-user:ec2-user "$APP_DIR"
git clone "$REPO" "$APP_DIR"
cd "$APP_DIR"
mkdir -p logs trades   # logs/ = session logs; trades/ = SQLite trade database

echo "=== [3/7] Python dependencies ==="
python3.11 -m pip install --upgrade pip --quiet
python3.11 -m pip install -r requirements.txt --quiet
echo "Dependencies installed."

echo "=== [4/7] Create .env (you MUST fill in real values) ==="
cat > "$APP_DIR/.env" << 'ENVEOF'
TRADIER_API_TOKEN=REPLACE_WITH_YOUR_TOKEN
TRADIER_ACCOUNT_ID=REPLACE_WITH_YOUR_ACCOUNT_ID
TRADIER_PAPER_TRADE=false
TELEGRAM_BOT_TOKEN=REPLACE_WITH_YOUR_BOT_TOKEN
TELEGRAM_CHAT_ID=REPLACE_WITH_YOUR_CHAT_ID

# ── Trade Logger (auto-detected: local=CSV, AWS=SQLite) ──────────────────────
# Leave DEPLOYMENT_ENV unset for auto-detect (EC2 metadata check).
# Override: DEPLOYMENT_ENV=aws  or  DEPLOYMENT_ENV=local
# DEPLOYMENT_ENV=aws

# ── Optional: PostgreSQL / RDS instead of SQLite (AWS only) ─────────────────
# Uncomment and set DATABASE_URL to use a PostgreSQL database.
# Also run:  pip install psycopg2-binary
# DATABASE_URL=postgresql://user:password@your-rds-endpoint:5432/trades
ENVEOF
chmod 600 "$APP_DIR/.env"
echo ">>> EDIT $APP_DIR/.env now with real credentials <<<"

echo "=== [5/7] Cron jobs (America/Chicago timezone) ==="
sudo timedatectl set-timezone America/Chicago
# Trading bot: Mon-Fri at 9:05 AM CST/CDT
# Data refresh: every 5 min during market hours (8:30 AM - 4:15 PM) Mon-Fri
(crontab -l 2>/dev/null; cat << 'CRONEOF'

# SPY Iron Condor — trading bot (9:05 AM CST/CDT, Mon-Fri)
5 9 * * 1-5 cd /opt/csalgotrader && /usr/bin/python3.11 -m iron_condor_0dte.live_trader >> /opt/csalgotrader/logs/session_$(date +\%Y\%m\%d).log 2>&1

# Dashboard data refresh (every 5 min, 8:30 AM - 4:15 PM, Mon-Fri)
*/5 8-16 * * 1-5 cd /opt/csalgotrader && /usr/bin/python3.11 generate_tradier_data.py >> /opt/csalgotrader/logs/data_refresh.log 2>&1
CRONEOF
) | crontab -
echo "Cron jobs installed."

echo "=== [6/7] Nginx — serve dashboard ==="
sudo tee /etc/nginx/conf.d/csalgotrader.conf > /dev/null << 'NGINXEOF'
server {
    listen 80;
    server_name _;
    root /opt/csalgotrader/CS_ALGOTRADER_APP;
    index tradier_dashboard.html index.html;

    # Never cache the generated JS data file
    location ~* tradier_account_data\.js$ {
        add_header Cache-Control "no-store, no-cache, must-revalidate";
        add_header Pragma "no-cache";
        expires -1;
    }

    location / {
        try_files $uri $uri/ =404;
    }

    access_log /var/log/nginx/csalgotrader_access.log;
    error_log  /var/log/nginx/csalgotrader_error.log;
}
NGINXEOF

sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx
echo "Nginx running."

echo "=== [7/7] SSH deploy key (for GitHub Actions) ==="
echo "Paste this public key into GitHub → Settings → Deploy keys (read-only):"
cat ~/.ssh/authorized_keys 2>/dev/null | tail -1 || echo "(no authorized_keys yet — add your CI public key)"

echo ""
echo "======================================================"
echo " Setup complete!  Next steps:"
echo "  1. Edit $APP_DIR/.env with real credentials"
echo "  2. Add GitHub Secrets: EC2_HOST, EC2_SSH_KEY"
echo "  3. Push to main — GitHub Actions will auto-deploy"
echo "  4. Dashboard: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)"
echo "======================================================"
