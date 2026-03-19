# FortressFlow — Ethical B2B Lead Generation Platform

> **Compliance-first B2B outreach automation for the dental and healthcare market.**
> Built and operated by [Gengyve USA Inc.](https://gengyveusa.com)

FortressFlow is a production-grade, multi-channel outreach sequencer that puts regulatory compliance, sender reputation, and data ethics at the centre of every design decision. It is purpose-built for dental practices, DSOs, and healthcare organisations that need to reach decision-makers without compromising on CAN-SPAM, GDPR, TCPA, or CCPA obligations.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                           External Traffic                           │
└───────────────────────────────────┬──────────────────────────────────┘
                                    │ HTTPS :443
                             ┌──────▼──────┐
                             │    Nginx    │  SSL termination / reverse proxy
                             └──────┬──────┘
                    ┌───────────────┼────────────────┐
                    │               │                │
             ┌──────▼──────┐ ┌──────▼──────┐  ┌──────▼──────┐
             │  Frontend   │ │   Backend   │  │  Prometheus  │
             │ (Next.js)   │ │  (FastAPI)  │  │  + Grafana   │
             │   :3000     │ │   :8000     │  │  :9090/:3000 │
             └─────────────┘ └──────┬──────┘  └─────────────┘
                                    │
              ┌─────────────────────┼───────────────────────┐
              │                     │                       │
       ┌──────▼──────┐      ┌───────▼──────┐        ┌──────▼──────┐
       │ PostgreSQL  │      │    Redis     │        │  RabbitMQ   │
       │   :5432     │      │   :6379      │        │   :5672     │
       └─────────────┘      └─────────────┘        └──────┬──────┘
                                                           │
                                                    ┌──────▼──────┐
                                                    │    Celery   │
                                                    │   Workers   │
                                                    └──────┬──────┘
                                         ┌─────────────────┼────────────────┐
                                         │                 │                │
                                  ┌──────▼──────┐  ┌───────▼──────┐ ┌──────▼───────┐
                                  │  AWS SES    │  │   Twilio     │ │  LinkedIn    │
                                  │  (Email)    │  │   (SMS)      │ │  (Outreach)  │
                                  └─────────────┘  └──────────────┘ └──────────────┘
```

---

## Features

### Phase 1 — Compliance & Consent Engine
- Consent record management with timestamped audit trail
- Unsubscribe link generation using HMAC-signed tokens
- Suppression list management (global + per-campaign)
- GDPR right-to-erasure and data-portability endpoints
- CAN-SPAM physical address injection into all outgoing emails
- TCPA time-of-day enforcement (8 am–9 pm recipient local time)

### Phase 2 — Lead Import & Enrichment
- CSV bulk import with validation and deduplication
- Waterfall enrichment via ZoomInfo → Apollo → HubSpot
- Enrichment TTL (90 days default) with automatic stale-data refresh
- Lead scoring using configurable weighted attribute rules
- HubSpot CRM bi-directional sync

### Phase 3 — Deliverability Fortress
- Dedicated sending subdomain with SPF/DKIM/DMARC/BIMI configuration
- AWS SES dedicated IP pool with per-identity warm-up ramp (15 % daily increase, starting from 5 emails/identity/day)
- Automated bounce and spam-complaint monitoring with circuit-breaker pause (>5 % bounce, >0.1 % spam)
- Inbox rotation across up to 10 sending identities
- SES Configuration Set event tracking for opens, clicks, bounces, and complaints

### Phase 4 — Sequence Engine & Visual Builder
- Multi-step email sequences with delay rules and branching
- Drag-and-drop sequence builder (React Flow)
- Conditional branching on open, click, reply, and bounce events
- Per-contact enrollment tracking with status lifecycle (active → completed / failed / paused)
- A/B variant support at each sequence step

### Phase 5 — Multi-Channel Outreach & Reply Detection
- Unified channel orchestrator: Email + SMS (Twilio) + LinkedIn
- IMAP-based reply detection with intelligent auto-reply filtering
- Global daily send caps (400 emails, 30 SMS, 25 LinkedIn touches)
- Channel-level retry logic with configurable back-off
- Webhook listeners for SES events, Twilio status callbacks, and LinkedIn OAuth

### Phase 6 — Production Hardening
- Distributed Redis-backed sliding-window rate limiting with per-endpoint policies
- Security headers middleware (CSP, HSTS, X-Frame-Options, etc.)
- CSRF double-submit cookie protection
- Request body size enforcement (10 MB maximum)
- Suspicious user-agent blocking (sqlmap, nikto, masscan, etc.)
- Structured JSON logging (production) / pretty text logging (development)
- Full Grafana observability dashboard (request metrics, email delivery KPIs, infrastructure)
- Prometheus alerting rules with Alertmanager integration
- Sentry performance tracing with environment-aware sampling rates

### Phase 7 — In-App AI Chatbot Assistant
- Floating chat widget on every page (Intercom-style, bottom-right)
- Streaming SSE responses from Groq (primary) / OpenAI (fallback) LLMs
- Slash commands: `/status`, `/help`, `/warmup`, `/sequences`, `/compliance`, `/leads`, `/deliverability`
- Live context injection — queries DB for active sequences, deliverability health, lead counts
- AI platform routing — routes complex questions to HubSpot Breeze, ZoomInfo Copilot, Apollo AI
- Proactive onboarding message for new users ("Need help getting started?")
- Dark mode, responsive (full-screen on mobile), keyboard shortcuts, ARIA accessibility
- Chat history persisted to `chat_logs` table with session tracking
- Per-user rate limiting (30 req/min) and input sanitization
- Anonymized chat feedback pushed to AI platforms for bi-directional learning

---

## Quick Start (Development)

### Prerequisites
- Docker ≥ 24 and Docker Compose v2
- Git

### Start all services

```bash
git clone https://github.com/gengyveusa/fortressflow.git
cd fortressflow
cp .env.example .env          # fill in your API keys
docker compose up -d
```

### Run database migrations

```bash
docker compose exec backend alembic upgrade head
```

### Seed development data

```bash
docker compose exec backend python -m scripts.seed_dev
```

### Access the services

| Service            | URL                        |
|--------------------|----------------------------|
| API (Swagger UI)   | http://localhost:8000/docs  |
| API (ReDoc)        | http://localhost:8000/redoc |
| Frontend           | http://localhost:3000       |
| Grafana            | http://localhost:3001       |
| Prometheus         | http://localhost:9090       |
| RabbitMQ Console   | http://localhost:15672      |

Default credentials for local development:
- Grafana: `admin` / `admin`
- RabbitMQ: `guest` / `guest`

---

## Production Deployment

See [DEPLOYMENT.md](./DEPLOYMENT.md) for the full step-by-step deployment guide.

### Prerequisites

- Ubuntu 22.04 LTS server (4 vCPU, 16 GB RAM, 100 GB SSD minimum)
- Domain name with DNS control
- AWS account with SES access
- Twilio account (if SMS is required)

### Environment Configuration

Copy and edit the production env file:

```bash
cp .env.example .env.production
nano .env.production
```

Required variables for production:

```bash
DATABASE_URL=postgresql+asyncpg://fortressflow:STRONG_PASSWORD@postgres/fortressflow
REDIS_URL=redis://:STRONG_PASSWORD@redis:6379/0
SECRET_KEY=<64-char random hex>
SENTRY_DSN=https://...@o0.ingest.sentry.io/...
ENVIRONMENT=production
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
SES_FROM_EMAIL=outreach@mail.yourcompany.com
SENDING_SUBDOMAIN=mail.yourcompany.com
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
```

### Deploy

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

### SSL/TLS with Certbot

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourcompany.com -d www.yourcompany.com -d api.yourcompany.com
```

### Database Migrations

```bash
# Apply pending migrations
docker compose exec backend alembic upgrade head

# Create a new migration
docker compose exec backend alembic revision --autogenerate -m "describe_change"

# Roll back one step
docker compose exec backend alembic downgrade -1
```

### Monitoring Setup

Grafana dashboards are provisioned automatically via the `infra/grafana/` volume mounts.
Access Grafana at `https://grafana.yourcompany.com` and confirm the **FortressFlow — Production Dashboard** appears under Dashboards.

---

## API Documentation

- **Swagger UI**: `/docs` (disabled in production by default; enable with `ENVIRONMENT=staging`)
- **ReDoc**: `/redoc`
- **OpenAPI JSON**: `/openapi.json`

All API endpoints are versioned under `/api/v1/`.

### Authentication

All protected endpoints require a Bearer JWT token:

```http
Authorization: Bearer <token>
```

Obtain a token by posting credentials to `/api/v1/auth/token`.

---

## AI Platform Integration

FortressFlow integrates with three leading AI sales-intelligence platforms.

### HubSpot Breeze AI

Configure via environment variables:

```bash
HUBSPOT_API_KEY=...
HUBSPOT_BREEZE_ENABLED=true
HUBSPOT_BREEZE_DATA_AGENT=true        # Enrichment & insights
HUBSPOT_BREEZE_PROSPECTING_AGENT=true # Automated prospecting
HUBSPOT_BREEZE_CONTENT_AGENT=true     # Email content suggestions
```

Breeze AI surfaces intent signals and prospect summaries directly in the sequence builder UI.

### ZoomInfo Copilot

```bash
ZOOMINFO_CLIENT_ID=...
ZOOMINFO_CLIENT_SECRET=...
ZOOMINFO_COPILOT_ENABLED=true
ZOOMINFO_GTM_WORKSPACE=true    # GTM Workspace integration
ZOOMINFO_CONTEXT_GRAPH=true    # GTM Context Graph for buying signals
```

ZoomInfo Copilot provides account-level intent data and organisational chart insights during lead enrichment.

### Apollo AI Assistant

```bash
APOLLO_API_KEY=...
APOLLO_AI_ENABLED=true
APOLLO_AI_SCORING=true             # Enhanced AI lead scoring
APOLLO_WATERFALL_ENRICHMENT=true   # Multi-source waterfall enrichment
APOLLO_MCP_INTEGRATION=true        # Claude MCP integration for AI outreach
```

Apollo's 2026 agentic features allow autonomous prospecting and enrichment with Claude-powered message personalisation.

### In-App AI Chatbot

FortressFlow includes a built-in AI assistant accessible from every page via the floating chat bubble.

**Setup:**
1. Set `GROQ_API_KEY` in your `.env` (primary LLM — fast and cost-effective)
2. Optionally set `OPENAI_API_KEY` for fallback
3. The chatbot automatically injects live context from your database

**Example conversations:**
```
You: How do I warm up my inboxes?
Assistant: Great question! Here's how to set up inbox warmup in FortressFlow:
  1. Go to **Deliverability** → Add your sending domain(s)
  2. The system starts at 5 emails/day per identity and ramps 15% daily
  3. Current config: 6-week warmup, 400 emails/day cap
  • Monitor via the Deliverability Health panel on the dashboard
  • The AI automatically adjusts ramp speed based on bounce/spam rates

You: /status
Assistant: **System Status:**
  - Active Sequences: 3
  - Total Enrolled: 147
  - Bounce Rate: 1.2%
  - Spam Rate: 0.02%
  - Total Leads: 892

You: What should I do next?
Assistant: Based on your current state, here are my recommendations:
  1. Your bounce rate (1.2%) is healthy — keep going
  2. Consider creating an A/B test on your top sequence to improve reply rates
  3. Import your DSO target list from Apollo for enrichment
```

**Slash commands:** `/status`, `/help`, `/warmup`, `/sequences`, `/compliance`, `/leads`, `/deliverability`

---

## Security

### Rate Limiting

Redis-backed sliding-window rate limiting is applied to every endpoint with the following policies:

| Endpoint                      | Limit         |
|-------------------------------|---------------|
| `/api/v1/leads/import`        | 10 req/min    |
| `/api/v1/sequences/generate`  | 5 req/min     |
| `/api/v1/webhooks/*`          | 500 req/min   |
| `/health`, `/metrics`         | No limit      |
| All other endpoints           | 200 req/min   |

Rate limit headers (`X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`) are included on all responses.

### CSRF Protection

Double-submit cookie pattern. A `ff_csrf` cookie is set on every response; mutating requests (POST/PUT/PATCH/DELETE) must echo the token in the `X-CSRF-Token` header. Requests authenticated with a Bearer token and webhook endpoints are exempt.

### Security Headers

Every response includes:

| Header                     | Value                                     |
|----------------------------|-------------------------------------------|
| `X-Content-Type-Options`   | `nosniff`                                 |
| `X-Frame-Options`          | `DENY`                                    |
| `X-XSS-Protection`         | `1; mode=block`                           |
| `Referrer-Policy`          | `strict-origin-when-cross-origin`         |
| `Permissions-Policy`       | `camera=(), microphone=(), geolocation=()` |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` (production only) |
| `Content-Security-Policy`  | Strict policy (see `middleware/security.py`) |

### Input Validation

- Request bodies are capped at **10 MB**; larger payloads receive HTTP 413.
- Known scanning user-agents (sqlmap, nikto, masscan, nessus, etc.) receive HTTP 403.
- All request bodies are validated by Pydantic models before reaching route handlers.

### Data Encryption

- Passwords are hashed with bcrypt (work factor 12).
- Unsubscribe tokens are HMAC-SHA256-signed with `UNSUBSCRIBE_HMAC_KEY`.
- API keys and secrets are stored in environment variables; never committed to source control.
- Database connections use TLS in production.

---

## Monitoring & Observability

### Grafana Dashboards

The **FortressFlow — Production Dashboard** (`uid: fortressflow-main`) provides four rows of panels:

- **Row 1 — Overview**: Request rate, p50/p95/p99 latency, error rate (4xx/5xx), active Celery workers.
- **Row 2 — Email Delivery**: Emails sent today, bounce rate, spam complaint rate, warmup progress per inbox.
- **Row 3 — Sequences**: Active sequences, enrollment status pie chart, open rate trend, reply rate trend.
- **Row 4 — Infrastructure**: PostgreSQL connections, Redis memory, RabbitMQ queue depth, Celery task duration.

Dashboard auto-refreshes every 30 seconds.

### Prometheus Alerts

Defined in `infra/prometheus/alerts.yml`. Key alerts:

| Alert                  | Condition                          | Severity  |
|------------------------|------------------------------------|-----------|
| `HighErrorRate`        | >5 % 5xx for 5 min                 | critical  |
| `HighLatency`          | p95 >2 s for 5 min                 | warning   |
| `HighBounceRate`       | >5 % bounce for 15 min             | critical  |
| `HighSpamComplaintRate` | >0.1 % spam for 15 min            | critical  |
| `LowOpenRate`          | <15 % open rate for 1 h            | warning   |
| `ServiceDown`          | Backend unreachable for 2 min      | critical  |
| `HighMemoryUsage`      | >85 % RAM for 10 min               | warning   |
| `QueueBacklog`         | >1 000 RabbitMQ messages for 5 min | warning   |
| `WarmupStall`          | No warmup emails for 1 h (biz hrs) | warning   |
| `HighRateLimitHits`    | >10 HTTP 429s/min                  | warning   |

### Sentry Error Tracking

Sentry is initialised with FastAPI, Starlette, Redis, SQLAlchemy, and logging integrations. Slow requests (>5 s) generate a Sentry `warning` event with full request context. Configure via `SENTRY_DSN` in your `.env` file.

### Log Aggregation

In production, all services emit structured JSON logs to stdout. Pipe stdout to your log aggregator (Datadog, CloudWatch Logs, Loki, etc.) via the Docker logging driver:

```yaml
# docker-compose.prod.yml
services:
  backend:
    logging:
      driver: awslogs
      options:
        awslogs-group: /fortressflow/backend
        awslogs-region: us-east-1
```

---

## Testing

### Backend Tests (pytest)

```bash
# Run all tests
docker compose exec backend pytest

# With coverage
docker compose exec backend pytest --cov=app --cov-report=term-missing

# Run a specific test file
docker compose exec backend pytest tests/test_middleware.py -v
```

### Frontend E2E Tests (Playwright)

```bash
cd frontend
npx playwright install
npx playwright test
npx playwright test --ui   # Interactive mode
```

### Load Testing

```bash
# Install k6
brew install k6

# Run the load test scenario
k6 run tests/load/baseline.js --vus 50 --duration 60s
```

---

## Compliance

FortressFlow is built for compliance with US and EU regulations governing commercial electronic communications. See [COMPLIANCE_CHECKLIST.md](./COMPLIANCE_CHECKLIST.md) for the full pre-launch checklist.

### CAN-SPAM

- Physical address is automatically appended to every outgoing email.
- One-click unsubscribe links use HMAC-signed tokens to prevent forgery.
- Opt-out requests are processed within 10 business days per the Act.
- Subject lines are validated against deceptive-pattern heuristics.

### GDPR

- Lawful basis is recorded per data subject at the point of consent capture.
- Data processing records are maintained in the audit log table.
- `/api/v1/compliance/erasure` implements the right to erasure (Article 17).
- `/api/v1/compliance/export` implements data portability (Article 20).
- Sub-processor DPAs are documented in `docs/legal/sub-processors.md`.

### TCPA (SMS)

- Express written consent is required before any SMS is sent.
- STOP keyword opt-out is handled by the Twilio webhook and immediately suppresses the contact.
- Sends are enforced between 8 am and 9 pm in the recipient's local timezone.
- DNC list scrubbing is performed at import time and before each send.

### CCPA

- Do-Not-Sell requests are honoured via `/api/v1/compliance/do-not-sell`.
- Privacy policy is accessible at `/privacy`.
- Consumer data requests are fulfilled within 45 days.
- Data inventory is maintained in `docs/legal/data-inventory.md`.

---

## Contributing

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/your-feature-name`
3. Commit your changes following the [Conventional Commits](https://www.conventionalcommits.org) spec.
4. Push to your fork and open a Pull Request against `main`.
5. Ensure all tests pass and coverage does not decrease.

Please read `CONTRIBUTING.md` before submitting a PR.

---

## License

**Proprietary — All Rights Reserved**

Copyright © 2024–2026 Gengyve USA Inc. All rights reserved.

This software and associated documentation files are the exclusive property of Gengyve USA Inc. Unauthorised copying, modification, distribution, or use of this software, in whole or in part, is strictly prohibited without prior written consent from Gengyve USA Inc.

Contact: thad@gengyveusa.com
