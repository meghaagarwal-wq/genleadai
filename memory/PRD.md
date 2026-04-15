# GenLeadAI Lead Management System — PRD

## Original Problem Statement
Build a full-stack Lead Management System (LMS) for a growth marketing agency that handles both B2B and B2C leads across multiple acquisition channels. Extended with ARIA — an autonomous AI Sales Agent. White+purple design overhaul applied.

## Architecture
- **Frontend:** React + TailwindCSS + shadcn/ui + Recharts + react-beautiful-dnd
- **Backend:** FastAPI (Python)
- **Database:** MongoDB
- **AI:** Claude API via Emergent LLM Key (claude-4-sonnet-20250514)
- **Email:** Resend API (re_jCACp6PS...)
- **Calendar:** Calendly API v2 (PAT auth, Megha Agarwal's account)
- **Storage:** Emergent Object Storage
- **Auth:** JWT-based with bcrypt password hashing

## Design System (Implemented Feb 2026)
- **Theme:** White-first UI with purple (#7C35DC) as dominant accent
- **Background:** #FAFAFA (page) / #FFFFFF (cards)
- **Borders:** #E8E0F5 (standard) / #F0ECF9 (subtle)
- **Text:** #1A0A2E (primary) / #5A4A7A (secondary) / #9B8AB0 (muted)
- **Gradient:** linear-gradient(135deg, #C044E0, #7C35DC, #5B28D4)
- **Typography:** Plus Jakarta Sans (headings), Inter (body), JetBrains Mono (code)
- **Shadows:** Purple-tinted card shadows and hover effects

## What's Been Implemented

### Phase 1 — Core LMS
- [x] Auth (login, register, JWT)
- [x] Lead CRUD with search, filters, pagination
- [x] Lead detail with ICP score, activity timeline
- [x] Pipeline Kanban (drag-drop, B2B/B2C)
- [x] Campaign CRUD with metrics
- [x] Analytics (6 chart types)
- [x] Team management, Settings
- [x] AI ICP scoring, summarization, email generation
- [x] CSV import, Resend email
- [x] 50 leads, 3 campaigns, 3 users seed data

### Phase 2 — ARIA AI Sales Agent
- [x] Claude-powered conversation engine
- [x] State machine (PENDING→AWAITING→ACTIVE→BOOKED/DNC)
- [x] First touch + follow-up generation
- [x] Reply processing with qualification
- [x] Calendly integration (real booking links)
- [x] Object Storage for brand deck/portfolio
- [x] Conversation panel on Lead Detail
- [x] ARIA Control Panel in Settings
- [x] Asset Library with upload/toggle
- [x] Live Feed page + Analytics
- [x] Human takeover/resume
- [x] Handoff email alerts

### Phase 3 — White + Purple Design Overhaul
- [x] Complete redesign from dark mode to white+purple
- [x] All pages: Login, Register, Dashboard, LeadInbox, LeadDetail, Pipeline, Campaigns, Analytics, AriaFeed, AriaAnalytics, Settings
- [x] Layout: White sidebar with purple active states
- [x] Plus Jakarta Sans + Inter + JetBrains Mono fonts
- [x] Purple gradient buttons, ICP gauges, chart palettes
- [x] Consistent shadow-card and shadow-hover effects
- [x] Badge system: hot (purple), warm (amber), cold (slate)

## Prioritized Backlog

### P0 (Next Sprint)
- Your 5 Today page (AI daily picks)
- Sleeping Leads + Revival Engine
- No-Show Recovery flow
- Referral Capture
- Automated background scheduler for ARIA touches

### P1
- Daily Brief (WhatsApp + email morning briefing)
- Intent Signals tracking + score boosts
- Score Decay rules engine
- Bulk Personalization Engine (CSV import → AI personalize → send)
- WhatsApp Broadcast Personalizer

### P2
- Sequence builder with conditional branching
- WebSocket real-time feed
- CSV/PDF export
- WhatsApp Business API real integration
- Notification center

## Next Tasks
1. Build "Your 5 Today" page with AI ranking algorithm
2. Build Sleeping Leads page with Revival Campaign launcher
3. Implement No-Show Recovery flow (Calendly webhook integration)
4. Add Referral Capture (auto-trigger after Won status)
5. Implement automated background scheduler for ARIA delayed touches
