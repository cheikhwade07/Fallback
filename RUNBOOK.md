# Fallback deployment runbook

Assumptions: Ubuntu 24.04 droplet, root SSH access, and the repository URL available for cloning. Replace `<REPO_URL>` and `<DROPLET_IP>` below.

1. SSH into the droplet:

   ```bash
   ssh root@<DROPLET_IP>
   ```

2. Install the system packages:

   ```bash
   apt update && apt upgrade -y
   apt install -y git python3 python3-venv python3-pip nodejs npm nginx ufw
   ```

3. Create the service user and clone the repo:

   ```bash
   useradd --system --create-home --shell /usr/sbin/nologin fallback
   git clone <REPO_URL> /opt/fallback
   chown -R fallback:fallback /opt/fallback
   ```

4. Create the backend virtual environment and install Python dependencies:

   ```bash
   python3 -m venv /opt/fallback/.venv
   /opt/fallback/.venv/bin/pip install --upgrade pip
   /opt/fallback/.venv/bin/pip install -r /opt/fallback/backend/requirements.txt
   ```

5. Install frontend dependencies and build with the public API base. An empty base uses nginx's same-origin `/api/` path and avoids CORS for the dashboard:

   ```bash
   cd /opt/fallback/frontend
   npm ci
   NEXT_PUBLIC_API_BASE= npm run build
   ```

6. Install both systemd units:

   ```bash
   install -m 0644 /opt/fallback/deploy/systemd/fallback-backend.service /etc/systemd/system/fallback-backend.service
   install -m 0644 /opt/fallback/deploy/systemd/fallback-frontend.service /etc/systemd/system/fallback-frontend.service
   systemctl daemon-reload
   systemctl enable --now fallback-backend.service fallback-frontend.service
   systemctl status --no-pager fallback-backend.service fallback-frontend.service
   ```

7. Enable nginx with the complete site config:

   ```bash
   install -m 0644 /opt/fallback/deploy/nginx/fallback.conf /etc/nginx/sites-available/fallback
   ln -s /etc/nginx/sites-available/fallback /etc/nginx/sites-enabled/fallback
   rm -f /etc/nginx/sites-enabled/default
   nginx -t
   systemctl enable nginx
   systemctl reload nginx
   ```

8. Open SSH and HTTP in UFW, then enable it:

   ```bash
   ufw allow 22
   ufw allow 80
   ufw --force enable
   ufw status
   ```

9. Check the deployed endpoints:

   ```bash
   curl http://<DROPLET_IP>/api/health
   curl -N http://<DROPLET_IP>/api/stream
   ```

10. In a second SSH session, inspect logs if needed:

   ```bash
   journalctl -u fallback-backend.service -f
   journalctl -u fallback-frontend.service -f
   ```
