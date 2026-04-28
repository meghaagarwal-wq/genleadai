# GenLeadAI — Full PRD

## Stack
FastAPI + React + MongoDB + Claude AI + Resend + Calendly + Emergent Object Storage + Stripe

## Complete Feature Map

### Core LMS
Auth (JWT), Lead CRUD, Pipeline Kanban (B2B/B2C), Campaigns, Analytics (6 charts), Team, Settings

### ARIA 3-Phase Sales PA
- Phase 1: First touch, qualification, Calendly booking, pre-call research + briefing
- Phase 2: Call hold + outcome buttons (Interested/Proposal/Not Fit/More Time/Rescheduled)
- Phase 3: Post-call messages, 4-step proposal follow-up, reply handling, Won/Lost

### Advanced Modules
Your 5 Today, Sleeping Leads + Revival Engine, No-Show Recovery, Referral Capture, Intent Signals, Broadcast Personalizer

### Production Lead Ingestion
Public REST API (API key auth), Embeddable web form, Calendly webhook, Meta Lead Ads webhook, API key management

### Product-Ready
- [x] Onboarding Wizard — 5-step setup (Company → Founder → Calendar → ICP → Launch)
- [x] Mobile-Responsive UI — Hamburger menu, responsive grids, touch-friendly
- [x] Stripe Billing — 3 plans (Starter $49, Growth $149, Scale $399) with checkout
- [x] CSV Export — Leads, activities per lead, analytics report
- [x] Audit Log — Full activity trail with pagination
- [x] Role-based access control (Admin/Manager/Sales Rep/Viewer)
- [x] Time-to-Value Tracker — Live milestone widget on Dashboard + roadmap preview on Onboarding Wizard step 4
- [x] /onboarding route wired in App.js for direct access to wizard

### Design
White + Purple (#7C35DC) theme, Plus Jakarta Sans, shadow-card system

## Recent Changes (Feb 2026)
- Added GET /api/ttv/milestones endpoint (server.py:2972-3107) tracking 5 milestones: signup → first_lead → first_aria → first_meeting → first_won
- Dashboard.js renders TTV "Your Progress" timeline (data-testid="ttv-tracker")
- OnboardingWizard.js step 4 renders TTV roadmap preview (data-testid="onb-ttv-preview")
- App.js wired /onboarding standalone route
- Fixed time_diff_human to return null for negative durations (seed-vs-signup mismatch)

## Test Status
- iteration_9.json: 100% passing (8/8 backend, all frontend flows verified)
- Test file added: /app/backend/tests/test_ttv.py

## Backlog
- P1: Refactor server.py (~3100 lines) into modules: auth, leads, ttv, onboarding, aria, billing
- P2: Real WebSocket flows for live updates (currently simulated)
- P2: Cosmetic — hide empty "Company:"/"Founder:" labels when user uses Skip path
- Deployment to custom domain: app.genleadai.com (deployment_agent ready)

## Deployment: READY
