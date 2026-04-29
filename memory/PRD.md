# GenLeadAI — Full PRD

## Stack
FastAPI + React + MongoDB + Claude AI + Resend + Calendly + Stripe + Sonner + Meta WhatsApp Cloud API

## Product
**ARIA**: AI Sales Personal Assistant — captures, qualifies, scores, assigns, follows up, and tracks leads from multiple channels. Reduces lead leakage, improves follow-up discipline, gives founders/sales teams pipeline visibility.

## 4-Tier Plan Structure (NEW)
| Plan | Price | Audience | Highlights |
|------|-------|----------|-----------|
| **ARIA Starter** | $49/mo | Small teams | Manual lead control, follow-up reminders, Hot/Warm/Cold tagging |
| **ARIA Growth** | $149/mo | Campaign-driven biz | Multi-source capture, stage pipeline, basic AI scoring, founder summary |
| **ARIA Pro** | $399/mo | Founder-led companies | AI qualification, follow-up drafts, WhatsApp workflows, full CRM sync, RBAC |
| **ARIA Custom** | Contact Sales | Complex sales engines | Custom stages/scoring/workflows, AI call scheduling, multi-brand, dedicated support |

50 feature flags drive gating across all tiers.

## Sidebar Navigation (9 items)
Dashboard · Lead Inbox · Pipeline · Follow-Ups · AI Assistant · Reports · Integrations · Plan & Billing · Settings

## Pages
- **Dashboard**: Founder view with TTV widget, brochure-opens alert, ARIA Best Time to Call, ARIA daily plan, etc.
- **Lead Inbox**: Filters, search, hot strip, 25 demo leads (when seeded)
- **Lead Profile**: Pre-Call Brochure, Best Time to Call, activity timeline, engagement
- **Pipeline**: Kanban board (default 8 stages; custom stages = ARIA Custom only)
- **Follow-Ups**: 4 buckets (Due today / Overdue / Upcoming / Completed)
- **AI Assistant**: 8 tiles — qualification, scoring, drafts, NBA, lost-lead analysis, daily/weekly summaries
- **Reports**: Aliased to Analytics
- **Integrations**: 11 cards (Website, Meta, Google, LinkedIn, WhatsApp, Calendly, GCal, Email, Zoho, HubSpot, Sheets) with Connected/Available/Coming Soon/Request states
- **Plan & Billing**: 4 plan cards + 7-group feature comparison matrix
- **Settings**: ARIA agent (incl. Daily Call Plan), Lead Magnet, API & Forms, Asset Library, Workspace, Team

## Key Backend Endpoints (NEW in iter 14)
- `GET /api/billing/plans` — full 4-plan catalog with feature flags
- `GET /api/billing/current-plan` — current workspace plan + features
- `POST /api/billing/checkout` — Stripe checkout (rejects 'custom')
- `POST /api/billing/request-upgrade` — emails admin (UPGRADE_REQUEST_EMAIL env)
- `POST /api/admin/load-demo-data?force=` — seeds 25 industry-diverse demo leads
- `POST /api/dev/set-plan?plan_id=` — dev/admin plan switcher (admin-only)
- `require_feature('key')` — FastAPI dependency raising 402 with structured detail

## ARIA AI Modules (existing)
- 3-Phase Sales PA · Calendly auto-booking · Pre-call brochure (lead magnet) with engagement tracking · Best Time to Call · Daily Call Plan email · TTV milestones with celebration toasts

## Test Status
- iteration_14.json: **18/18 backend pytests + 16/16 frontend testids** after the 2 fixes (sidebar testid regex, LockBadge `<button>` → `<span role=button>` to eliminate React hydration warning)

## Phase 2 Plan (next session)
- C: Role-based dashboards (Founder/Manager/Rep/Marketing variants — Founder exists)
- D: Follow-Ups workflow page (mark complete, reschedule, type/channel selector)

## Phase 3 Plan
- E: AI Assistant unified UI tied to existing ARIA endpoints
- F: Integrations connection flows (Meta Ads, Google Ads OAuth)
- J: Reports polish (rep performance, lost-reason chart, time-in-stage)

## Backlog
- P1: server.py refactor (~4500 lines) into modular routers — overdue
- P1: `@app.on_event("startup")` → FastAPI lifespan handler (deprecation warning)
- P1: Real Stripe price IDs for Pro tier (currently uses amount-based checkout)
- P2: Customer Stripe webhook to auto-promote plan on payment.succeeded
- P2: `/api/billing/request-upgrade` to surface email_sent boolean

## Deployment: READY
Custom domain: app.genleadai.com
