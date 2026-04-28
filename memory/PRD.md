# GenLeadAI — Full PRD

## Stack
FastAPI + React + MongoDB + Claude AI + Resend + Calendly + Emergent Object Storage + Stripe + Sonner + Meta WhatsApp Cloud API

## Complete Feature Map

### Core LMS
Auth (JWT), Lead CRUD, Pipeline Kanban (B2B/B2C), Campaigns, Analytics (6 charts), Team, Settings, RBAC

### ARIA 3-Phase Sales PA
- Phase 1: First touch, qualification, Calendly booking, pre-call research + briefing
- Phase 2: Call hold + outcome buttons
- Phase 3: Post-call messages, 4-step proposal follow-up, Won/Lost

### Advanced Modules
Your 5 Today, Sleeping Leads + Revival Engine, No-Show Recovery, Referral Capture, Intent Signals, Broadcast Personalizer

### Production Lead Ingestion
Public REST API (API key auth), Embeddable web form, Calendly webhook, Meta Lead Ads webhook, WhatsApp webhook (verify + receive)

### Time-to-Value
- Live milestone widget on Dashboard
- Roadmap preview on Onboarding Wizard step 4
- **Celebration toast** — Sonner toaster fires share-worthy toast on milestone flip with copy-to-share button

### Pre-Call Lead Magnet (FULL)
- **Workspace config** (Settings → Lead Magnet): name, URL OR PDF/PPTX upload, send timing, customizable template
- **Per-campaign override** with `inherit:true|false` toggle (`PUT /api/lead-magnets/campaign/{id}`)
- Auto-send on ARIA ESCALATE (pre_booking) + Calendly invitee.created (post_booking)
- Channel auto-detected (email/whatsapp) from ARIA's most recent send
- LeadDetail "Pre-Call Brochure" card with manual Send + engagement (sends, opens, last opened, hot badge)
- **Dashboard "They opened your brochure!" alert** — shows recent opens with hot badges, click-through to lead
- **🔥 Hot strip on Lead Inbox rows** — leads who opened brochure get red→purple left strip + inline "Nx hot" badge
- Public tracking endpoint redirects + logs each open with timestamp
- Pydantic Literal validators on type/send_timing — invalid values rejected with 422

### Real Meta WhatsApp Cloud API (NEW)
- Outbound text send via Graph API v23.0 (`POST /{phone_number_id}/messages`)
- Webhook verify (`GET /api/webhooks/whatsapp` with hub.challenge echo) + receive (`POST /api/webhooks/whatsapp` for inbound replies)
- Inbound reply matched to lead by exact phone OR anchored last-10-digits regex
- Graceful **logged-only fallback** when WHATSAPP_ACCESS_TOKEN/PHONE_NUMBER_ID env empty
- Required env: `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_VERIFY_TOKEN` (placeholders in /app/backend/.env)

### Design
White + Purple (#7C35DC) theme, Plus Jakarta Sans, Sonner toasts (bottom-right, rich colors)

## Recent Changes
**Feb 28, 2026 (multi-iteration session)**
- Iter 9: TTV endpoint, Dashboard widget, Onboarding step 4 preview, /onboarding route
- Iter 10: TTV celebration toast hook + Sonner Toaster; Lead Magnet feature (config, upload, send, tracking, engagement); BACKEND_URL env added
- **Iter 11: Per-campaign override; Pydantic Literal validators; Dashboard brochure-opens alert; Lead Inbox 🔥 Hot strip; Real Meta WhatsApp Cloud API (send + webhook verify + receive); Hardened phone matching to anchored last-10**

## Test Status
- iteration_11.json: **36/36 backend tests passing (14 new + 22 regression) + 100% frontend flows verified**
- Test files: /app/backend/tests/test_ttv.py, test_lead_magnet.py

## Backlog
- P1: **Refactor server.py (~3666 lines) into modular routers** — auth, leads, ttv, onboarding, aria, billing, lead_magnet, whatsapp (deferred to focused session)
- P2: Materialize per-lead engagement summary if leads grow >10k (current aggregation is O(N) per dashboard load)
- P2: WhatsApp template messages (for proactive sends outside the 24h window)
- Production: Set actual `WHATSAPP_*` env values + add Calendly webhook verification signature

## Deployment: READY
Custom domain target: app.genleadai.com
