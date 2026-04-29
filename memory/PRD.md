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
- **AriaInsightCard**: dark gradient "ARIA SAYS · 🟢 ONLINE" callout with 48px animated robot avatar, pulse glow
- **AriaAvatar component**: custom SVG robot face — halo pulse, eye blink, antenna LED twinkle
- **Tokens**: --sidebar-bg, --sidebar-active-border (#C044E0 3px left), --shadow-card, --gradient-brand
- **Language**: AI Sales PA / lead leakage / follow-up discipline / revenue movement / command center / next best action

## Sidebar Navigation (9 items)
Dashboard · Lead Inbox · Pipeline · Follow-Ups · AI Assistant · Reports · Integrations · Plan & Billing · Settings

## Pages
- **Dashboard** — "ARIA Command Center" with dynamic ARIA Daily Brief, TTV widget, brochure-opens alert, Best Time to Call
- **Lead Inbox** — Hot strip, filters, search, 25 demo leads
- **Lead Profile** — Pre-Call Brochure card, Best Time to Call, activity timeline
- **Pipeline** — Kanban (8 stages; custom stages = Custom plan); now shows Active Pipeline total + per-stage value totals + per-card deal-value chips (iter 18)
- **Follow-Ups** — "Follow-Up Command Center" with ARIA Priority Queue insight, 4 buckets, inline +1d/+3d/Done actions per row (iter 18)
- **AI Assistant** — "ARIA AI Assistant" with 8 gated tiles
- **Reports** (alias of Analytics)
- **Integrations** — "Connect ARIA With Your Growth Stack", 11 cards
- **Plan & Billing** — "Choose your sales operating layer", 4 plan cards + 7-group feature matrix
- **Settings** — ARIA agent, Daily Call Plan email, End-of-Day Wrap email (iter 18), Lead Magnet, API & Forms, Workspace, Team

## Scheduled Emails (ARIA cron loops, 60s tick)
- **Daily Call Plan** — 8 AM local, top-N leads to call today, sorted by call_score
- **End-of-Day Wrap** — 6 PM local, today's activity summary: calls/emails/WA sent, wins, losses, hot leads still untouched, tomorrow's top 3, momentum tag (strong/steady/quiet)

## Test Status
- iteration_18.json: 11/11 backend pytest pass for EOD module + regressions. Frontend: Settings EOD panel 100%, Pipeline value totals 100%, FollowUps reschedule 100%, Done button initially blocked by PATCH null bug → **FIXED in iter 18 final** (server.py:381 now uses `exclude_unset=True`). Curl-verified end-to-end.

## Last Shipped (iter 18)
1. **End-of-Day Wrap email** — `eod_wrap_collection`, EndOfDayWrapConfig, _compute_eod_wrap, _render_eod_wrap_html, _send_eod_wrap, GET/PUT/POST/preview endpoints, _eod_wrap_loop background task, startup hook. Settings UI panel below Daily Call Plan.
2. **Pipeline value totals** — Active pipeline chip (header), per-stage value totals in column headers, per-card deal-value chips. fmtInr / stageValue / totalPipelineValue helpers.
3. **Follow-Up inline actions** — markComplete (POST activity + PATCH next_followup_at:null) and reschedule(+1d/+3d) inline buttons. Outer row converted from `<button>` to `<div role="button">` for valid HTML nesting.
4. **CRITICAL bug fix** — PATCH /api/leads/{id} now uses `lead_update.dict(exclude_unset=True)` instead of dropping null values. Lets callers explicitly clear fields (used by Mark Complete flow).

## Phase 2 (Next session)
- Role-based dashboards: Sales Manager view + Sales Rep view
- Lead Profile two-column layout with ARIA Suggestions card
- Mobile drawer/responsive table-to-card transformations
- Generate Message action on Follow-Up rows (currently only +1d/+3d/Done)

## Phase 3
- AI Assistant unified UI (qualification, drafts, NBA, lost-lead analysis) wired to existing ARIA Claude endpoints
- Integrations OAuth flows (Meta Ads, Google Ads, LinkedIn)
- Reports polish (rep performance, lost-reason chart, time-in-stage, avg time to first follow-up)

## Backlog
- P1: server.py refactor (~5100 lines) into modular routers (still pending)
- P1: `@app.on_event("startup")` → FastAPI lifespan handler
- P1: Real Stripe price IDs for Pro tier
- P2: Customer Stripe webhook to auto-promote plan on `payment.succeeded`
- P2: DRY `EmailScheduleCard` component shared by Daily Call Plan + EOD Wrap (currently ~140 lines duplicate JSX in Settings.js)
- P2: Single-endpoint POST /api/leads/{id}/complete-followup (atomic activity + status clear; currently FE makes 2 calls)
- P2: Pre-existing react-beautiful-dnd `isDropDisabled` dev warning on Pipeline page
- Production: Set `WHATSAPP_*` env values; verify Resend domain

## Deployment: READY
Custom domain target: app.genleadai.com
