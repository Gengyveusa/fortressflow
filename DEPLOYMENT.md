# FortressFlow — Production Deployment Guide

This guide walks through a complete production deployment of FortressFlow on a single-server Ubuntu 22.04 instance. For multi-node or Kubernetes deployments, contact the Gengyve USA engineering team.

---

## 1. Server Requirements

### Minimum Specification

| Resource | Minimum          | Recommended        |
|----------|------------------|--------------------|
| CPU      | 4 vCPU           | 8 vCPU             |
| RAM      | 16 GB            | 32 GB              |
| Disk     | 100 GB SSD       | 200 GB NVMe SSD    |
| Network  | 1 Gbps           | 1 Gbps             |
| OS       | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS   |

> **AWS equivalent**: `c6i.2xlarge` (8 vCPU / 16 GB) or `c6i.4xlarge` for higher throughput.

### Open Ports (Firewall / Security Group)

| Port | Protocol | Purpose                          |
|------|----------|----------------------------------|
| 22   | TCP      | SSH (restrict to your IP range)  |
| 80   | TCP      | HTTP (redirect to HTTPS)         |
| 443  | TCP      | HTTPS                            |

All other ports should be closed to the public. Internal service communication occurs over the Docker bridge network.

---

## 2. Domain Setup

### DNS Records

Add the following DNS records in your registrar or Route 53 / Cloudflare:

```
# A records — replace 1.2.3.4 with your server IP
@                A    1.2.3.4
www              A    1.2.3.4
api              A    1.2.3.4
grafana          A    1.2.3.4

# Sending subdomain — required for email deliverability
mail             A    1.2.3.4    # or a dedicated IP pool address
```

Allow up to 24–48 hours for DNS propagation.

### Sending Subdomain

A dedicated sending subdomain (e.g., `mail.yourcompany.com`) isolates your transactional sending reputation from the root domain. All outbound email **must** originate from this subdomain.

---

## 3. SSL Certificate (Let's Encrypt / Certbot)

```bash
# Install Certbot
sudo apt update
sudo apt install -y certbot python3-certbot-nginx

# Issue certificates for all subdomains
sudo certbot --nginx \
  -d yourcompany.com \
  -d www.yourcompany.com \
  -d api.yourcompany.com \
  -d grafana.yourcompany.com \
  --email thad@gengyveusa.com \
  --agree-tos \
  --no-eff-email

# Verify auto-renewal
sudo certbot renew --dry-run

# Confirm renewal timer is active
sudo systemctl status certbot.timer
```

Certbot auto-configures Nginx for HTTPS redirection and sets up a systemd timer for 90-day certificate renewal.

---

## 4. SPF / DKIM / DMARC / BIMI Records

All four DNS records are required before starting the IP warmup. Configure them in the DNS zone for your **sending subdomain** (`mail.yourcompany.com`).

### SPF

```
mail.yourcompany.com.  TXT  "v=spf1 include:amazonses.com ~all"
```

> If you send from multiple providers, chain them: `include:amazonses.com include:sendgrid.net`.

### DKIM

AWS SES generates the DKIM keys automatically. After verifying your domain in the SES console, it provides three CNAME records. Add them verbatim:

```
<selector1>._domainkey.mail.yourcompany.com.  CNAME  <selector1>.dkim.amazonses.com.
<selector2>._domainkey.mail.yourcompany.com.  CNAME  <selector2>.dkim.amazonses.com.
<selector3>._domainkey.mail.yourcompany.com.  CNAME  <selector3>.dkim.amazonses.com.
```

### DMARC

Start with a monitoring-only policy (`p=none`) and move to `p=quarantine` then `p=reject` as you confirm legitimate mail is aligned:

```
_dmarc.mail.yourcompany.com.  TXT  "v=DMARC1; p=none; rua=mailto:dmarc-reports@yourcompany.com; ruf=mailto:dmarc-forensics@yourcompany.com; fo=1; adkim=s; aspf=s"
```

Recommended progression:
1. Week 1–2: `p=none` (monitoring)
2. Week 3–4: `p=quarantine; pct=10`
3. Week 5+:  `p=reject`

### BIMI (Optional but Recommended)

BIMI displays your brand logo in supporting inboxes (Gmail, Yahoo, Apple Mail). Requires DMARC `p=quarantine` or `p=reject`.

```
default._bimi.mail.yourcompany.com.  TXT  "v=BIMI1; l=https://yourcompany.com/assets/bimi-logo.svg; a=https://yourcompany.com/assets/vmc.pem"
```

The SVG must comply with the [BIMI SVG profile](https://bimigroup.org/svg-profile/). A Verified Mark Certificate (VMC) from DigiCert or Entrust is required for Google-verified BIMI.

---

## 5. Docker Installation

```bash
# Remove old Docker packages
for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do
  sudo apt remove -y $pkg
done

# Install using the official Docker repository
sudo apt update
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Allow the current user to run Docker without sudo
sudo usermod -aG docker $USER
newgrp docker

# Verify installation
docker --version
docker compose version
```

---

## 6. Clone and Configure

```bash
# Clone the repository
git clone https://github.com/gengyveusa/fortressflow.git /opt/fortressflow
cd /opt/fortressflow

# Copy and edit the production environment file
cp .env.example .env.production

# Generate secure random secrets
echo "SECRET_KEY=$(openssl rand -hex 32)"
echo "UNSUBSCRIBE_HMAC_KEY=$(openssl rand -hex 32)"
echo "POSTGRES_PASSWORD=$(openssl rand -hex 24)"
echo "REDIS_PASSWORD=$(openssl rand -hex 24)"
```

Edit `/opt/fortressflow/.env.production` and fill in all required values:

```bash
# Application
ENVIRONMENT=production
SECRET_KEY=<64-char hex from above>
UNSUBSCRIBE_HMAC_KEY=<64-char hex from above>

# Database
POSTGRES_PASSWORD=<from above>
DATABASE_URL=postgresql+asyncpg://fortressflow:<POSTGRES_PASSWORD>@postgres/fortressflow

# Redis
REDIS_PASSWORD=<from above>
REDIS_URL=redis://:REDIS_PASSWORD@redis:6379/0

# AWS SES
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
SES_FROM_EMAIL=outreach@mail.yourcompany.com
SES_CONFIGURATION_SET=fortressflow-tracking
SENDING_SUBDOMAIN=mail.yourcompany.com

# Twilio (optional — for SMS)
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1...

# Sentry (recommended)
SENTRY_DSN=https://...@o0.ingest.sentry.io/...

# AI integrations (optional)
HUBSPOT_API_KEY=...
ZOOMINFO_CLIENT_ID=...
APOLLO_API_KEY=...
```

---

## 7. Build and Deploy

```bash
# Build images and start all services
docker compose -f docker-compose.prod.yml up -d --build

# Verify all containers are healthy
docker compose -f docker-compose.prod.yml ps

# Tail the backend logs
docker compose -f docker-compose.prod.yml logs -f backend

# Check the health endpoint
curl https://api.yourcompany.com/health
```

Expected health response:
```json
{"status": "ok", "version": "0.6.0", "environment": "production"}
```

---

## 8. Database Migration

```bash
# Apply all pending Alembic migrations
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head

# Verify the current revision
docker compose -f docker-compose.prod.yml exec backend alembic current

# (Optional) View migration history
docker compose -f docker-compose.prod.yml exec backend alembic history --verbose
```

> **Always take a database snapshot before running migrations in production.**

```bash
# Create a pre-migration backup
docker compose -f docker-compose.prod.yml exec postgres \
  pg_dump -U fortressflow fortressflow > backup_$(date +%Y%m%d_%H%M%S).sql
```

---

## 9. Initial Setup

### Create the Admin User

```bash
docker compose -f docker-compose.prod.yml exec backend \
  python -m scripts.create_admin \
    --email thad@gengyveusa.com \
    --name "Thad" \
    --password "<STRONG_PASSWORD>"
```

### Configure SES

1. Verify your sending domain in the [AWS SES console](https://console.aws.amazon.com/ses/).
2. Add DKIM CNAME records (see step 4).
3. Create the `fortressflow-tracking` Configuration Set with the following event destinations:
   - **SNS topic** for bounces and complaints → configure the FortressFlow `/api/v1/webhooks/ses` endpoint as the subscriber.
   - **Kinesis Firehose** for open/click events (optional for volume analytics).
4. Request production access (exit sandbox) if you have not already.

### Configure Twilio

1. Purchase a phone number in the Twilio console.
2. Set the incoming message webhook to: `https://api.yourcompany.com/api/v1/webhooks/twilio/sms`
3. Set the status callback URL to: `https://api.yourcompany.com/api/v1/webhooks/twilio/status`

### API Key Configuration

Store API keys as environment variables in `.env.production`. Never hardcode secrets in the codebase. Rotate keys at least once per year or immediately after any suspected exposure.

---

## 10. Monitoring Verification

```bash
# Prometheus — verify all targets are UP
curl http://localhost:9090/api/v1/targets | python3 -m json.tool | grep '"health"'
# Expected: all instances show "health": "up"

# Grafana — access the dashboard
open https://grafana.yourcompany.com
# Log in with admin / <GRAFANA_ADMIN_PASSWORD>
# Navigate to Dashboards → FortressFlow — Production Dashboard
# Confirm all panels are loading data

# Alertmanager — verify it is reachable
curl http://localhost:9093/-/healthy
```

---

## 11. Warmup Initiation

**Do not** begin full-volume sending before completing at least 4–6 weeks of IP warmup.

### Start Warmup

```bash
# Verify the warmup scheduler is running
docker compose -f docker-compose.prod.yml exec backend \
  python -m scripts.check_warmup_status

# Kick off the warmup for all configured sending identities
docker compose -f docker-compose.prod.yml exec backend \
  python -m scripts.start_warmup --identities all
```

### Warmup Schedule (per identity)

| Week | Daily Volume |
|------|-------------|
| 1    | 5–25        |
| 2    | 25–50       |
| 3    | 50–100      |
| 4    | 100–200     |
| 5    | 200–300     |
| 6    | 300–400     |

Monitor the **Bounce Rate** and **Spam Complaint Rate** panels in Grafana daily. If bounce rate exceeds 3 % or spam complaint rate exceeds 0.05 %, pause the warmup and investigate before continuing.

---

## 12. Troubleshooting Guide

### Backend container fails to start

```bash
# Check logs for startup errors
docker compose -f docker-compose.prod.yml logs --tail=100 backend

# Common causes:
# - DATABASE_URL is wrong or Postgres is not ready → check postgres container
# - Missing required env var → review .env.production
# - Port 8000 is already in use → stop conflicting process
```

### Database connection refused

```bash
# Check if Postgres is healthy
docker compose -f docker-compose.prod.yml exec postgres pg_isready

# Verify the connection string
docker compose -f docker-compose.prod.yml exec backend \
  python -c "from app.config import settings; print(settings.DATABASE_URL)"
```

### Redis rate limiter falling back to in-process

```bash
# Check Redis connectivity
docker compose -f docker-compose.prod.yml exec backend \
  python -c "import redis; r=redis.from_url('$REDIS_URL'); print(r.ping())"

# Check Redis logs
docker compose -f docker-compose.prod.yml logs redis
```

### Emails not being delivered

1. Verify the SES configuration set is active and receiving events.
2. Check the SES console for bounce/complaint metrics and suppression list entries.
3. Run `dig txt mail.yourcompany.com` and confirm SPF record is present.
4. Run `dig cname selector1._domainkey.mail.yourcompany.com` to verify DKIM CNAMEs.
5. Check the Grafana **Bounce Rate** and **Spam Complaint Rate** gauges.
6. Review Celery worker logs: `docker compose -f docker-compose.prod.yml logs celery-worker`.

### Grafana shows no data

```bash
# Check Prometheus is scraping the backend
curl http://localhost:9090/api/v1/query?query=up

# Verify the backend /metrics endpoint
curl http://localhost:8000/metrics | head -20
```

### Container out of memory (OOMKill)

Increase the server RAM or add Docker memory limits tuned to your workload. As a first step:

```bash
# Check memory usage
docker stats --no-stream

# Identify the largest consumer and restart it
docker compose -f docker-compose.prod.yml restart <service-name>
```

### SSL certificate not auto-renewing

```bash
# Check Certbot timer
sudo systemctl status certbot.timer

# Force a manual renewal test
sudo certbot renew --dry-run

# Reload Nginx after renewal
sudo systemctl reload nginx
```

---

## Maintenance

### Updating FortressFlow

```bash
cd /opt/fortressflow
git pull origin main
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
docker compose -f docker-compose.prod.yml up -d
```

### Database Backup Schedule

Configure a daily cron job for automated backups:

```bash
# /etc/cron.d/fortressflow-backup
0 2 * * * root docker compose -f /opt/fortressflow/docker-compose.prod.yml exec -T postgres \
  pg_dump -U fortressflow fortressflow | gzip > /backups/fortressflow_$(date +\%Y\%m\%d).sql.gz
```

Retain at minimum 30 days of daily backups and 12 months of monthly backups.

### Log Rotation

Docker handles log rotation via the `json-file` driver. Configure limits in `/etc/docker/daemon.json`:

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "5"
  }
}
```

Restart the Docker daemon after changing this file: `sudo systemctl restart docker`.
