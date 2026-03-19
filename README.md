# FortressFlow

Production-ready ethical B2B lead-gen + multi-channel sequencer platform with compliance-first architecture.

## Overview

FortressFlow is a legitimate B2B outreach tool — NOT a blackhat scraper. All leads come from user-uploaded/verified sources only (ZoomInfo/Apollo enrichment + professional meeting notes). Every outreach channel is gated behind explicit consent verification.

## Tech Stack

- **Backend**: Python 3.12 + FastAPI (async)
- **Database**: PostgreSQL 16 + Redis 7 (queues/rate limits)
- **Workers**: Celery + RabbitMQ
- **Frontend**: Next.js 15 (App Router) + React Flow + Tailwind CSS + shadcn/ui
- **Auth**: NextAuth
- **Infra**: Docker + docker-compose
- **Monitoring**: Sentry + Prometheus + Grafana

## Quick Start

### Prerequisites
- Docker & docker-compose
- Node.js 20+ (for local frontend development)
- Python 3.12+ (for local backend development)

### 1. Clone and Configure

```bash
git clone https://github.com/Gengyveusa/fortressflow.git
cd fortressflow
cp .env.example .env
# Edit .env and set secure values for SECRET_KEY and UNSUBSCRIBE_HMAC_KEY
```

### 2. Start All Services

```bash
docker-compose up -d
```

This starts:
- PostgreSQL on port 5432
- Redis on port 6379
- RabbitMQ on ports 5672 + 15672 (management UI)
- FastAPI backend on port 8000
- Celery worker
- Next.js frontend on port 3000
- Prometheus on port 9090
- Grafana on port 3001

### 3. Run Migrations

```bash
docker-compose exec backend alembic upgrade head
```

### 4. Access the Platform

- **Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **RabbitMQ**: http://localhost:15672 (fortressflow/fortressflow_dev)
- **Grafana**: http://localhost:3001 (admin/admin)

## Multi-Channel Outreach

FortressFlow supports three outreach channels, all gated behind compliance:

### Email (Amazon SES)
- HTML + plain text composition with template engine
- Tracking pixel injection for open tracking
- RFC 8058 one-click unsubscribe headers
- Bounce/complaint webhook processing
- 4-week warmup schedule (5 → 400 emails/day)

### SMS (Twilio)
- 10DLC-compliant SMS delivery
- STOP keyword auto-DNC processing
- Segment counting (160 char limit awareness)
- Status callback webhook handling

### LinkedIn
- Connection request with personalized note (300 char limit)
- InMail composition with subject/body
- Direct message to existing connections
- CSV export for manual execution workflows
- Rate limiting (25/day safe limit)

## Template Engine

All outreach content uses `{{variable}}` interpolation:

| Variable | Description |
|----------|-------------|
| `{{first_name}}` | Lead's first name |
| `{{last_name}}` | Lead's last name |
| `{{company}}` | Lead's company |
| `{{title}}` | Lead's job title |
| `{{sender_name}}` | Your name |
| `{{sender_company}}` | Your company |
| `{{unsubscribe_url}}` | HMAC-signed unsubscribe link |

## Gengyve Sequence Presets

Three pre-built outreach sequences targeting dental offices and DSOs:

1. **Cold Outreach** (9 steps, ~14 days) — Multi-channel introduction: educational email hook → LinkedIn connect → value-add follow-up → SMS → breakup email
2. **Post-Meeting Follow-up** (6 steps, ~10 days) — Warm relationship sequence: thank-you + sample offer → LinkedIn connect → sample check-in → SMS
3. **Re-engagement Nurture** (7 steps, ~21 days) — Education-first re-warming: clinical research share → case study → LinkedIn value-add → open door final touch

Deploy any preset with one API call: `POST /api/v1/presets/{index}/deploy`

## Sequence Engine

The sequence engine runs every 15 minutes (configurable via `SEQUENCE_ENGINE_INTERVAL_MINUTES`) and:

1. Finds all active enrollments where the next step delay has elapsed
2. Checks compliance gate (consent + DNC + daily limits)
3. Loads and renders the step's template with lead data
4. Dispatches via the appropriate channel service
5. Logs the touch and advances the enrollment

## API Reference

### Template Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/templates/` | Create a template |
| `GET` | `/api/v1/templates/` | List templates (filterable) |
| `GET` | `/api/v1/templates/{id}` | Get template details |
| `PUT` | `/api/v1/templates/{id}` | Update a template |
| `DELETE` | `/api/v1/templates/{id}` | Deactivate a template |
| `POST` | `/api/v1/templates/preview` | Preview with sample data |

### Preset Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/presets/` | List available presets |
| `POST` | `/api/v1/presets/{index}/deploy` | Deploy a preset (creates sequence + templates) |

### Compliance Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/compliance/check` | Check if lead can be contacted |
| `POST` | `/api/v1/compliance/consent` | Record consent with proof |
| `POST` | `/api/v1/compliance/revoke` | Revoke consent |
| `GET` | `/api/v1/compliance/audit/{lead_id}` | Full audit trail |
| `POST` | `/api/v1/unsubscribe/{token}` | One-click unsubscribe |

### Lead Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/leads/` | Create a lead |
| `GET` | `/api/v1/leads/` | List leads (paginated) |
| `GET` | `/api/v1/leads/{id}` | Get lead details |
| `POST` | `/api/v1/leads/import/csv` | Bulk CSV import |
| `POST` | `/api/v1/leads/{id}/touch` | Log an outreach touch |

## Development

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Start PostgreSQL and Redis first
docker-compose up -d postgres redis rabbitmq

# Run migrations
alembic upgrade head

# Start dev server
uvicorn app.main:app --reload
```

### Running Tests

```bash
cd backend
pytest -v
```

### Frontend

```bash
cd frontend
npm install --legacy-peer-deps
npm run dev
```

## Compliance Architecture

FortressFlow implements a **hard-gate compliance system**:

1. **Consent Gate**: Every outreach channel (email, SMS, LinkedIn) requires explicit, tracked consent
2. **DNC Checks**: Global and per-channel Do-Not-Contact list checked before every send
3. **Daily Limits**: Per-lead rate limits enforced (100 emails, 30 SMS, 25 LinkedIn per day)
4. **Validation**: Email and phone numbers validated before any contact attempt
5. **Audit Trail**: Every touch logged with full metadata, retained for 5+ years
6. **One-Click Unsubscribe**: HMAC-signed tokens auto-add to DNC list
7. **STOP Keyword**: Auto-DNC on SMS STOP keyword detection

### Consent Methods

- `meeting_card`: Business card exchanged at professional meeting
- `web_form`: Web form opt-in with IP/timestamp proof
- `import_verified`: ZoomInfo/Apollo verified professional contact

## Integration Setup

### HubSpot

1. Create a Private App in HubSpot with `crm.objects.contacts.write` and `crm.objects.notes.write` scopes
2. Copy the API key to `HUBSPOT_API_KEY` in `.env`

### ZoomInfo

1. Obtain API credentials from ZoomInfo
2. Set `ZOOMINFO_CLIENT_ID` and `ZOOMINFO_CLIENT_SECRET` in `.env`

### Apollo.io

1. Get API key from Apollo.io settings
2. Set `APOLLO_API_KEY` in `.env`

### Twilio (SMS)

1. Set up a 10DLC phone number in Twilio
2. Configure `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` in `.env`

### Amazon SES (Email)

1. Verify your sending domain in AWS SES
2. Configure SPF/DKIM/DMARC records
3. Set `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `SES_FROM_EMAIL` in `.env`

## Email Deliverability

FortressFlow includes a warmup system:

- 4-week ramp schedule (5 → 400 emails/day)
- Automatic pause on bounce rate > 2% or spam rate > 0.1%
- Rotate 5-10 inboxes/domains
- Full SPF/DKIM/DMARC/BIMI configuration

## Monitoring

- **Prometheus** scrapes `/metrics` every 15 seconds
- **Grafana** dashboards for delivery rates, bounce rates, consent stats
- **Sentry** for error tracking (set `SENTRY_DSN` in `.env`)

## License

MIT
