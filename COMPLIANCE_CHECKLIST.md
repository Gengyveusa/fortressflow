# FortressFlow Compliance Checklist

Pre-launch compliance verification for Gengyve USA Inc. operations.
Review each item with your legal counsel before beginning production sending.
This checklist does not constitute legal advice.

Last updated: March 2026

---

## CAN-SPAM Compliance (15 U.S.C. § 7701 et seq.)

### Identification

- [ ] Physical mailing address of Gengyve USA Inc. is included in every outgoing commercial email
- [ ] "From" name accurately identifies Gengyve USA or the authorised sender
- [ ] "Reply-To" address is functional and monitored
- [ ] Subject lines do not use deceptive or misleading language
- [ ] Emails are identified as advertising or solicitations where required

### Opt-Out Mechanism

- [ ] Every commercial email includes a clear and conspicuous opt-out link
- [ ] Opt-out mechanism does not require the recipient to pay a fee, provide personally identifiable information, or take any steps other than sending a reply email or visiting a single page on a website
- [ ] Opt-out requests are honoured within **10 business days**
- [ ] Suppressed addresses are never re-added to a mailing list without fresh consent
- [ ] The unsubscribe endpoint (`/api/v1/leads/unsubscribe`) is tested and functional in production
- [ ] HMAC-signed unsubscribe tokens are validated server-side before processing
- [ ] Opt-out confirmation email is sent to the suppressed address

### Third-Party Senders

- [ ] Any third-party email vendors (e.g., AWS SES) have been informed that commercial email must comply with CAN-SPAM
- [ ] FortressFlow retains liability as the initiating sender and has contractual representations from any third party that it will comply

---

## GDPR Compliance (EU 2016/679)

### Lawful Basis

- [ ] A lawful basis for processing personal data has been identified and documented for each data category:
  - Outreach to EU contacts: **Legitimate interests** (Article 6(1)(f)) — LIA completed and documented
  - Newsletter subscribers: **Consent** (Article 6(1)(a)) — explicit opt-in mechanism in place
- [ ] Legitimate Interests Assessment (LIA) is on file and reviewed by legal counsel
- [ ] Balancing test confirms interests do not override data subjects' rights

### Transparency

- [ ] Privacy notice is accessible and written in plain language
- [ ] Privacy notice covers: identity of controller, purposes of processing, legal basis, retention periods, third-party sharing, and data subject rights
- [ ] Privacy notice is linked from all data collection points (import forms, landing pages, email footers)

### Data Subject Rights

- [ ] **Right of access** (Article 15): `/api/v1/compliance/export` returns all personal data for a subject within 30 days
- [ ] **Right to rectification** (Article 16): leads can be updated via the admin interface
- [ ] **Right to erasure / right to be forgotten** (Article 17): `/api/v1/compliance/erasure` permanently deletes all personal data and logs the deletion in the audit table
- [ ] **Right to restriction** (Article 18): contacts can be marked as processing-restricted without deletion
- [ ] **Right to data portability** (Article 20): export endpoint returns data in machine-readable format (JSON / CSV)
- [ ] **Right to object** (Article 21): unsubscribe / opt-out mechanism satisfies this right for marketing processing
- [ ] Data subject request workflow is documented and response SLA is ≤30 days

### Data Processing Records

- [ ] Article 30 Records of Processing Activities (RoPA) are maintained in `docs/legal/ropa.md`
- [ ] All data processing activities are catalogued with purpose, legal basis, data categories, recipients, and retention periods
- [ ] Records are updated whenever a new data source or processing activity is added

### Sub-processors and DPA

- [ ] Data Processing Agreements (DPAs) are in place with all sub-processors:
  - [ ] AWS (SES, RDS, S3) — DPA via AWS Customer Agreement
  - [ ] Sentry — DPA executed
  - [ ] Twilio — DPA executed
  - [ ] HubSpot — DPA executed (if Breeze AI enabled)
  - [ ] ZoomInfo — DPA executed (if Copilot enabled)
  - [ ] Apollo.io — DPA executed (if AI features enabled)
- [ ] Sub-processor list is published and kept up to date
- [ ] Customers (if any) are notified before new sub-processors are added

### International Transfers

- [ ] Any transfer of EU personal data to the US relies on a valid transfer mechanism (Standard Contractual Clauses, adequacy decision, or Binding Corporate Rules)
- [ ] Transfer Impact Assessments (TIAs) completed for all US-based sub-processors

---

## TCPA Compliance (47 U.S.C. § 227) — SMS Channel

### Consent

- [ ] **Express written consent** has been obtained from each recipient before sending any marketing SMS
- [ ] Consent records include: date/time, IP address, opt-in method, and exact consent language shown to the user
- [ ] Consent records are stored in the `sms_consent` table and can be retrieved per contact
- [ ] Consent is not buried in general terms and conditions — it is a standalone, conspicuous disclosure

### Opt-Out

- [ ] STOP keyword triggers immediate suppression via the Twilio webhook
- [ ] HELP keyword returns a compliant help message including sender identity and opt-out instructions
- [ ] Opt-out confirmations are sent as required by carrier guidelines
- [ ] Opt-outs are permanent unless the recipient affirmatively re-opts-in

### Time Restrictions

- [ ] All SMS are sent between **8:00 am and 9:00 pm** in the **recipient's local timezone** (TCPA § 227(b)(1)(C)(i))
- [ ] Timezone inference from area code or contact record is tested and accurate
- [ ] Messages queued outside the permitted window are held and delivered at the next permitted time

### Do Not Call (DNC) List

- [ ] National DNC Registry scrubbing is performed at import time and before each campaign send
- [ ] Company-level DNC list is maintained and synced to the suppression table
- [ ] State-specific DNC lists are checked where required (Florida, Indiana, Wyoming, etc.)
- [ ] DNC scrub records are retained for evidence of compliance

### Registration (10DLC)

- [ ] Brand registration submitted to The Campaign Registry (TCR)
- [ ] Campaign registered with TCR with accurate use case description
- [ ] Phone number(s) linked to the registered campaign
- [ ] Carrier throughput limits are respected (standard 10DLC: 75 msg/s)

---

## CCPA / CPRA Compliance (Cal. Civ. Code § 1798.100 et seq.)

### Consumer Rights

- [ ] **Right to know**: consumers can request disclosure of personal information collected, sold, or disclosed in the past 12 months
- [ ] **Right to delete**: deletion requests are honoured within 45 days (90 with extension notice)
- [ ] **Right to opt-out of sale or sharing**: "Do Not Sell or Share My Personal Information" link is present on the website
- [ ] `/api/v1/compliance/do-not-sell` endpoint correctly flags contacts and prevents future data sharing
- [ ] **Right to correct**: inaccurate personal information can be corrected by the consumer
- [ ] **Right to limit use of sensitive personal information**: process for limiting use is documented

### Privacy Policy

- [ ] Privacy policy is published at `/privacy` and accessible from every page footer
- [ ] Policy discloses all categories of personal information collected, purposes of use, and retention periods
- [ ] Policy discloses whether personal information is sold or shared and the categories of third parties involved
- [ ] Policy includes contact information for submitting privacy requests (email + mail address)
- [ ] Policy was last reviewed within the past 12 months

### Data Inventory

- [ ] Comprehensive data inventory is maintained in `docs/legal/data-inventory.md`
- [ ] Inventory maps each data element to: source, purpose, legal basis, retention period, and third-party sharing
- [ ] Inventory is updated within 30 days of adding a new data type or processing activity

### Service Provider Agreements

- [ ] Written contracts with all service providers confirm they process data only as directed and do not sell or share data
- [ ] Contracts include required CCPA/CPRA service provider provisions

---

## Technical Security

### Transport & Encryption

- [ ] HTTPS enforced on all public-facing endpoints (HTTP → HTTPS redirect in Nginx)
- [ ] TLS 1.2 minimum; TLS 1.3 preferred
- [ ] HSTS header configured with `max-age=31536000; includeSubDomains; preload`
- [ ] Database connections use TLS in production (`sslmode=require`)
- [ ] Redis connections use TLS in production (if Redis 6+ with TLS enabled)
- [ ] Secrets at rest are encrypted at the storage level (AWS RDS encryption, EBS encryption)

### Authentication & Authorisation

- [ ] All protected API endpoints require a valid JWT Bearer token
- [ ] JWT secret (`SECRET_KEY`) is at least 64 hex characters and randomly generated
- [ ] Tokens expire after an appropriate interval (default: 60 minutes)
- [ ] Admin actions require elevated token scope or re-authentication
- [ ] Passwords are hashed with bcrypt (work factor ≥ 12)
- [ ] Brute-force protection: account lockout after N failed login attempts

### Rate Limiting

- [ ] Redis-backed rate limiting is active (`RedisRateLimitMiddleware`)
- [ ] Per-endpoint policies are configured (see `middleware/redis_rate_limit.py`)
- [ ] Rate limit response headers (`X-RateLimit-*`) are returned to clients
- [ ] Fallback to in-process rate limiting is tested and working

### CSRF Protection

- [ ] `CSRFMiddleware` is active and tested
- [ ] CSRF validation passes on all mutating endpoints (POST/PUT/PATCH/DELETE)
- [ ] Webhook endpoints are correctly exempted
- [ ] Bearer-authenticated API endpoints are correctly exempted

### Security Headers

- [ ] `X-Content-Type-Options: nosniff` present on all responses
- [ ] `X-Frame-Options: DENY` present on all responses
- [ ] `X-XSS-Protection: 1; mode=block` present on all responses
- [ ] `Referrer-Policy: strict-origin-when-cross-origin` present on all responses
- [ ] `Permissions-Policy` header restricts unused browser features
- [ ] `Content-Security-Policy` is deployed and tested (production policy is strict)
- [ ] `Strict-Transport-Security` is set in production with `includeSubDomains`
- [ ] `Server` header is removed or set to a non-revealing value

### Input Validation

- [ ] All request bodies are validated by Pydantic models before reaching route handlers
- [ ] SQL injection prevention: all database queries use parameterised statements (SQLAlchemy ORM)
- [ ] XSS prevention: all user-supplied content is escaped before rendering
- [ ] Request body size is capped at 10 MB (`RequestValidationMiddleware`)
- [ ] File upload types are validated (MIME type + extension whitelist)
- [ ] Suspicious user-agents are blocked (`RequestValidationMiddleware`)

### Dependency & Secret Management

- [ ] `pip-audit` or `safety` runs in CI to detect known CVEs in Python dependencies
- [ ] `npm audit` runs in CI for frontend dependencies
- [ ] Dependabot (or Renovate) is configured for automated dependency PRs
- [ ] No secrets, API keys, or passwords are committed to source control
- [ ] `.env` and `*.pem` files are in `.gitignore`
- [ ] Secrets are injected at runtime via environment variables or a secrets manager (AWS Secrets Manager, Vault)
- [ ] Secret rotation policy documented: API keys rotated ≥ annually or on personnel change

---

## Email Deliverability

### DNS Authentication

- [ ] SPF record published for sending subdomain (`mail.yourcompany.com`)
- [ ] DKIM signing enabled and CNAME records published (Easy DKIM via SES)
- [ ] DMARC policy published; start at `p=none` and progress to `p=reject` over 4–6 weeks
- [ ] DMARC RUA reports are being received and reviewed weekly
- [ ] BIMI record published (optional; requires `p=quarantine` or `p=reject` DMARC)

### Infrastructure

- [ ] Dedicated sending subdomain configured (`SENDING_SUBDOMAIN` env var)
- [ ] Dedicated IP pool configured in SES (`DEDICATED_IP_POOL` env var)
- [ ] SES Configuration Set created with SNS event destinations for bounces, complaints, opens, and clicks
- [ ] SES production access requested and approved (out of sandbox)
- [ ] Multiple sending identities configured (up to 10) for inbox rotation

### Warmup

- [ ] IP warmup plan documented and approved by deliverability lead
- [ ] Warmup scheduler is running and following the ramp schedule
- [ ] Warmup volume caps are respected (`DAILY_WARMUP_VOLUME_CAP`)
- [ ] Warmup emails use high-quality, engaged seed lists to build positive reputation
- [ ] Warmup Grafana panel monitored daily for the duration of the warmup period

### Reputation Monitoring

- [ ] Bounce handling automated: hard bounces suppress the address immediately; soft bounces after 3 failures
- [ ] Spam complaint handling automated: complaint events suppress the address within seconds
- [ ] Circuit-breaker thresholds configured: pause sending at >5 % bounce or >0.1 % spam complaint rate
- [ ] Google Postmaster Tools domain verified and monitored (if sending to Gmail users)
- [ ] Microsoft SNDS / JMRP enrolled (if sending to Outlook / Hotmail / Live users)
- [ ] Open rate monitored; alert triggered if below 15 % for more than 1 hour

### List Hygiene

- [ ] Email validation performed at import time (syntax + MX record check)
- [ ] Stale contacts (>6 months without engagement) are suppressed or re-opted-in before sending
- [ ] Suppression lists are backed up and not accidentally overwritten during data imports
- [ ] Role-based addresses (`postmaster@`, `admin@`, `support@`) are filtered from outbound sequences
