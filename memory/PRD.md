# GenLeadAI Lead Management System — PRD

## Architecture
- **Frontend:** React + TailwindCSS + Recharts + react-beautiful-dnd
- **Backend:** FastAPI (Python) + MongoDB
- **AI:** Claude API via Emergent LLM Key | **Email:** Resend API | **Calendar:** Calendly API v2 | **Storage:** Emergent Object Storage
- **Auth:** JWT + bcrypt | **Design:** White+Purple (#7C35DC)

## Complete Feature List

### Core LMS
- Auth, Lead CRUD, Pipeline Kanban, Campaigns, Analytics, Team, Settings
- AI ICP scoring, summarization, email generation, CSV import

### ARIA 3-Phase Sales PA
- Phase 1: First touch, qualification, Calendly booking, pre-call research + briefing
- Phase 2: Call hold + 5 outcome buttons (Interested/Proposal/Not Fit/More Time/Rescheduled)
- Phase 3: Post-call messages, proposal follow-up (4-step), reply handling, Won/Lost detection
- Founder Override: Take over, hand back, private instructions, weekly summary

### Advanced Modules
- Your 5 Today (AI daily picks), Sleeping Leads + Revival Engine
- No-Show Recovery, Referral Capture, Intent Signals, Broadcast Personalizer

### Production Lead Ingestion (NEW)
- [x] Public REST API: POST /api/v1/leads with API key auth
- [x] Embeddable web form: POST /api/form/submit (no auth, UTM auto-capture)
- [x] Embed code generator with GenLeadAI-branded form
- [x] API key management (create, list, revoke)
- [x] Calendly webhook receiver (auto-creates leads on booking)
- [x] Meta Lead Ads webhook receiver (Facebook/Instagram)
- [x] Lead deduplication on email (all endpoints)
- [x] Auto-link campaigns by UTM params
- [x] Settings > API & Forms tab with keys, embed code, webhook URLs

### To make emails universal
- Verify genleadai.com domain in Resend → update SENDER_EMAIL to aria@genleadai.com

## Deployment: READY
- Deployment health check: PASS
- Custom domain: app.genleadai.com ready to link
