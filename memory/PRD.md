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

## Iter 28 — Pietential "Ask Aria to Reply" Claude integration + CSV patch verification (Feb 2026)
**Backend** (`/app/backend/routes/pietential.py`):
- New endpoint `POST /api/pt/leads/{id}/ask-aria` — Claude 4 Sonnet via Emergent LLM Key.
- Builds rich prompt context: lead identity + ICP fit + score + stage, last 10 engagement events with timestamps + score deltas + source, **account cascade context** (sequence_status, pause_required, highest_score, pause warning), Aria's recommendation tier, last internal note, optional founder steer.
- Tone matrix: founder_led / consultative / direct / soft_nurture / sharp_closer (+ friendly / premium).
- Channel matrix: linkedin / email (with Subject:) / whatsapp / call_script.
- Graceful heuristic fallback if Emergent LLM key missing or Claude errors.

**Frontend**:
- New `PtAskAriaModal` component (`/app/frontend/src/pietential/components/PtAskAriaModal.js`) — channel + tone pickers, AI-POWERED badge, ACCOUNT PAUSED badge when company.pause_required, regenerate, copy & open CTA.
- Mounted on `PtLeadDetail` via "Ask Aria to Reply" button in header (purple gradient).

**Verification**:
- CSV `_recompute_company` patch (Iter 27 leftover) verified end-to-end via curl: 0-event CSV row creates lead AND flips `saleshandy_active=True` on `pt_companies`.
- `/api/pt/leads/{id}/ask-aria` curl-verified with both empty timeline (cold-touch grounded in title/company/ICP) and rich timeline (consultative reply referencing actual click-through).
- Screenshot-verified frontend modal renders on top of PtLeadDetail with correct purple gradient, channel + tone selectors functional, regenerate spinner active.

## Iter 21 — Secondary workspace pages + typography (Feb 2026)
Backend additions in `/app/backend/aria_agent_routes.py`:
- **Sales Assets**: GET `/assets/catalog`, GET `/assets`, POST `/assets`, PATCH `/assets/{id}`, DELETE `/assets/{id}`, POST `/assets/{id}/use` (7 types) stored in `aria_sales_assets` collection.
- **ARIA Brain**: GET `/brain` — completion % from training, 6 sections, gaps, live memory.
- **Weekly Recap**: GET `/weekly-recap` — 7-day vs prev-7-day deltas, biggest win/miss, top channel, 3-item focus.

Frontend new pages: `/aria-agent/assets`, `/aria-agent/brain`, `/aria-agent/weekly-recap` (private, in sidebar).

Typography aligned with genleadai.com: Space Grotesk (display) + Inter (body).

## Iter 26 — SalesHandy auto-poll cron + Automation rules (Feb 2026)
**Auto-poll cron:** `_saleshandy_poll_loop` async task started in `attach_integrations_routes` startup hook — polls SalesHandy activity every 5 min, dedupes events, syncs to ARIA activities collection. Verified in backend logs: `[SalesHandyAutoPoll] Background loop started (5 min tick)`.

**Automation rules** (3 new endpoints):
- `GET/POST/PATCH/DELETE /api/integrations/automation/rules` — CRUD on rules with triggers (`status`, `source`, `icp_tier`)
- `apply_rules_to_lead` helper exposed via `app.state.apply_integration_rules` — called from `PATCH /api/leads/{id}` whenever status changes
- Auto-pushes lead to configured SalesHandy sequence / Lemlist campaign on trigger match
- Dedup via `synced_prospects` collection (won't push twice to same sequence)
- Logs activity event `auto_pushed_to_{platform}` with rule_id metadata

**Frontend:** AutomationRules section added to SalesEngagement page with rule list, on/off toggle, run count display, and inline create form (platform → sequence → trigger → value with live preview).

## Iter 25 — SalesHandy + Lemlist integrations (Feb 2026)
**Bring-your-own-key model** — each workspace pastes its own API keys, Fernet-encrypted (AES-128) before storage.

Backend (`/app/backend/integrations_routes.py` — new modular file):
- `GET /api/integrations/status` — connection state + masked key preview
- `POST /api/integrations/keys` — save encrypted (auto-registers Lemlist webhook)
- `DELETE /api/integrations/keys/{platform}` — disconnect
- `POST /api/integrations/test/{platform}` — test connection by listing sequences/campaigns
- `GET /api/integrations/sequences/{platform}` — list available sequences (SH) / campaigns (LL)
- `POST /api/integrations/push` — push selected ARIA leads into a chosen sequence (with dedup)
- `POST /api/integrations/lemlist/webhook` — real-time inbound: contacted/opened/clicked/replied/bounced/meetingBooked → ARIA activity feed
- `POST /api/integrations/saleshandy/poll` — manual polling endpoint (no webhooks on SH)

Two API client classes: `SalesHandyClient` (x-api-key) + `LemlistClient` (Basic auth with `:APIKEY` format).

Required env: `ENCRYPTION_KEY` (Fernet) — added to `/app/backend/.env`.

Frontend:
- `/sales-engagement` page — `SalesEngagement.js` with both platform cards
- `PushToSequenceModal.js` — used from Lead Inbox "Send to sequence" button
- Sidebar entry "Sales Engagement"

## Iter 24 — CSV field mapping (Feb 2026)
- Frontend `CSVUploadForm` evolved into a 3-step wizard: **Upload → Map fields → Preview**.
- Auto-suggests ARIA field for each CSV column using a synonym lookup table covering HubSpot, Pipedrive, Salesforce, and spreadsheet conventions (e.g. "First Name" → `first_name`, "Email Address" → `email`, "Lead Source" → `source_channel`, "Phone Number" → `phone`).
- Manual override per-column with disabled options preventing duplicate mapping.
- Required-field status chips with green/red indicators; Continue button gated on required fields being mapped.
- Verified end-to-end with a HubSpot-style CSV — all 7 columns auto-mapped correctly with 0 manual clicks.
- Test data IDs added: `csv-stepper`, `mapping-row-{col}`, `mapping-select-{col}`, `mapping-required-status`, `mapping-missing-msg`, `mapping-continue-btn`, `preview-back-btn`, `preview-back-to-map-btn`.

## Iter 23 — CSV bulk lead upload (Feb 2026)
- Backend: `POST /api/leads/bulk` accepts up to 5,000 leads, uses MongoDB `insert_many(ordered=False)`, dedupes within-payload by email, returns `{created, failed, errors[]}` with row-level error reasons (validation + duplicate-key tolerated).
- Frontend: `LeadInbox` Add Lead modal now has dual-mode tabs: **Single lead** (existing form) and **CSV upload** (new). CSV mode uses `papaparse` with drag-drop, required column validation, live preview with row-level error highlighting, and a downloadable template (`aria-leads-template.csv`).
- New dependency: `papaparse@5.5.3`.
- Test data IDs: `mode-tab-csv`, `csv-dropzone`, `csv-file-input`, `csv-template-btn`, `csv-preview`, `csv-valid-count`, `csv-invalid-count`, `csv-submit-btn`, `csv-result-screen`, `csv-created-count`.

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

## Iter 28 — Sync Activity Digest card on Dashboard (Feb 2026)
**Backend** new endpoint: `GET /api/integrations/digest/today` (in `integrations_routes.py`).
- Aggregates today's UTC activities by type from `activities_collection`.
- Tracked event types: `email_sent`, `email_opened`, `email_clicked`, `replied`, `bounced`, `meeting_scheduled`, `interested`, `pushed_to_lemlist`, `pushed_to_saleshandy`, `auto_pushed_to_lemlist`, `auto_pushed_to_saleshandy`.
- Returns `{today_start, connected:{lemlist, saleshandy}, any_connected, counts:{...}, recent:[]}` where recent is the latest 5 events hydrated with `lead_name` and `company`.

**Frontend** new component: `/app/frontend/src/components/SyncActivityDigest.js`
- Mounted on Dashboard between `<AriaAgentActivitySection />` and `<FounderCommandCenter />`.
- 6 KPI tiles: Sent / Opened / Clicked / Replies / Meetings / Pushed.
- 3 states: populated (today has events), quiet (connected but no events yet), empty (not connected — CTA to /sales-engagement).
- Header shows Lemlist / SalesHandy connection pills + "Manage" link to /sales-engagement.
- Auto-refreshes every 90 seconds.
- Test data IDs: `sync-activity-digest`, `digest-tile-{name}`, `digest-recent-{i}`, `digest-manage-link`, `digest-empty-state`, `digest-quiet-state`, `digest-connect-cta`.

**Test status (iter 23)**: Backend 100%, Frontend 100%, zero regressions.

## Iter 29 — Beta badge + Beta feedback (Feb 2026)
**Beta badges:** amber pill next to the ARIA brand on Login page, authenticated sidebar (desktop + mobile), public nav (all 12 SEO pages). Browser tab title updated to "ARIA (Beta) | AI Sales Assistant...". Testids: `beta-badge-login`, `beta-badge-sidebar`, `beta-badge-mobile`, `beta-badge-public`.

**Beta feedback** — new modular router `/app/backend/routes/beta_feedback.py`:
- `POST /api/beta-feedback` — any authenticated user; message 3–2000 chars; category ∈ {bug, idea, praise, other}; optional page_url.
- `GET /api/beta-feedback` — admin-only; returns `{feedback:[], counts:{total, unresolved, by_category}}`; filter by `resolved` and `category`.
- `PATCH /api/beta-feedback/{id}` — admin-only; resolve/reopen + admin_note.
- `DELETE /api/beta-feedback/{id}` — admin-only.

**Frontend:**
- `BetaFeedbackButton.js` — amber pill button below Sign Out in sidebar. Opens modal with 4-category picker (Bug/Idea/Love it/Other with Phosphor icons), textarea with char counter, "attach page URL" checkbox. Sonner toast on success.
- `AdminFeedback.js` mounted at `/admin/feedback` — 4 stat tiles + filter chips + resolve-toggle + delete rows.

**Test status (iter 24)**: Backend 15/15 pytest, Frontend e2e 100%, zero issues.

## Iter 30 — Aria for Pietential workspace (multi-tenant ready) (Feb 2026)

**Architecture: workspace switcher pattern.** New top-level `WorkspaceProvider` (`/app/frontend/src/context/WorkspaceContext.js`) with localStorage persistence. Two workspaces today: `aria_crm` (existing) and `pietential`. Adding new tenants = adding a row to `WORKSPACES` array. Switcher dropdowns in both sidebars.

**Backend** new modular router `/app/backend/routes/pietential.py` (single file, ~600 lines, fully self-contained):
- 6 isolated MongoDB collections: `pt_leads`, `pt_companies`, `pt_events`, `pt_tasks`, `pt_notes`, `pt_integrations`.
- 19 scoring rules (`SCORING_RULES`) covering Saleshandy/Lemlist/Newsletter/Lead Magnet/JSA/Website/Calendly/Manual.
- Stage classifier (cold/warm/hot/engaged/session_pilot) + recommendation generator.
- Account cascade: when any contact crosses Hot or fires a `trigger_pause` event, the whole company gets `pause_required=true` and `sequence_status=pause_required`. Engaged+ flips owner to John.
- Auto-task generator: pause Saleshandy + pause Lemlist + route to John + send John personal email + create opportunity (for Calendly).
- 25+ endpoints: leads CRUD + bulk + CSV, companies CRUD, events ingest, tasks CRUD, notes, overview metrics, weekly+monthly reports, scoring-rules introspection, integrations upsert+test.
- 13 webhook endpoints (Saleshandy/Lemlist/Newsletter/Lead Magnet/JSA/Calendly/GA4) routed through one `_ingest_event` dispatcher.

**Frontend** new `/app/frontend/src/pietential/` workspace:
- `PtLayout` — light enterprise theme, teal accent (#0F766E), sidebar with workspace switcher + 7 nav items.
- 8 pages: Overview (10 metric tiles + zero-state), Lead Feed (table + 5 filters + add modal + CSV upload), Lead Detail (Identity + Status + Score breakdown + Timeline + Notes + simulate-event), Accounts (with pause banner), Tasks (CRUD with auto-task creation banner), Reports (weekly+monthly tabs), Integrations (13 cards with API-key save + webhook hint URLs + copy button), Settings (scoring rules + stages + decay).

**Branding**: "Aria" wordmark + Beta pill + "for Pietential" subtitle. Multi-tenant: each tenant can have its own brand label.

**Test status (iter 25)**: Backend 13/13 pytest, Frontend e2e 100%, zero blocking issues. Code review noted webhook authentication + plaintext API key storage as production hardening items (acceptable for client demo).

## Iter 31 — Pietential Phase 2 (a + b + c + Train Aria) (Feb 2026)

**Demo polish (a):**
- "Replay demo flow" button on Pt Overview → creates demo-prospect@pietential-demo.com lead, applies 4 events (newsletter.subscribed → saleshandy.email_clicked → saleshandy.positive_reply → calendly.session_booked) showing cold→warm→hot→engaged→session_pilot cascade live.
- Lead Detail: copy-email and copy-LinkedIn quick actions.
- Overview redesigned with two sections — Primary platforms (5 SH/Lemlist tiles) + Pipeline health (10 tiles incl. john_owned).

**Roles UI (b):**
- New page `/pt/team` (admin only) showing role legend (4 roles) + member table with role dropdown.
- New endpoints `/api/pt/team`, `/api/pt/team/role`, `/api/pt/me/permissions`.
- Non-admin users see a clear notice; role guard enforced backend-side.

**Production hardening (c):**
- **Fernet encryption** for integration `api_key` (reuses `ENCRYPTION_KEY` env var). Lists return `api_key_masked` (••••XXXX); plaintext never returned.
- **Webhook signature verification** via optional `X-Pt-Webhook-Secret` header; per-integration `webhook_secret` stored. Uses `hmac.compare_digest` for timing-safe equality. Falls open when no secret set (acceptable for client demo).
- **Score decay cron** — hourly background loop on startup. −10 at 30d inactive, −20 + `automation_status='long_cycle_nurture'` at 60d inactive. Manual trigger at `/api/pt/score-decay/run` (admin only).

**Train Aria:**
- New collection `pt_training_signals` + endpoints `/api/pt/training/signal` + `/api/pt/training/signals`.
- TrainAriaCard on Lead Detail with 3 controls: ICP fit override (match/partial/outside), reply classification (positive/neutral/negative), "Mark positive conversation" (idempotent — fires +40 score event only once per lead).

**Pietential-specific:**
- Saleshandy + Lemlist marked PRIMARY; other 11 integrations moved to Future/Optional section in Integrations page.
- New `/pt/saleshandy` and `/pt/lemlist` activity pages with platform-specific stats (opens/clicks/replies vs connections/DM replies/post engagement).
- New `/pt/touchpoints` Touchpoint Map page rendering all 10 prospect touchpoint flows from the Pietential roadmap with live event counts per touchpoint.

**Test status (iter 26)**: Backend 25/25 pytest, Frontend e2e 100%, zero blocking issues. Two follow-up fixes applied post-test: hmac.compare_digest for timing-safe webhook secret check + idempotency on positive_conversation training signal.

## Backlog
- P1: continue server.py extraction — remaining 4818 lines still hold aria/*, leads/*, lead-magnets/*, billing/*, assets/*, webhooks/*
- P1: `@app.on_event("startup")` → FastAPI lifespan handler
- P2: DRY shared `EmailScheduleCard` for DCP + EOD
- P2: (Security) /api/auth/register is open; lock behind invite/admin-only
- P2: Seed sample automation rule + Lemlist activity for UI demo of rule-test button + timeline badges

## Iter 27 — Rule testing + badges + modular backend refactor (Feb 2026)
**Frontend**:
- `LeadDetail.js` activity timeline renders Lemlist / SalesHandy badges when `activity.metadata.platform` is set (INTEGRATION_EVENT_META + platformOf helper).
- `SalesEngagement.js` AutomationRules each row now shows a `Test` button (testid `rule-test-{id}`) that calls `POST /api/integrations/automation/rules/{id}/test` and displays a result panel with `would_run` state, skip/push reason, and sample matching lead.
- Silenced 21 Pipeline.js react-beautiful-dnd dev warnings by passing explicit `isDropDisabled={false}` on every `<Droppable>`.

**Backend bug fix**: `integrations_routes.py` line 541 — `test_rule` endpoint projection had a Python bareword bug (`status: 1 if False else 1` → NameError). Fixed to `'status': 1`.

**Backend modular refactor (major)**: server.py reduced from 5252 → 4818 lines.
- New `/app/backend/deps.py` centralises DB handle, collections (8 core), JWT helpers, `get_current_user`, `verify_password`, `get_password_hash`, `create_access_token`, `serialize_doc`.
- New `/app/backend/routes/` directory with:
  - `auth.py` — `/api/auth/register|login|me`
  - `meta.py` — `/api/health`, `/api/users`, `/api/calendly/event-types|user|availability`
  - `campaigns.py` — `/api/campaigns` CRUD
  - `ai.py` — `/api/ai/score|email-generate|chat|summarize`
  - `analytics.py` — `/api/analytics/dashboard`, `/api/email/send`
- server.py uses `app.include_router(...)` for each; zero behaviour change verified via iteration_22 testing agent (23/24 pytest pass, frontend 6/6 pass, 0 console errors, 100% regression clean).

## Deployment: READY
Custom domain target: app.genleadai.com
