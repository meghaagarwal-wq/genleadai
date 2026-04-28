# GenLeadAI — Full PRD

## Stack
FastAPI + React + MongoDB + Claude AI + Resend + Calendly + Emergent Object Storage + Stripe + Sonner + Meta WhatsApp Cloud API

## Complete Feature Map

### Core LMS
Auth (JWT), Lead CRUD, Pipeline Kanban (B2B/B2C), Campaigns, Analytics (6 charts), Team, Settings, RBAC

### ARIA 3-Phase Sales PA
Phase 1: First touch + qualification + Calendly + briefing
Phase 2: Call hold + outcome buttons
Phase 3: Post-call follow-ups, Won/Lost

### Advanced Modules
Your 5 Today, Sleeping Leads + Revival, No-Show Recovery, Referral Capture, Intent Signals, Broadcast Personalizer

### Production Lead Ingestion
Public REST API, Embeddable web form, Calendly webhook, Meta Lead Ads webhook, WhatsApp webhook (verify + receive)

### Time-to-Value
- Live milestone widget on Dashboard, Onboarding step 4 preview, milestone celebration toasts (Sonner)

### Pre-Call Lead Magnet (FULL)
- Workspace config + per-campaign override (`inherit:true|false`)
- URL OR PDF/PPTX upload, send timing, customizable template
- Auto-send on ARIA ESCALATE + Calendly booked
- Channel auto-detected (email/whatsapp)
- LeadDetail Pre-Call Brochure card with Send + engagement
- Dashboard "They opened your brochure!" alert
- 🔥 Hot strip on Lead Inbox rows
- Public tracking redirect + view logging
- Pydantic Literal validators

### Real Meta WhatsApp Cloud API
- Outbound text via Graph API v23.0
- Webhook verify + receive, lead matched by exact phone or anchored last-10-digits regex
- Graceful logged-only fallback when env empty

### ARIA's Best Time to Call (NEW — iter 12)
- 2 endpoints:
  - `GET /api/aria/best-time-to-call/{lead_id}` — for LeadDetail
  - `GET /api/aria/call-priority?limit=N` — top leads ready right now, for Dashboard
- Combines: brochure-open recency (≤30m=+60, ≤4h=+30) + lead timezone (country or phone-code) + active hours window (from reply heatmap or 10am-4pm default) + ICP boost (hot=+20, warm=+10)
- Output: call_score 0-100, urgency (now/soon/later), suggested_action, reasons[], lead_local_hour, active_window
- Dashboard widget: top 3 leads with CALL NOW chip + tel: link
- LeadDetail card: full breakdown + Call {first_name} button when urgency=now

### Design
White + Purple (#7C35DC), Plus Jakarta Sans, Sonner toasts

## Recent Changes
- Iter 9: TTV endpoint, Dashboard widget, /onboarding route
- Iter 10: TTV celebration toast hook + Sonner Toaster, Lead Magnet, BACKEND_URL env
- Iter 11: Per-campaign override, Literal validators, Dashboard brochure-opens alert, Lead Inbox hot strip, Real WhatsApp Cloud API
- **Iter 12: ARIA's Best Time to Call (Dashboard widget + LeadDetail card + 2 endpoints, 14/14 backend tests, weight tuning so hot-ICP leads in-window reach 'soon')**

## Test Status
- iteration_12.json: 14/14 backend + 100% frontend; cumulative 50+/50+ tests across 4 iterations.

## Backlog
- P1: Refactor server.py (~3915 lines) into modular routers — deferred to dedicated session
- P2: Materialize per-lead engagement summary if leads grow >10k
- P2: WhatsApp template messages (proactive sends outside 24h window)
- P2: Allow founder to override the active-hours window per workspace (currently 10am-4pm default)
- Production: Set actual `WHATSAPP_*` env values + Calendly webhook signature verification

## Deployment: READY
Custom domain target: app.genleadai.com
