# GenLeadAI Lead Management System — PRD

## Architecture
- **Frontend:** React + TailwindCSS + Recharts + react-beautiful-dnd
- **Backend:** FastAPI (Python) + MongoDB
- **AI:** Claude API via Emergent LLM Key
- **Email:** Resend API | **Calendar:** Calendly API v2 | **Storage:** Emergent Object Storage
- **Auth:** JWT + bcrypt | **Design:** White+Purple (#7C35DC) theme

## All Implemented Features (Feb 2026)

### Core LMS
- Auth (login/register/JWT), Lead CRUD with search/filters/pagination
- Pipeline Kanban (drag-drop, B2B/B2C), Campaign CRUD, Analytics (6 chart types)
- AI ICP scoring, summarization, email generation, chat assistant
- CSV import, Team management, Settings, 50 leads seed data

### ARIA AI Sales Agent
- Claude-powered conversation engine with state machine
- First touch + follow-up, reply processing, qualification
- Calendly integration (real booking), Object Storage (assets)
- Conversation panel, Control Panel, Live Feed, Analytics
- Human takeover/resume, handoff email alerts

### New Modules (Phase 3)
- [x] **Your 5 Today** — AI-ranked top 5 leads with reasons, actions, mark-done
- [x] **Sleeping Leads + Revival Engine** — 14+ days inactive, segment tabs, bulk revival campaign with 4 angles + channel picker
- [x] **No-Show Recovery** — 3-step follow-up with Calendly re-booking
- [x] **Referral Capture** — Auto-ask after Won status
- [x] **Intent Signals** — Email opens, link clicks with +10 score boosts
- [x] **Broadcast Personalizer** — Filter→Template→Preview→Send with {{tokens}}
- [x] **WhatsApp + Email dual channel** — Email real (Resend), WhatsApp simulated (pluggable)

### Design System
- White-first UI with purple gradient accents
- Plus Jakarta Sans / Inter / JetBrains Mono typography
- Full badge system, shadow-card effects, consistent color palette

## Backlog
### P0: Automated background scheduler for ARIA delayed touches
### P1: Daily Brief (morning WhatsApp+email), Score Decay engine, Sequence builder
### P2: Real WhatsApp Business API, WebSocket live feed, CSV/PDF export
