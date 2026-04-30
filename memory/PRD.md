# GenLeadAI — Full PRD

## Stack
FastAPI + React + MongoDB + Claude AI + Resend + Calendly + Stripe + Sonner + Meta WhatsApp Cloud API

## Product
**ARIA**: Hyper-personalised **AI sales agent** for startups, founder-led businesses, SaaS companies, agencies, consultants, and service businesses that cannot yet hire a full sales/lead-management/follow-up/call-booking team.

## Brand promise
- "Deploy your first AI sales hire before building a sales team."
- "Your CRM stores leads. ARIA works them."

## Positioning
ARIA is **not** a CRM, **not** a chatbot, **not** an automation dashboard. It's an AI sales hire that captures, qualifies, nurtures, books calls, prepares founder briefs, follows up post-call, revives silent leads, and only escalates to humans when needed.

## Existing app (preserved as-is)
- Sidebar nav (9 items): Dashboard, Lead Inbox, Pipeline, Follow-Ups, AI Assistant, Reports, Integrations, Plan & Billing, Settings
- Dashboard with ARIA Daily Brief, ARIA Today widget, Founder Command Center (revenue leakage / money at risk / hot untouched / proposal graveyard / source quality / lost reasons), TTV tracking, Daily Call Plan email, End-of-Day Wrap email
- 4-tier plan structure (Starter / Growth / Pro / Custom) with feature gating
- Brand: dark sidebar, ARIA robot avatar, Plus Jakarta Sans, purple/violet gradient
- Lead Inbox with Hot strip, Pipeline kanban with deal-value totals, Follow-Ups with inline +1d/+3d/Done actions
- Calendly + Resend + Meta WhatsApp Cloud API integrations

## ADDITIVE — AI Sales Agent layer (iter 19–20)
### New backend module: `/app/backend/aria_agent_routes.py`
14 new endpoints under `/api/aria-agent/*`:
- `GET/PUT /training` — full Train ARIA wizard data
- `GET /playbooks` + `POST /playbooks/{id}/activate` + `/deactivate`
- `GET /journeys/default` — 17-step default journey + 5 templates + max=26 touchpoints
- `POST /founder-brief/{lead_id}` — **Claude 4 Sonnet powered** via Emergent LLM Key. Uses lead profile + recent activity history + workspace training context to generate `recommended_pitch`, `suggested_opening`, `questions_to_ask`, `aria_recommendation`. Falls back to heuristic on Claude error. Returns `ai_powered: true|false`. ~10–12 sec generation time.
- `GET /aria-read/{lead_id}` — conversation intelligence (temperature/intent/urgency/fit/need/pain/objection/next-action/suggested-response/handoff-needed/aria-thinks)
- `GET /handoff/rules` + `/handoff/alerts`
- `GET /revival/segments` (7 segments + Day 1/4/9/15/30 default journey)
- `GET /agent-activity` — 6 KPIs for Dashboard activity section
- `GET /insights` — 8 headline insights + 4 recommendations + live observation

### New sidebar section "AI SALES AGENT" (additive, below existing 9 items)
- Train ARIA `/aria-agent/train`
- Sales Playbooks `/aria-agent/playbooks`
- Sales Journeys `/aria-agent/journeys`
- Founder Briefs `/aria-agent/briefs`
- Human Handoff `/aria-agent/handoff`
- Revival Engine `/aria-agent/revival`
- ARIA Insights `/aria-agent/insights`

### Dashboard additions
- Positioning banner: "ARIA · YOUR FIRST AI SALES HIRE — Your CRM stores leads. ARIA works them."
- ARIA Sales Agent Activity card with 6 tiles (responded today, qualified, follow-ups sent, calls booked, hot escalated, silent revived)
- Mounted between AriaTodayWidget and FounderCommandCenter — nothing pre-existing removed

### LeadDetail additions
- `<AriaReadPanel>` in left column above Lead Magnet card — purple gradient header, status badges, ARIA thinks block, 4 KV intelligence fields, suggested response with copy button, Generate Founder Brief button → opens modal with full brief

## Test Status
- iteration_19.json: 100% pass — 13 backend endpoints + all 7 new pages + dashboard activity section + sidebar both groups verified. Zero regressions on existing surface.
- iteration_20 (current): aria-read endpoint + AriaReadPanel + Founder Brief modal added; backend curl-verified, frontend screenshot-verified.
- iteration_21 (NEW — Feb 2026): 3 secondary workspace pages shipped — **Sales Assets** (CRUD library ARIA uses to reply), **ARIA Brain** (consolidated knowledge map with % completion + gaps), **Weekly Recap** (week-over-week sales summary). Backend: 15/15 pytest PASS. Frontend: full CRUD on Sales Assets verified, all 3 sidebar nav items functional, no console errors, zero regressions. Typography aligned to genleadai.com: **Space Grotesk (display) + Inter (body)** replaces Instrument Serif. Computed h1 font-family verified.

## Phase Next (not yet shipped)
- Conversations chat-style thread redesign (currently exists as AriaConversationPanel)
- Booking Assistant inline reminder cards on calendar/booking pages
- Microcopy sweep across remaining pages ("ARIA is working this lead", empty states)
- Wire actual Claude completions into Founder Brief instead of heuristic template
- "Take over manually" / "Let ARIA reply" actions actually mutating conversation state

## Iter 21 — Secondary workspace pages + typography (Feb 2026)
Backend additions in `/app/backend/aria_agent_routes.py`:
- **Sales Assets**: GET `/assets/catalog`, GET `/assets`, POST `/assets`, PATCH `/assets/{id}`, DELETE `/assets/{id}`, POST `/assets/{id}/use` (7 types) stored in `aria_sales_assets` collection.
- **ARIA Brain**: GET `/brain` — completion % from training, 6 sections, gaps, live memory.
- **Weekly Recap**: GET `/weekly-recap` — 7-day vs prev-7-day deltas, biggest win/miss, top channel, 3-item focus.

Frontend new pages: `/aria-agent/assets`, `/aria-agent/brain`, `/aria-agent/weekly-recap` (private, in sidebar).

Typography aligned with genleadai.com: Space Grotesk (display) + Inter (body).

## Iter 22 — Public ARIA content ecosystem (Feb 2026 · SEO/AIO/GEO)

12 public, indexable pages live OUTSIDE auth. The private ARIA workspace is untouched and still gated by ProtectedRoute.

Pages shipped:
- `/aria` — Main product page (hero, definition, 6 features, who-for, FAQ)
- `/aria/demo-dashboard` — Public demo with sample data only (Priya/GrowthNest, Rohit/SaaSWorks, Ananya/ScaleHive, Karan/CloudNest). Includes Demo Workspace label + disclaimer.
- `/aria/lead-feed` — Lead Feed SEO page
- `/aria/sales-reports` — Sales reports SEO page
- `/aria/use-cases/{founders,startups,agencies,consultants,sales-teams}` — 5 persona pages from a shared template
- `/aria/compare/{aria-vs-crm,aria-vs-spreadsheets,ai-sales-assistant-vs-crm}` — 3 comparison pages from a shared template

Per-page SEO (via `useSEO` hook injecting tags + JSON-LD):
- Unique `<title>`, meta description, canonical link
- Open Graph (`og:title`, `og:description`, `og:url`, `og:image`, `og:site_name`)
- Twitter card (`summary_large_image` with title/description/image)
- JSON-LD: SoftwareApplication, FAQPage, WebPage, BreadcrumbList per page
- `index.html` ships base Organization + WebSite JSON-LD for non-JS crawlers

Crawlability:
- `/robots.txt` — explicit Allow for OAI-SearchBot, ChatGPT-User, GPTBot, PerplexityBot, ClaudeBot, Google-Extended, anthropic-ai, Applebot
- `/sitemap.xml` — all 12 public URLs with priorities
- All routes mounted in `App.js` BEFORE the protected `/*` catch-all

Branding/Voice:
- "CRMs store pipeline. ARIA tells founders what to do next" used consistently
- Answer-first definitions placed at top of every page so AI engines can quote
- Internal links between product page → use cases → compare → demo dashboard

## Test Status (iter 22)
- iteration_21.json: 100% pass — all 12 public pages render with title/canonical/JSON-LD/H1/FAQ; demo dashboard uses sample data only; robots.txt + sitemap.xml served; private dashboard regression clean (ProtectedRoute redirects, real workspace pages still work post-login).
Backend additions in `/app/backend/aria_agent_routes.py`:
- **Sales Assets**: GET `/assets/catalog`, GET `/assets`, POST `/assets`, PATCH `/assets/{id}`, DELETE `/assets/{id}`, POST `/assets/{id}/use` (7 types: message_template, voice_note, case_study, proposal_template, founder_intro, objection_response, pricing_doc) stored in `aria_sales_assets` collection.
- **ARIA Brain**: GET `/brain` — computes completion % from training collection, 6 sections (business, icp, qualification, voice, objections, booking), gaps list, live memory stats.
- **Weekly Recap**: GET `/weekly-recap` — 7-day vs prev-7-day deltas on 6 KPIs (new leads, qualified, replies, calls booked, won, lost), biggest win/miss, top channel, 3-item focus plan.

Frontend new pages:
- `/aria-agent/assets` → `SalesAssets.js` (type tabs, stats tiles, full CRUD modal, copy-to-clipboard increments usage)
- `/aria-agent/brain` → `AriaBrain.js` (conic-gradient completion ring, expandable section cards, gaps linking to Train ARIA)
- `/aria-agent/weekly-recap` → `WeeklyRecap.js` (narrative hero, stat grid with delta badges, biggest win/miss, next-week focus)

Sidebar additions (AI SALES AGENT section): Sales Assets, ARIA Brain, Weekly Recap.

Typography alignment:
- `index.css`: `--font-display` → `Space Grotesk` (matches genleadai.com display H1/H2), `--font-sans`/`--font-body` → `Inter` primary (matches genleadai.com body). Removed Instrument Serif.
- `.font-display` weight 700 + `-0.02em` tracking for display legibility.
- `PageHeader.js` H1 sizes tuned down to 2rem/2.375rem/2.75rem for sans-serif readability.

## Backlog
- P1: server.py refactor (~5160 lines) into `/app/backend/routes/`
- P1: `@app.on_event("startup")` → FastAPI lifespan handler
- P2: DRY shared `EmailScheduleCard` for DCP + EOD
- P2: react-beautiful-dnd `isDropDisabled` dev warning on Pipeline (pre-existing)

## Deployment: READY
Custom domain target: app.genleadai.com
