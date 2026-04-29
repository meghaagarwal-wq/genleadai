# GenLeadAI — Full PRD

## Stack
FastAPI + React + MongoDB + Claude AI + Resend + Calendly + Stripe + Sonner + Meta WhatsApp Cloud API

## Product
**ARIA**: AI Sales Personal Assistant — captures, qualifies, scores, assigns, follows up, and tracks every lead from one command center. Reduces lead leakage, enforces follow-up discipline, gives founders/sales teams pipeline visibility.

## 4-Tier Plan Structure
| Plan | Price | Audience | Highlights |
|------|-------|----------|-----------|
| **ARIA Starter** | $49/mo | Small teams | Manual lead control, follow-up reminders, Hot/Warm/Cold tagging |
| **ARIA Growth** | $149/mo | Campaign-driven biz | Multi-source capture, stage pipeline, basic AI scoring, founder summary |
| **ARIA Pro** | $399/mo | Founder-led companies | AI qualification, follow-up drafts, WhatsApp workflows, full CRM sync, RBAC |
| **ARIA Custom** | Contact Sales | Complex sales engines | Custom stages/scoring/workflows, AI call scheduling, multi-brand, dedicated support |

50 feature flags drive gating across all tiers via `_has_feature` + `require_feature` dependency.

## ARIA Brand Visual System
- **Dark premium sidebar** (`linear-gradient(180deg, #0E0820 → #1A0F38)`) with brand block "ARIA / AI SALES PA · GENLEADAI" and animated ARIA robot avatar
- **Premium top bar**: search "Search leads, follow-ups, campaigns…", AI Summary button, gradient "+ Add Lead" CTA, notifications bell with red dot
- **PageHeader component**: eyebrow (purple uppercase) + 36px h1 + 16px subtitle + actions slot
- **AriaInsightCard**: dark gradient "ARIA SAYS · 🟢 ONLINE" callout with 48px animated robot avatar, pulse glow, dynamic message + CTA. Urgent tone speeds pulse to 2.4s and shifts halo to coral.
- **AriaAvatar component (NEW iter 16)**: custom SVG robot face with idle animations — halo pulse, eye blink, antenna LED twinkle, head breathing. Three tones: default (purple), urgent (coral), soft (lilac). Reusable at any size.
- **Tokens**: --sidebar-bg, --sidebar-active-border (#C044E0 3px left), --shadow-card, --gradient-brand
- **Language**: replaced generic CRM terms with AI Sales PA / lead leakage / follow-up discipline / revenue movement / command center / next best action

## Sidebar Navigation (9 items)
Dashboard · Lead Inbox · Pipeline · Follow-Ups · AI Assistant · Reports · Integrations · Plan & Billing · Settings

## Pages (with new ARIA brand language)
- **Dashboard** — "ARIA Command Center" with dynamic ARIA Daily Brief, TTV widget, brochure-opens alert, Best Time to Call
- **Lead Inbox** — Hot strip, filters, search, 25 demo leads
- **Lead Profile** — Pre-Call Brochure card, Best Time to Call, activity timeline
- **Pipeline** — Kanban (8 stages; custom stages = Custom plan)
- **Follow-Ups** — "Follow-Up Command Center" with ARIA Priority Queue insight, 4 buckets
- **AI Assistant** — "ARIA AI Assistant" with 8 gated tiles
- **Reports** (alias of Analytics)
- **Integrations** — "Connect ARIA With Your Growth Stack", 11 cards
- **Plan & Billing** — "Choose your sales operating layer", 4 plan cards + 7-group feature matrix
- **Settings** — ARIA agent (Daily Call Plan), Lead Magnet, API & Forms, Workspace, Team

## Test Status
- iteration_15.json: **100% pass** (9/9 backend smoke + 9/9 frontend routes, zero console errors, zero regressions). Pre-existing react-beautiful-dnd dev warning noted as non-blocking.

## Phase 2 (Next session)
- Role-based dashboards: Sales Manager view (team ownership, rep activity, lost reasons, conversion by source) + Sales Rep view (my leads, follow-ups due today, hot leads assigned, calls scheduled)
- Follow-Ups workflow: Mark Complete + Reschedule + Generate Message + Type/channel selector
- Lead Profile two-column layout with ARIA Suggestions card
- Pipeline rebuild with deal-value totals per stage
- Mobile drawer/responsive table-to-card transformations

## Phase 3
- AI Assistant unified UI (qualification, drafts, NBA, lost-lead analysis) wired to existing ARIA Claude endpoints
- Integrations OAuth flows (Meta Ads, Google Ads, LinkedIn)
- Reports polish (rep performance, lost-reason chart, time-in-stage, avg time to first follow-up)

## Backlog
- P1: server.py refactor (~4500 lines) into modular routers
- P1: `@app.on_event("startup")` → FastAPI lifespan handler
- P1: Real Stripe price IDs for Pro tier
- P2: Customer Stripe webhook to auto-promote plan on `payment.succeeded`
- P2: Pre-existing react-beautiful-dnd `isDropDisabled` dev warning on Pipeline page
- Production: Set `WHATSAPP_*` env values; verify Resend domain

## Deployment: READY
Custom domain target: app.genleadai.com
