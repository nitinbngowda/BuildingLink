# CronMaster & BuildingLink on Oracle Cloud (Ubuntu)

This guide walks you through deploying **CronMaster** and the **BuildingLink Auto-Booker** onto your free **Oracle Cloud Infrastructure (OCI) Ubuntu VM**.

---

## 🌟 What You Get

- **Full-featured Web Dashboard**: Accessible from any browser (desktop or phone).
- **On / Off Switches**: Enable or disable any cron job instantly with a single toggle.
- **Run Now**: Manually trigger any job on-demand with live output feedback.
- **Execution History**: Full audit trail of all automated and manual runs (status, duration, timestamp).
- **Integrated Log Viewer**: Monospace terminal to inspect complete stdout/stderr logs and copy them.
- **BuildingLink Badminton Court Auto-Booker**: Pre-configured out of the box to run at 12:00 AM midnight.
- **BuildingLink Preferences Editor**: Change your preferred booking time slots directly from the Web UI.
- **Multi-Job Support**: Easily add and manage future cron jobs and scripts from the same dashboard.

---

## 🚀 Quick Setup (Under 5 Minutes)

### Step 1: Open Port 5000 in Oracle Cloud Console (Crucial)

Oracle Cloud instances block all incoming ports by default in their cloud virtual firewall (Security Lists).

1. Log into your **[Oracle Cloud Console](https://cloud.oracle.com)**.
2. In the top-left menu, navigate to **Networking** → **Virtual Cloud Networks (VCN)**.
3. Click on your VCN (usually `vcn-...`).
4. Under **Resources** on the left, click **Security Lists**, then click **Default Security List for vcn-...**.
5. Click **Add Ingress Rules**:
   - **Source Type**: `CIDR`
   - **Source CIDR**: `0.0.0.0/0`
   - **IP Protocol**: `TCP`
   - **Destination Port Range**: `5000`
   - **Description**: `CronMaster Web Dashboard`
6. Click **Add Ingress Rules**.

---

### Step 2: Set Server Timezone to Building Local Time

BuildingLink opens bookings at **12:00 AM midnight in the building's local timezone** (Toronto / Eastern Time):

SSH into your Oracle VM:
```bash
ssh -i /path/to/your-key.key ubuntu@<YOUR_ORACLE_PUBLIC_IP>
```

Set timezone to Eastern Time:
```bash
sudo timedatectl set-timezone America/Toronto
```
Verify with `timedatectl`. The time should now match your building's local time.

---

### Step 3: Transfer Files to Your Oracle VM

From your local machine (PowerShell or Terminal), run:

```powershell
scp -i /path/to/your-key.key -r C:\Development\BuildingLink ubuntu@<YOUR_ORACLE_PUBLIC_IP>:/home/ubuntu/
```

*(Alternatively, you can push to a private Git repository and `git clone` it on the server).*

---

### Step 4: Run the 1-Line Deployment Script

SSH into your Oracle VM:
```bash
cd /home/ubuntu/BuildingLink
sudo bash deploy_oracle.sh
```

The script automatically:
1. Installs Python 3 and system dependencies.
2. Configures the systemd background service (`cronmaster.service`) for **24/7 auto-start across server reboots**.
3. Configures Ubuntu's internal firewall (`iptables` and `ufw`) to allow traffic on port 5000.
4. Starts the service and displays your public dashboard URL.

---

### Step 5: Open Your Web Dashboard

In your browser, visit:
```
http://<YOUR_ORACLE_PUBLIC_IP>:5000
```

You will see:
- **Active Schedulers**: Pre-loaded with the BuildingLink Badminton Auto-Booker.
- **On/Off Toggle**: Switch it on to automatically book at 12:00 AM every night.
- **"Run Now" Button**: Click to test the booking or run a dry-run immediately.
- **"Logs" Button**: Click to see the live console log.
- **BuildingLink Settings Tab**: Customize your preferred booking times (`19:00`, `20:00`, etc.) or update credentials anytime.
- **"+ New Job" Button**: Add future scripts, backups, web scrapers, or cron jobs.

---

## 🛠️ Adding Future Jobs in the Web UI

To add future cron jobs:
1. Click **+ New Job** in the top navigation.
2. Fill in:
   - **Job Name**: e.g. `Weekly Database Backup`
   - **Command**: Any shell command or script, e.g.:
     - `python3 /home/ubuntu/my_script.py`
     - `/usr/bin/bash /home/ubuntu/scripts/backup.sh`
     - `curl -s https://api.mywebsite.com/ping`
   - **Schedule**: Pick a preset (Daily at Midnight, Hourly, Every 15 min) or enter a custom cron expression (e.g. `0 9 * * 1-5`).
   - **Enable / Disable**: Choose whether it starts active.
3. Click **Save Job**.

---

## 🔒 Optional: Adding Password Protection (Basic Auth)

Because your Oracle VM has a public IP address, you can protect the dashboard with Basic Auth or Caddy / Nginx reverse proxy with free SSL.

### Quick Reverse Proxy with Caddy (Free HTTPS + Password in 3 lines):
```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy
```

Edit `/etc/caddy/Caddyfile`:
```caddy
yourdomain.com {
    basicauth {
        admin $2a$14$Zkx19XLiW6... # generated with `caddy hash-password`
    }
    reverse_proxy localhost:5000
}
```
Run `sudo systemctl restart caddy`. You now have automatic free HTTPS with password protection!

---

## 📋 Useful Service Commands on Ubuntu

- **Check Service Status**:
  ```bash
  sudo systemctl status cronmaster
  ```
- **Restart Dashboard & Scheduler**:
  ```bash
  sudo systemctl restart cronmaster
  ```
- **View Live Server Logs**:
  ```bash
  sudo journalctl -u cronmaster -f
  ```
- **Stop Service**:
  ```bash
  sudo systemctl stop cronmaster
  ```

