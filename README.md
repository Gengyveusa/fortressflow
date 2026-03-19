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
- **AI Platforms**: HubSpot Breeze AI + ZoomInfo Copilot + Apollo AI (2026)

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

## Phase 3: Deliverability Fortress

### Architecture Overview

Phase 3 implements a production-grade email deliverability system with AI-powered warmup:

```
┌──────────────────────────────────────────────────────┐
│                  Deliverability Router                 │
│  Round-robin rotation across 5-10 sending identities  │
│  Health-aware routing · Daily cap: 300-400 touches    │
└────────────────┬─────────────────────────────────────┘
                 │
    ┌────────────┴────────────┐
    │    Sending Identities   │
    │  outreach1@mail.domain  │
    │  outreach2@mail.domain  │
    │  outreach3@mail.domain  │
    │  ... up to 10 inboxes   │
    └────────────┬────────────┘
                 │
    ┌────────────┴────────────┐
    │    Amazon SES (v2)      │
    │  Dedicated IP Pool      │
    │  Configuration Set      │
    │  Event Tracking         │
    └────────────┬────────────┘
                 │
    ┌────────────┴──────────────────────────┐
    │  DNS Authentication Layer              │
    │  SPF · DKIM · DMARC · BIMI            │
    │  Strict alignment · Dedicated subdomain│
    └───────────────────────────────────────┘
```

### AI-Powered Warmup System

The warmup engine uses a 4-6 week progressive ramp with AI-selected seeds:

| Week | Daily Volume | Cumulative | Strategy |
|------|-------------|------------|----------|
| 1 | 5-8 | ~50 | AI-selected high-engagement seeds |
| 2 | 9-15 | ~120 | Expand to medium-engagement contacts |
| 3 | 16-25 | ~260 | Widen audience with health monitoring |
| 4 | 26-35 | ~470 | Full monitoring, auto-pause if unhealthy |
| 5 | 36-45 | ~750 | Approaching target volume |
| 6 | 46-50 | ~1,090 | Full production capacity |

**Safety thresholds (auto-pause triggers):**
- Bounce rate > 5%
- Spam/complaint rate > 0.1%
- Open rate < 15% (after 50+ sends)

### Platform AI Integration

FortressFlow maximizes three paid AI platforms for smarter outreach:

#### HubSpot Breeze AI
- **Data Agent**: Contact-level engagement insights and predictive scoring
- **Prospecting Agent**: Identifies ideal warmup seeds by engagement likelihood
- **Content Agent**: Subject line optimization and personalization suggestions
- **Breeze Studio**: Advanced workflow orchestration

#### ZoomInfo Copilot
- **GTM Workspace**: Account-level intelligence (tech stack, org hierarchy, funding)
- **GTM Context Graph**: Intent signals and buying behavior scoring

#### Apollo AI (2026 Agentic)
- **AI Scoring**: Enhanced lead scoring with MCP + Claude integration
- **Waterfall Enrichment**: Cascading data sources for maximum coverage
- **Agentic Workflows**: Natural language-driven automation

#### Bi-Directional Learning Loops

```
Platform AI recommends seeds → FortressFlow sends warmup emails
    → Tracks outcomes (opens, replies, bounces)
        → Feeds results back to platforms
            → Platforms refine scoring models
                → Better seed recommendations next cycle
```

### Sending Identity Rotation

FortressFlow rotates across 5-10 verified sending identities:

```bash
# Add sending identities via API
POST /api/v1/deliverability/inboxes
{
  "email_address": "outreach1@mail.gengyveusa.com",
  "display_name": "Thad - Gengyve USA",
  "domain": "mail.gengyveusa.com"
}
```

The deliverability router automatically:
1. Round-robin selects the next healthy inbox
2. Checks daily per-inbox and total volume caps
3. Skips inboxes with health_score < 50
4. Updates reputation metrics on SES events (bounce, complaint, open)

## Multi-Channel Outreach

FortressFlow supports three outreach channels, all gated behind compliance:

### Email (Amazon SES)
- HTML + plain text composition with template engine
- Tracking pixel injection for open tracking
- RFC 8058 one-click unsubscribe headers
- Bounce/complaint webhook processing
- AI-powered 4-6 week warmup with platform AI seed selection

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

### Deliverability Endpoints (Phase 3)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/deliverability/domains` | List sending domains |
| `POST` | `/api/v1/deliverability/domains` | Add domain (triggers SES verification) |
| `GET` | `/api/v1/deliverability/domains/{name}/dns` | DNS setup instructions |
| `GET` | `/api/v1/deliverability/inboxes` | List sending inboxes |
| `POST` | `/api/v1/deliverability/inboxes` | Create inbox (auto-warmup config) |
| `POST` | `/api/v1/deliverability/inboxes/{id}/pause` | Pause inbox |
| `POST` | `/api/v1/deliverability/inboxes/{id}/resume` | Resume inbox |
| `GET` | `/api/v1/deliverability/warmup` | Warmup queue status |
| `GET` | `/api/v1/deliverability/warmup/config/{id}` | Warmup config for inbox |
| `PUT` | `/api/v1/deliverability/warmup/config/{id}` | Update warmup config |
| `GET` | `/api/v1/deliverability/warmup/ramp-schedule` | Preview ramp schedule |
| `GET` | `/api/v1/deliverability/dashboard` | Full deliverability dashboard |

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
| `POST` | `/api/v1/presets/{index}/deploy` | Deploy a preset |

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

## Celery Beat Schedule

| Task | Schedule | Description |
|------|----------|-------------|
| Re-verify stale leads | Daily 2:00 AM UTC | Re-enrich leads older than 90 days |
| Sequence engine | Every 15 min | Advance enrolled leads through steps |
| Warmup cycle | Daily 6:00 AM UTC | AI-powered warmup for all inboxes |
| Warmup feedback loop | Daily 7:00 AM UTC | Send outcomes to AI platforms |
| Reset daily counters | Daily midnight UTC | Reset per-inbox send counters |
| Domain metrics | Hourly (:30) | Aggregate inbox → domain metrics |
| Health score recalc | Every 6 hours (:15) | Recalculate inbox health scores |

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

### HubSpot (with Breeze AI)

1. Create a Private App in HubSpot with `crm.objects.contacts.write` and `crm.objects.notes.write` scopes
2. Copy the API key to `HUBSPOT_API_KEY` in `.env`
3. **Enable Breeze AI**: Set `HUBSPOT_BREEZE_ENABLED=true` in `.env`
4. Ensure your HubSpot plan includes Breeze AI features (Professional+ required)
5. Breeze agents used:
   - **Data Agent**: Provides contact engagement insights for warmup seed selection
   - **Prospecting Agent**: Identifies high-engagement contacts as warmup seeds
   - **Content Agent**: Optimizes email subject lines and personalization
   - **Breeze Studio**: Orchestrates advanced AI workflows

### ZoomInfo (with Copilot)

1. Obtain API credentials from ZoomInfo
2. Set `ZOOMINFO_CLIENT_ID` and `ZOOMINFO_CLIENT_SECRET` in `.env`
3. **Enable Copilot**: Set `ZOOMINFO_COPILOT_ENABLED=true` in `.env`
4. Copilot features used:
   - **GTM Workspace**: Account intelligence (tech stack, org chart, funding)
   - **GTM Context Graph**: Intent signals and buyer behavior scoring

### Apollo.io (with AI Assistant)

1. Get API key from Apollo.io settings
2. Set `APOLLO_API_KEY` in `.env`
3. **Enable AI**: Set `APOLLO_AI_ENABLED=true` in `.env`
4. Apollo AI features used:
   - **Enhanced AI Scoring**: Lead quality scoring with MCP + Claude
   - **Waterfall Enrichment**: Cascading data sources for maximum coverage
   - **Agentic Workflows**: Natural language automation

### Twilio (SMS)

1. Set up a 10DLC phone number in Twilio
2. Configure `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` in `.env`

### Amazon SES (Email)

1. Use FortressFlow's DNS setup endpoint to get required records:
   ```
   GET /api/v1/deliverability/domains/{domain}/dns
   ```
2. Add the returned DNS records to your domain (SPF, DKIM CNAMEs, DMARC, BIMI)
3. Configure in `.env`:
   ```
   AWS_ACCESS_KEY_ID=your-key
   AWS_SECRET_ACCESS_KEY=your-secret
   AWS_REGION=us-east-1
   SES_FROM_EMAIL=outreach@mail.gengyveusa.com
   SENDING_SUBDOMAIN=mail.gengyveusa.com
   SES_CONFIGURATION_SET=fortressflow-tracking
   DEDICATED_IP_POOL=fortressflow-pool
   ```
4. Add sending identities via the API:
   ```
   POST /api/v1/deliverability/inboxes
   ```

## Email Deliverability

FortressFlow implements a comprehensive deliverability fortress:

- **Dedicated subdomain**: Full SPF/DKIM/DMARC/BIMI on `mail.gengyveusa.com`
- **AI-powered 4-6 week warmup**: Platform AI selects high-engagement seeds
- **Identity rotation**: 5-10 sending identities with round-robin routing
- **Health monitoring**: Auto-pause on bounce > 5% or spam > 0.1%
- **Daily volume cap**: 300-400 email touches/day across all identities
- **Bi-directional learning**: Warmup outcomes feed back to AI platforms
- **SES event tracking**: Real-time bounce/complaint/open/click processing
- **Dedicated IP pool**: Managed IP allocation for consistent reputation

## Monitoring

- **Prometheus** scrapes `/metrics` every 15 seconds
- **Grafana** dashboards for delivery rates, bounce rates, consent stats
- **Sentry** for error tracking (set `SENTRY_DSN` in `.env`)
- **Deliverability Dashboard**: `GET /api/v1/deliverability/dashboard` for real-time inbox/domain health

## License

MIT
