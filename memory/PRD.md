# GenLeadAI Lead Management System — PRD

## Original Problem Statement
Build a full-stack Lead Management System (LMS) for a growth marketing agency that handles both B2B and B2C leads across multiple acquisition channels. Extended with ARIA — an autonomous AI Sales Agent that qualifies leads, handles objections, and books Calendly meetings.

## Architecture
- **Frontend:** React + TailwindCSS + shadcn/ui + Recharts
- **Backend:** FastAPI (Python)
- **Database:** MongoDB
- **AI:** Claude API via Emergent LLM Key (claude-4-sonnet-20250514)
- **Email:** Resend API
- **Calendar:** Calendly API v2 (PAT auth)
- **Storage:** Emergent Object Storage
- **Auth:** JWT-based with bcrypt password hashing

## User Personas
- **Admin (Megha):** Full access, manages workspace, ARIA settings, campaigns, team
- **Sales Rep (Sarah, James):** Manages assigned leads, logs activities, monitors ARIA
- **Viewer:** Read-only access to dashboard and reports

## What's Been Implemented (Feb 2026)

### Phase 1 — Core LMS
- [x] Auth system (login, register, JWT tokens)
- [x] Complete lead CRUD with search, filters, pagination
- [x] Lead detail page with profile, ICP score, activity timeline
- [x] Pipeline Kanban with drag-and-drop (B2B/B2C toggle)
- [x] Campaign CRUD with metrics
- [x] Analytics dashboard (channel, funnel, pie charts, status distribution)
- [x] Team management page
- [x] Settings page with workspace config
- [x] AI ICP scoring, summarization, email generation, chat assistant
- [x] CSV lead import
- [x] Email sending via Resend
- [x] Seed data (50 leads, 3 campaigns, 3 users, 120 activities)

### Phase 2 — ARIA AI Sales Agent
- [x] ARIA agent engine (Claude-powered conversational AI)
- [x] Conversation state machine (PENDING → AWAITING → ACTIVE → BOOKED/ESCALATED/DNC)
- [x] First touch generation (personalized, warm messages)
- [x] Follow-up generation (different angle, value-add)
- [x] Reply processing (qualification, objection handling)
- [x] Action execution (send email, update status, book meeting, escalate, DNC)
- [x] Calendly integration (fetch event types, availability, create scheduling links)
- [x] Emergent Object Storage for asset uploads (brand deck, portfolio)
- [x] ARIA conversation panel on Lead Detail page
- [x] ARIA Control Panel in Settings (persona, timing, founder config)
- [x] Asset Library with upload, toggle first-touch, soft-delete
- [x] ARIA Live Feed page with active conversation threads
- [x] ARIA Analytics page with conversion funnel, state distribution
- [x] Human takeover / resume ARIA functionality
- [x] Handoff email alerts to founder via Resend

## Prioritized Backlog

### P0 (Next Sprint)
- Automated background job scheduler (cron-like) for delayed first touch and follow-ups
- WebSocket real-time updates for ARIA feed
- Sequence builder with conditional branching

### P1
- Slack webhook integration for handoff alerts
- CSV/PDF export
- Notification center (in-app + email)
- Lead assignment rules (round-robin)
- Embeddable web form generator

### P2
- WhatsApp Business API real integration (360dialog/Twilio)
- Email thread viewer
- Custom fields builder
- Score history chart
- Daily digest email
- Saved filter presets

## Next Tasks
1. Implement background scheduler for automated ARIA touches
2. Add WebSocket for real-time ARIA feed updates
3. Build sequence builder with conditional branching
4. Add Slack webhook for handoff notifications
5. Implement CSV/PDF export functionality
