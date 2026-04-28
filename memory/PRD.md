# GenLeadAI — Full PRD

## Stack
FastAPI + React + MongoDB + Claude AI + Resend + Calendly + Stripe + Sonner + Meta WhatsApp Cloud API

## Complete Feature Map

### Core LMS
Auth (JWT), Lead CRUD, Pipeline Kanban, Campaigns, Analytics, Team, Settings, RBAC

### ARIA 3-Phase Sales PA
Phase 1 → Calendly + briefing; Phase 2 → outcome buttons; Phase 3 → follow-ups, Won/Lost

### Advanced Modules
Your 5 Today, Sleeping Leads + Revival, No-Show Recovery, Referral Capture, Intent Signals, Broadcast Personalizer

### Production Lead Ingestion
Public REST API, Embed form, Calendly webhook, Meta Lead Ads webhook, WhatsApp webhook (verify + receive)

### Time-to-Value
- Live milestone widget on Dashboard, Onboarding step 4 preview, milestone celebration toasts (Sonner)

### Pre-Call Lead Magnet (FULL)
- Workspace + per-campaign override config; URL or PDF/PPTX upload
- Auto-send on ARIA ESCALATE + Calendly booked; channel auto-detected
- LeadDetail Pre-Call Brochure card; Dashboard "They opened" alert; 🔥 Lead Inbox hot strip
- Public tracking redirect + view logging; Pydantic Literal validators

### Real Meta WhatsApp Cloud API
- Outbound text via Graph API v23.0; webhook verify + receive
- Lead matched by exact phone or anchored last-10 regex
- Graceful logged-only fallback when env empty

### ARIA's Best Time to Call
- 2 endpoints: `/api/aria/best-time-to-call/{lead_id}` + `/api/aria/call-priority?limit=N`
- call_score 0-100 from brochure-open + timezone + active hours + ICP
- Dashboard widget (top-N with tel: Call buttons) + LeadDetail card

### ARIA Daily Call Plan Email (NEW — iter 13)
- Background asyncio loop (60s tick) sends a daily email to the founder with the top N leads to call today
- Endpoints: `GET/PUT /api/aria/daily-call-plan/config`, `POST /api/aria/daily-call-plan/send-now`, `GET /api/aria/daily-call-plan/preview`
- Settings → ARIA Agent → Daily Call Plan panel (toggle, recipient, hour, UTC offset, plan size)
- Beautiful HTML email with urgency badges (CALL NOW/SOON/LATER), ICP chip, reasons, tel: links per lead
- Idempotency via `last_sent_date`; fractional-UTC-offset-correct (5-min fire window keyed off minute-of-day-UTC)
- Pydantic field validators (hour 0-23, tz -12..14, plan_size 1-10)

### Design
White + Purple (#7C35DC), Plus Jakarta Sans, Sonner toasts

## Recent Changes
- Iter 9-10: TTV + celebration toasts + Lead Magnet
- Iter 11: Per-campaign override + Literal validators + Dashboard alert + 🔥 Lead Inbox + WhatsApp Cloud API
- Iter 12: Best Time to Call (Dashboard widget + LeadDetail card)
- **Iter 13: Daily Call Plan Email — full feature, 13/13 backend tests + 100% frontend, fractional-UTC offset bug fixed post-test**

## Test Status
iteration_13.json: 13/13 backend pytests + 100% frontend; cumulative 80+/80+ tests across iterations.

## Backlog
- P1: Refactor server.py (~4100 lines) into modular routers — overdue, deferred to dedicated session
- P1: Migrate `@app.on_event("startup")` to FastAPI lifespan handler (deprecated)
- P2: Daily plan visual theme — match dark cards in ARIA Agent tab
- P2: Multi-workspace support (current single-tenant assumption documented)
- P2: Friendly error mapping for Resend free-tier verbatim error
- Production: Set `WHATSAPP_*` env values; verify Resend domain to remove free-tier recipient restriction

## Deployment: READY
Custom domain target: app.genleadai.com
