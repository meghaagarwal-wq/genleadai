# GenLeadAI — Full PRD

## Stack
FastAPI + React + MongoDB + Claude AI + Resend + Calendly + Emergent Object Storage + Stripe + Sonner

## Complete Feature Map

### Core LMS
Auth (JWT), Lead CRUD, Pipeline Kanban (B2B/B2C), Campaigns, Analytics (6 charts), Team, Settings

### ARIA 3-Phase Sales PA
- Phase 1: First touch, qualification, Calendly booking, pre-call research + briefing
- Phase 2: Call hold + outcome buttons
- Phase 3: Post-call messages, 4-step proposal follow-up, reply handling, Won/Lost

### Advanced Modules
Your 5 Today, Sleeping Leads + Revival Engine, No-Show Recovery, Referral Capture, Intent Signals, Broadcast Personalizer

### Production Lead Ingestion
Public REST API (API key auth), Embeddable web form, Calendly webhook, Meta Lead Ads webhook, API key management

### Product-Ready
- [x] Onboarding Wizard — 5-step setup with TTV roadmap preview
- [x] Mobile-Responsive UI
- [x] Stripe Billing — 3 plans
- [x] CSV Export, Audit Log, RBAC
- [x] Time-to-Value Tracker — Live milestone widget on Dashboard
- [x] **TTV Milestone Celebration Toast** — Sonner toaster fires share-worthy toast on milestone flip with copy-to-share button
- [x] **Pre-Call Lead Magnet** (NEW)
  - Settings → Lead Magnet tab: name, URL or PDF/PPTX upload (≤25MB), send timing (pre_booking | post_booking | both), customizable message template ({first_name}/{link}/{founder})
  - Auto-send hooked into ARIA ESCALATE (qualified) and Calendly invitee.created (booked)
  - Channel auto-detected from ARIA's most recent send to that lead (email/whatsapp)
  - LeadDetail "Pre-Call Brochure" card with manual Send button + engagement (sends, opens, last opened, hot badge)
  - Public tracking endpoint redirects + logs each open with timestamp
  - Backend tracking URL is absolute (BACKEND_URL env)

### Design
White + Purple (#7C35DC) theme, Plus Jakarta Sans, Sonner toasts (bottom-right, rich colors)

## Recent Changes
**Feb 28, 2026**
- Added GET /api/ttv/milestones endpoint, Dashboard widget, OnboardingWizard step 4 preview
- Wired /onboarding standalone route in App.js
**Feb 28, 2026 (cont.)**
- Added TTV milestone celebration toast (`/app/frontend/src/hooks/useTtvMilestoneWatcher.js`) + Sonner Toaster mounted globally in Layout
- Added Lead Magnet feature (~300 lines added to server.py: helper + 6 endpoints)
- Settings.js Lead Magnet tab; LeadDetail.js Pre-Call Brochure card with engagement tracking
- Auto-send hooks: ARIA ESCALATE (line ~979) for pre_booking; Calendly webhook (line ~2685) for post_booking
- Added BACKEND_URL to /app/backend/.env so tracking URLs are absolute

## Test Status
- iteration_10.json: 100% passing (14/14 backend, all frontend flows verified)
- New test file: /app/backend/tests/test_lead_magnet.py

## Backlog
- P1: Per-campaign lead magnet override (workspace default exists; campaign override is in PRD but not built)
- P1: Refactor server.py (~3416 lines) into modules: auth, leads, ttv, onboarding, aria, billing, lead_magnet
- P1: Real WhatsApp send (currently logs `whatsapp_sent` activity only)
- P2: Pydantic Literal validators for LeadMagnetConfig.type and send_timing
- P2: Real WebSocket flows for live updates
- Deployment to custom domain: app.genleadai.com (deployment_agent ready)

## Deployment: READY
