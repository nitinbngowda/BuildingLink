#!/usr/bin/env bash
# ==============================================================================
# CronMaster — Automated Oracle Cloud Ubuntu Deployment Script
# ==============================================================================
set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "\n${BLUE}======================================================${NC}"
echo -e "${GREEN}  CronMaster Web Scheduler — Oracle Ubuntu Installer   ${NC}"
echo -e "${BLUE}======================================================${NC}\n"

# 1. Require sudo
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}[ERROR] Please run with sudo: sudo bash deploy_oracle.sh${NC}"
  exit 1
fi

CURRENT_USER=${SUDO_USER:-$(whoami)}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT=5000

echo -e "${BLUE}[1/5] Updating packages & checking dependencies...${NC}"
apt-get update -y > /dev/null 2>&1 || true
apt-get install -y python3 curl iptables-persistent netfilter-persistent > /dev/null 2>&1 || true

echo -e "${BLUE}[2/5] Setting up permissions for user '${CURRENT_USER}'...${NC}"
chown -R "${CURRENT_USER}:${CURRENT_USER}" "${SCRIPT_DIR}"
chmod +x "${SCRIPT_DIR}/buildinglink_bot.py"
chmod +x "${SCRIPT_DIR}/web_scheduler/app.py"

echo -e "${BLUE}[3/5] Configuring systemd background service (24/7 auto-start)...${NC}"
SERVICE_FILE="/etc/systemd/system/cronmaster.service"

cat > "${SERVICE_FILE}" <<EOF
[Unit]
Description=CronMaster Web Scheduler & Automation Engine
After=network.target

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${SCRIPT_DIR}
ExecStart=/usr/bin/python3 ${SCRIPT_DIR}/web_scheduler/app.py
Restart=always
RestartSec=5
Environment=PORT=${PORT}
Environment=HOST=0.0.0.0
Environment=PYTHONUNBUFFERED=1

LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable cronmaster.service
systemctl restart cronmaster.service

echo -e "${BLUE}[4/5] Opening firewall port ${PORT} on Ubuntu (iptables & ufw)...${NC}"
# Oracle Cloud Ubuntu images include strict default iptables rules
iptables -I INPUT 6 -p tcp --dport ${PORT} -m state --state NEW -j ACCEPT 2>/dev/null || iptables -A INPUT -p tcp --dport ${PORT} -j ACCEPT
netfilter-persistent save > /dev/null 2>&1 || true

if command -v ufw >/dev/null 2>&1; then
  ufw allow ${PORT}/tcp > /dev/null 2>&1 || true
fi

echo -e "${BLUE}[5/5] Verifying service status...${NC}"
sleep 2

if systemctl is-active --quiet cronmaster.service; then
  PUBLIC_IP=$(curl -s https://ifconfig.me || curl -s https://api.ipify.org || echo "<YOUR_ORACLE_PUBLIC_IP>")
  
  echo -e "\n${GREEN}======================================================${NC}"
  echo -e "${GREEN}  ✓ CronMaster is Successfully Installed & Running!    ${NC}"
  echo -e "${GREEN}======================================================${NC}"
  echo -e "\nAccess your Web Dashboard at:"
  echo -e "👉  ${YELLOW}http://${PUBLIC_IP}:${PORT}${NC}\n"
  echo -e "Dashboard Features:"
  echo -e "  • BuildingLink Badminton Scheduler: Pre-configured for 12:00 AM"
  echo -e "  • On/Off Switches: Toggle any scheduled job with 1 click"
  echo -e "  • History & Logs: Real-time execution logs & run audit trail"
  echo -e "  • Add Future Jobs: Manage all your cron tasks from one place"
  echo -e "\nManage service with:"
  echo -e "  sudo systemctl status cronmaster"
  echo -e "  sudo systemctl restart cronmaster"
  echo -e "  sudo journalctl -u cronmaster -f\n"
  echo -e "${YELLOW}IMPORTANT: Ensure you added an Ingress Rule for Port ${PORT} in your OCI Console Security List!${NC}\n"
else
  echo -e "${RED}[ERROR] Service failed to start. View logs with: journalctl -u cronmaster -xe${NC}"
fi

