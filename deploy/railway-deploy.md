# FortressFlow — Railway Deployment Guide

Deploy FortressFlow to [Railway](https://railway.app) using managed PostgreSQL and Redis plugins with Docker-based services.

---

## Architecture on Railway

| Railway Service   | Source              | Build     | Notes                              |
|-------------------|---------------------|-----------|------------------------------------|
| **frontend**      | `frontend/`         | Dockerfile | Next.js 15 standalone              |
| **backend**       | `backend/`          | Dockerfile | FastAPI + Alembic migrations       |
| **worker**        | `backend/` (reused) | Dockerfile | Celery worker for async tasks      |
| **PostgreSQL**    | Railway plugin      | —         | Managed, auto-provisioned          |
| **Redis**         | Railway plugin      | —         | Managed, auto-provisioned          |

> **RabbitMQ**: Railway does not offer a native RabbitMQ plugin. Options:
> 1. Use Redis as the Celery broker (`redis://` instead of `amqp://`) — simplest
> 2. Deploy a RabbitMQ Docker service on Railway
> 3. Use CloudAMQP or another managed RabbitMQ provider

---

## Prerequisites

```bash
# Install Railway CLI
npm install -g @railway/cli

# Authenticate
railway login
```

---

## Step 1: Create Project

```bash
railway init
# Choose "Empty project" and name it "fortressflow"
```

---

## Step 2: Add Managed Plugins

In the Railway dashboard (or CLI):

```bash
# Add PostgreSQL
railway add --plugin postgresql

# Add Redis
railway add --plugin redis
```

Railway auto-provisions these and exposes connection variables:
- `DATABASE_URL` (from PostgreSQL plugin)
- `REDIS_URL` (from Redis plugin)

---

## Step 3: Deploy Backend Service

```bash
# Create the backend service
railway service create backend

# Link your CLI to the backend service
railway link
# Select the "backend" service when prompted

# Set the root directory
railway settings set rootDirectory backend
```

### Backend Environment Variables

```bash
railway variables set \
  DATABASE_URL='${{Postgres.DATABASE_URL}}' \
  REDIS_URL='${{Redis.REDIS_URL}}' \
  RABBITMQ_URL='${{Redis.REDIS_URL}}' \
  SECRET_KEY='<run: openssl rand -hex 32>' \
  UNSUBSCRIBE_HMAC_KEY='<run: openssl rand -hex 16>' \
  ENVIRONMENT=production \
  CORS_ORIGINS='https://your-frontend.up.railway.app' \
  PORT=8000
```

> **Important**: Replace `RABBITMQ_URL` with the Redis URL to use Redis as the Celery broker. This requires updating `backend/app/workers/celery_app.py` to accept Redis URLs, or simply setting the variable since Celery supports Redis natively.

### Backend Start Command

Set in Railway dashboard under Service → Settings → Deploy:

```
sh -c 'python -m alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2 --loop uvloop --http httptools --proxy-headers --forwarded-allow-ips=*'
```

### Backend Health Check

- **Path**: `/health`
- **Timeout**: 300s

---

## Step 4: Deploy Worker Service

```bash
# Create the worker service
railway service create worker

# Link your CLI to the worker service
railway link
# Select the "worker" service when prompted

# Use the same backend directory
railway settings set rootDirectory backend
```

### Worker Environment Variables

```bash
railway variables set \
  DATABASE_URL='${{Postgres.DATABASE_URL}}' \
  REDIS_URL='${{Redis.REDIS_URL}}' \
  RABBITMQ_URL='${{Redis.REDIS_URL}}' \
  SECRET_KEY='<same as backend>' \
  UNSUBSCRIBE_HMAC_KEY='<same as backend>' \
  ENVIRONMENT=production
```

### Worker Start Command

```
celery -A app.workers.celery_app worker --loglevel=info --concurrency=2
```

> **No health check** needed for the worker — it is not an HTTP service.

---

## Step 5: Deploy Frontend Service

```bash
# Create the frontend service
railway service create frontend

# Link your CLI to the frontend service
railway link
# Select the "frontend" service when prompted

# Set the root directory
railway settings set rootDirectory frontend
```

### Frontend Environment Variables

```bash
railway variables set \
  BACKEND_URL='http://${{backend.RAILWAY_PRIVATE_DOMAIN}}:8000' \
  NEXT_PUBLIC_BACKEND_URL='https://${{backend.RAILWAY_PUBLIC_DOMAIN}}' \
  NEXTAUTH_URL='https://your-frontend.up.railway.app' \
  NEXTAUTH_SECRET='<run: openssl rand -hex 32>' \
  PORT=3000
```

> **Private networking**: `BACKEND_URL` uses Railway's internal private domain for server-side API calls (Next.js rewrites). `NEXT_PUBLIC_BACKEND_URL` uses the public domain for client-side requests.

### Frontend Build Args

The Dockerfile accepts build-time ARGs:
- `NEXT_PUBLIC_BACKEND_URL` — baked into the client bundle at build time
- `BACKEND_URL` — used by Next.js server-side rewrites

Set these in Railway dashboard under Service → Settings → Build → Build Arguments.

### Frontend Health Check

- **Path**: `/`
- **Timeout**: 300s

---

## Step 6: Configure Custom Domains

In the Railway dashboard, for each service:

1. **Frontend**: Add `app.fortressflow.com` → update DNS CNAME to Railway's domain
2. **Backend**: Add `api.fortressflow.com` → update DNS CNAME to Railway's domain

After adding custom domains, update environment variables:

```bash
# Backend
railway variables set CORS_ORIGINS='https://app.fortressflow.com'

# Frontend
railway variables set \
  NEXT_PUBLIC_BACKEND_URL='https://api.fortressflow.com' \
  BACKEND_URL='http://${{backend.RAILWAY_PRIVATE_DOMAIN}}:8000' \
  NEXTAUTH_URL='https://app.fortressflow.com'
```

---

## Step 7: Add Third-Party Secrets

Set these on the **backend** service as needed:

```bash
railway variables set \
  SENTRY_DSN='https://...' \
  HUBSPOT_API_KEY='...' \
  ZOOMINFO_CLIENT_ID='...' \
  ZOOMINFO_CLIENT_SECRET='...' \
  ZOOMINFO_API_KEY='...' \
  APOLLO_API_KEY='...' \
  TWILIO_ACCOUNT_SID='...' \
  TWILIO_AUTH_TOKEN='...' \
  TWILIO_PHONE_NUMBER='...' \
  AWS_ACCESS_KEY_ID='...' \
  AWS_SECRET_ACCESS_KEY='...' \
  AWS_REGION='us-east-1' \
  SES_FROM_EMAIL='outreach@mail.fortressflow.com' \
  SES_CONFIGURATION_SET='fortressflow-tracking' \
  SENDING_SUBDOMAIN='mail.fortressflow.com' \
  GROQ_API_KEY='...' \
  OPENAI_API_KEY='...'
```

Set these on the **worker** service too (it needs the same secrets for async task processing).

---

## Step 8: Deploy

```bash
# Deploy all services
railway up

# Or deploy from the dashboard by connecting your GitHub repo
# Railway will auto-deploy on push to main
```

---

## Verifying the Deployment

```bash
# Backend health
curl https://api.fortressflow.com/health
# Expected: {"status": "ok", "version": "0.7.0", "environment": "production"}

# Backend readiness (checks DB + Redis)
curl https://api.fortressflow.com/ready

# Frontend
curl -I https://app.fortressflow.com
# Expected: HTTP/2 200
```

---

## Railway-Specific Notes

### Database Migrations

Migrations run automatically on each backend deploy via the start command. To run manually:

```bash
railway run -s backend -- python -m alembic upgrade head
```

### Scaling

```bash
# Scale backend to 2 replicas (Pro plan required)
# Set in Railway dashboard → Service → Settings → Replicas
```

### Logs

```bash
# View service logs
railway logs -s backend
railway logs -s frontend
railway logs -s worker
```

### PostgreSQL Connection

Railway's `DATABASE_URL` uses the standard `postgresql://` scheme. The backend expects `postgresql+asyncpg://`. Handle this with a variable reference or by adjusting the `DATABASE_URL` format:

```bash
# Option A: Set explicitly with asyncpg driver
railway variables set \
  DATABASE_URL='postgresql+asyncpg://...'

# Option B: Modify backend/app/config.py to auto-convert
# (add .replace("postgresql://", "postgresql+asyncpg://") in the Settings class)
```

### Cost Estimate (Railway Pro)

| Service    | Approximate Monthly Cost |
|------------|-------------------------|
| Backend    | $5–10                   |
| Frontend   | $5–10                   |
| Worker     | $5–10                   |
| PostgreSQL | $5–15                   |
| Redis      | $3–5                    |
| **Total**  | **~$23–50/month**       |

Costs scale with usage. Railway charges per vCPU-hour and GB-hour of RAM.

---

## Rollback

Railway keeps deploy history. To rollback:

1. Go to the Railway dashboard
2. Select the service
3. Click on Deployments
4. Click "Rollback" on a previous successful deploy

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Build fails with ESLint/TS errors | `next.config.ts` already configured to ignore build errors |
| `DATABASE_URL` scheme mismatch | See PostgreSQL Connection section above |
| Frontend can't reach backend | Check `BACKEND_URL` uses private domain for server-side, public for client |
| Celery can't connect to broker | Ensure `RABBITMQ_URL` points to Redis URL if using Redis as broker |
| Health check failing | Increase timeout to 300s; check service logs for startup errors |
