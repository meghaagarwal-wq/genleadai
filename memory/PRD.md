# GenLeadAI Lead Management System — PRD

## Architecture
- **Frontend:** React + TailwindCSS + Recharts + react-beautiful-dnd
- **Backend:** FastAPI (Python) + MongoDB
- **AI:** Claude API via Emergent LLM Key | **Email:** Resend API | **Calendar:** Calendly API v2 | **Storage:** Emergent Object Storage
- **Auth:** JWT + bcrypt | **Design:** White+Purple (#7C35DC)

## Complete Feature List (Feb 2026)

### Core LMS
- [x] Auth, Lead CRUD, Pipeline Kanban, Campaigns, Analytics, Team, Settings
- [x] AI ICP scoring, summarization, email generation
- [x] CSV import, 50 leads seed data

### ARIA AI Sales Agent → Sales PA (3-Phase)
**Phase 1 — Before the Call (Aria owns):**
- [x] First touch + follow-up generation
- [x] Reply processing with qualification + objection handling
- [x] Calendly meeting booking
- [x] Pre-call research engine (Claude AI inference)
- [x] Pre-call brief generation (email to founder)
- [x] Pre-call lead reminder

**Phase 2 — The Call (Founder owns):**
- [x] ON_HOLD_DURING_CALL state (Aria paused)
- [x] Post-call outcome buttons: Interested, Sending Proposal, Not a Fit, Needs More Time, Rescheduled
- [x] Automatic Phase 3 trigger based on outcome

**Phase 3 — After Call + Proposal (Aria owns):**
- [x] Post-call warm message to lead
- [x] Mark Proposal Sent workflow
- [x] 4-step proposal follow-up sequence (48h, 4d, 7d, 14d)
- [x] Reply handling with value reframing (never discount)
- [x] Complex question escalation to founder
- [x] Won/Lost detection and appropriate responses

**Founder Controls:**
- [x] Take Over / Hand Back to Aria
- [x] Private instructions (partial override)
- [x] Weekly sales summary (email)
- [x] Phase indicator on conversation panel

### New Modules
- [x] Your 5 Today (AI daily picks with weighted ranking)
- [x] Sleeping Leads + Revival Engine (bulk revival with 4 angles)
- [x] No-Show Recovery (3-step)
- [x] Referral Capture
- [x] Intent Signals with score boosts
- [x] Broadcast Personalizer (filter → template → preview → send)
- [x] WhatsApp + Email dual channel (Email real, WhatsApp pluggable)

### Design
- [x] White+Purple theme throughout all pages
- [x] Plus Jakarta Sans / Inter / JetBrains Mono typography

## Backlog
### P0: Automated background scheduler, Score Decay engine
### P1: Daily Brief via WhatsApp, Sequence builder, Real WhatsApp API
### P2: WebSocket live feed, CSV/PDF export, Notification center
