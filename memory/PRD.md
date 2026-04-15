# GenLeadAI Lead Management System — PRD

## Original Problem Statement
Build a full-stack Lead Management System (LMS) for a growth marketing agency that handles both B2B and B2C leads across multiple acquisition channels. Production-grade application.

## Architecture
- **Frontend:** React + TailwindCSS + shadcn/ui + Recharts
- **Backend:** FastAPI (Python) 
- **Database:** MongoDB
- **AI:** Claude API via Emergent LLM Key (claude-4-sonnet-20250514)
- **Email:** Resend API
- **Auth:** JWT-based with bcrypt password hashing

## User Personas
- **Admin (Megha):** Full access, manages workspace, campaigns, team
- **Sales Rep (Sarah, James):** Manages assigned leads, logs activities
- **Viewer:** Read-only access to dashboard and reports

## Core Requirements (Static)
1. Lead CRUD with B2B/B2C types and multi-channel acquisition tracking
2. AI-powered ICP scoring (0-100, hot/warm/cold tiers)
3. Pipeline Kanban boards with drag-and-drop
4. Campaign management with metrics
5. Analytics dashboard with charts
6. Team management with RBAC
7. Activity timeline per lead
8. Email integration via Resend

## What's Been Implemented (Feb 2026)
- [x] Auth system (login, register, JWT tokens)
- [x] Complete lead CRUD with search, filters, pagination
- [x] Lead detail page with profile, ICP score, activity timeline
- [x] Pipeline Kanban with drag-and-drop (B2B/B2C toggle)
- [x] Campaign CRUD with metrics
- [x] Analytics dashboard (channel, funnel, pie charts, status distribution)
- [x] Team management page
- [x] Settings page with workspace config
- [x] AI ICP scoring via Claude API
- [x] AI lead summarization
- [x] AI email copy generation
- [x] AI chat assistant
- [x] CSV lead import
- [x] Email sending via Resend
- [x] Seed data (50 leads, 3 campaigns, 3 users, 120 activities)
- [x] Dark mode enterprise SaaS design

## Prioritized Backlog

### P0 (Next Sprint)
- Real-time live feed via WebSocket
- Lead deduplication on email + phone
- Sequence builder with multi-step drip campaigns

### P1
- CSV/Excel export functionality
- PDF report generation
- Notification center (in-app + email)
- Lead assignment rules (round-robin, capacity caps)
- Embeddable web form generator

### P2
- WhatsApp webhook receiver
- Email thread viewer
- Custom fields builder
- Pipeline stage editor
- Score history chart
- Daily digest email
- Saved filter presets
- Bulk actions (assign, tag, status change)

## Next Tasks
1. Add WebSocket for real-time lead feed
2. Build sequence builder with conditional branching
3. Implement notification center
4. Add CSV/PDF export
5. Build embeddable form generator
