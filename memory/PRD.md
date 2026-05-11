## Iter 41 — Dashboard UI/UX Beautification: AriaCommandRoom hero + light/warm glassmorphism (Feb 2026)

**User intent:** "Beautify and upgrade the UI/UX of the existing ARIA dashboard." Light background, warm neutral base, deep navy text, glassmorphism, tasteful micro-animations (page fade-in, hover lift, glowing ring on Hot Leads, soft pulse for ARIA Active), and a new ARIA Personality Layer panel showing current mode + next best action. Backend untouched.

**New component** `/app/frontend/src/components/AriaCommandRoom.js` — the premium AI-first dashboard hero:
- Warm gradient surface (white → lavender → cream) with radial soft-light overlays.
- Time-of-day greeting ("Good evening, Megha") with Sun/Moon/Coffee icon.
- H1: "Your AI sales command room" + supporting copy.
- **Animated ARIA ACTIVE pill** (`aria-status-pill`) — green pulsing dot via `aria-ping` keyframe + BETA badge + "Multi-tenant · DPDP-ready" subtext.
- **Today summary stat grid** (`today-summary`): Hot leads (with red glowing ring via `aria-stat-hot` class when > 0), Conversations today, Going cold, Meetings this week — each clickable.
- **ARIA Personality Panel** (`aria-personality-panel`) — Robot avatar in a colored gradient tile, "Aria is watching your pipeline" eyebrow, dynamic mode chip (`drafting | nurturing | following | listening`) computed from real hot/stale/recent-opens/pending-followups counters, sentence + subtitle from `buildNextAction()` (also fed by real analytics), primary CTA + "Ask Aria what to do next" secondary button.
- **Quick actions grid** (`quick-actions`): Add lead · Your 5 today · Pipeline · Conversations.
- Hits real endpoints `/api/analytics/dashboard`, `/api/health/stale-leads`, `/api/leads?icp_tier=hot&limit=1` — no fake data.

**Dashboard.js refactor** (`/app/frontend/src/pages/Dashboard.js`):
- Replaced `<WorkspaceHero />` with `<AriaCommandRoom userName={user?.full_name} />` at the top.
- Wrapped root in `aria-fade-up`; AriaStories and the central workspace grid get staggered `aria-fade-up-1` / `aria-fade-up-2` reveals.
- Every card (KPI grid, all chart cards, Priority Leads, ARIA Activity, B2B/B2C donut, ICP donut, Quick Actions, Recent Leads table) now uses `aria-card-lift` (translateY -2px + shadow-hover on hover) + `rounded-2xl`.
- Existing motion utilities reused from `index.css`: `aria-fade-up`, `aria-fade-up-1..4`, `aria-card-lift`, `aria-pulse-ring`.

**Verified (testing_agent_v3_fork iter41)**:
- Frontend 100% — all 24 required data-testids rendered, real backend data hydrated (Hot=19, Going Cold=83), all 4 stat-card navigations work, all 4 quick-actions navigate correctly, ARIA Personality Panel mode chip + CTA work, console clean, zero regressions on legacy dashboard sections.

---


## Iter 40 — Marathon Session 2: Integration Hub + Conversations + Legal + Retention (Feb 2026)

User: "start with session 2" — continued Option D marathon. Built Phase 7 remaining, Phase 8 retention/legal, and Phase 3.4 Conversations page.

### Phase 7 — Unified Integration Hub
- **Backend `/app/backend/routes/integrations_hub.py`** (≈360 lines, single unified module):
  - 8 supported types: `ga4` · `meta_capi` · `zapier` · `make` · `typeform` · `instantly` · `google_ads` · `apollo` — each with category (analytics/automation/lead_source/outreach) and direction (outbound/inbound).
  - Endpoints: `GET /api/integrations/list`, `POST /api/integrations/{type}/connect`, `DELETE /api/integrations/{type}/disconnect`, `POST /api/integrations/{type}/test`, `GET /api/integrations/events?limit=N`, `POST /api/integrations/events/{id}/retry`.
  - **Outbound dispatchers:**
    - `_fire_ga4` — GA4 Measurement Protocol POST with sha256 client_id, maps Aria events to GA4 event names (aria_lead_created, aria_meeting_booked, aria_deal_closed_won…).
    - `_fire_meta_capi` — Meta Conversions API POST with sha256-hashed user_data (em/ph/fn/ln), supports test_event_code.
    - `_fire_generic_webhook` — Zapier + Make.com (same JSON body with event_type, lead snapshot, extra).
  - **Inbound webhooks (no-auth, public):**
    - `POST /api/integrations/typeform/webhook/{tenant_id}` — parses form_response.answers, normalizes, routes through lead_capture.capture_lead.
    - `POST /api/integrations/instantly/webhook/{tenant_id}` — handles reply payloads.
    - `POST /api/integrations/google-ads/webhook/{tenant_id}` — parses user_column_data array.
    - `POST /api/integrations/apollo/import` (authenticated) — bulk array import, de-dupes via _normalize_and_capture.
  - **Lifecycle fan-out** — `fire_lifecycle_event(tenant_id, event_type, lead, extra)` injected at top of `crm_sync.fire_event` so it fires for every Aria lifecycle event regardless of CRM connection state. Async/non-blocking; logs every dispatch to `integration_events`.
  - Secret masking on response — `access_token`, `api_secret`, `webhook_url` etc. are masked as `EAAx••••••••xxxx` so secrets never leak back to UI.
- **Frontend `/app/frontend/src/pages/Integrations.js`** — full rewrite:
  - Hub page (`integrations-hub-page`) with category filter pills (`cat-all/analytics/automation/lead_source/outreach`).
  - 8 integration cards each showing category badge, blurb, connection status (`Connected` green / `Not connected` grey), and last error if any.
  - Config modal opens on card click. For outbound: input fields (Measurement ID, API secret, Pixel ID, Hook URL, etc.) with masked previews of current values, Save/Test/Disconnect actions. For inbound: shows a **copyable webhook URL card** + docs link. For Apollo: JSON textarea + bulk Import button.

### Phase 3.4 — Conversations page (`/conversations`)
- **Backend `/app/backend/routes/conversations.py`** — `GET /api/conversations/threads` joins leads + aria_conversations to surface last message preview + Aria confidence + sentiment per thread. Urgent and negative sentiment threads float to top.
- **Frontend `/app/frontend/src/pages/Conversations.js`** — sentiment filter pills (All/Urgent/Negative/Positive/Neutral with live counts), name/phone search, urgent rows highlighted with red gradient stripe. Click thread → routes to `/lead-inbox?lead={id}` for full takeover.
- Sidebar nav `nav-conversations` (ChatCircle icon) inserted between Follow-Ups and AI Assistant.

### Phase 8.7 — Data Retention background loop
- New `/app/backend/routes/retention.py` — 24h tick (started in server.py startup):
  - Conversation messages older than 365 days → content redacted to `[redacted]` (metadata preserved).
  - `classification_log` older than 180 days → hard delete.
  - `api_usage_log` older than 90 days → hard delete.
  - `failed_message_log` resolved entries older than 30 days → hard delete.

### Phase 8.8 — Legal pages
- Replaced `/app/frontend/src/pages/legal/Legal.js` (old dark-theme stub) with full GenLeadAI-branded, DPDP Act 2023-compliant content for **/privacy**, **/terms**, **/dpa**. Each page is public (no auth), uses `LegalShell` with a "Back to Aria" link, gradient-friendly icon header, structured H2/H3/UL sections.

### Bug fixed during testing
- **HIGH:** `lead_capture.py` phone-dedup regex crashed when cleaned phone had a leading `+` (regex `+xxxxx$` rejected by Mongo). Fixed by wrapping in `re.escape(phone_tail)`. Curl-verified with `+91922222` after fix.

### Verified — Iter 40 testing
- Backend 17/18 pytest pass (1 HIGH issue identified + immediately fixed in-session).
- Frontend 100% e2e — all 4 new pages render, all data-testids match, no console errors, sidebar nav-conversations works, category filter narrows the hub cards correctly, config modal opens with proper masking, secret retention preserves existing config values.

### Phase 7 not yet built (Session 3+ candidates)
- Lemlist / Saleshandy hub-style cards (existing Sales Engagement page already covers these via different UI).
- HubSpot / Pipedrive / Zoho / Salesforce hub-style cards (existing CRM tab in Settings already covers these via dedicated CrmSettingsTab).
- OAuth flow for Meta Lead Ads (currently uses static webhook URL).

### Remaining marathon items (Session 3+)
- 360dialog webhook HMAC signature verification audit.
- Embeddable lead capture widget v2 — "Click-to-WhatsApp" lite button (alt of current form).
- Settings → Notifications tab (mentioned in Master Spec 4.2).
- Master Spec Phase 5.6 "Platform Stats" tab for Master Admin.

---


## Iter 39 — Marathon Session 1: Dashboard wiring + Reports + Admin tabs + Failed Message UI + Website Widget (Feb 2026)

User request: full Phase 1-8 audit against the Master Spec and execute everything missing. Chose Option D (marathon). This is **Session 1 of N** covering:

### Phase 3 — Dashboard wiring (5 min)
- Wired `<PipelineHealthGauge />` into Dashboard right column (above `<PipelineMoodCard />`).
- Wired `<StaleLeadAlertChip />` between AriaStories and the main grid — shows only when stale leads exist.

### Phase 5.1 — Reports page (`/reports`)
- **Backend:** new `/app/backend/routes/reports.py` with 5 endpoints:
  - `GET /api/reports/summary?period=this_month|last_month|last_3_months` — 4 KPIs with % change vs previous period (leads_handled, qualified, meetings, won).
  - `GET /api/reports/funnel` — 6-stage Pipeline funnel (Entered → Contacted → Replied → Qualified → Meeting → Won) with drop-off % per stage.
  - `GET /api/reports/activity` — daily conversation count (last 30d) + touchpoint sent/failed/skipped totals.
  - `GET /api/reports/sources` — per-source aggregation with conversion %.
  - `GET /api/reports/export` — branded PDF via reportlab (KPI table + funnel table + source table + GenLeadAI footer).
- **Frontend:** new `/app/frontend/src/pages/Reports.js` — 3 period toggles, 4 KPI cards, Recharts horizontal bar funnel, Recharts BarChart for daily conversations, PieChart for touchpoint mix, source performance table. `Export PDF` button downloads file.
- Replaced `/reports` route (was pointing to old `Analytics`).

### Phase 5.5 — Failed Message Log UI (`/admin/failed-messages`)
- New page `/app/frontend/src/pages/FailedMessages.js` consuming existing `/api/failed-messages` endpoints (list/retry/dismiss already shipped Iter 36).
- Lists unresolved failures with retry count, channel icon, error reason, payload preview, lead link.
- Owner/admin buttons: individual Retry, individual Dismiss, "Retry all" batch action.
- Sidebar nav entry `nav-failed-messages` added under PLATFORM section.
- Auto-refresh every 30s.

### Phase 5.6 — Master Admin remaining tabs
- **HealthMonitorTab** — new `/app/backend/routes/audit_log.py` endpoint `GET /api/admin/workspaces/health/services` returning live pings for: MongoDB (with latency), Claude (config status), Resend, WhatsApp providers (configured tenant count), Stripe, Touchpoint engine (idle/ok heuristic). Component auto-refreshes every 30s, shows 6 service cards with status badges.
- **TrialExpiriesTab** — consumes existing `/api/admin/workspaces/trials/expiring?days=N` endpoint. Window selector (1/3/7/14 days), per-row Extend +7d / Email owner / Mark Converted actions.
- MasterAdmin.js TABS reduced from 4 placeholders to 4 real tabs: Revenue · All Workspaces · Trial Expiries · Health Monitor.

### Phase 7 — Website Form Widget + Public Lead Capture
- **Backend:** new `/app/backend/routes/lead_capture.py`:
  - `GET/POST /api/lead-capture/config` — tenant-side widget config (owner/admin only).
  - `GET /api/lead-capture/public-config` — public, no-auth, returns safe subset.
  - `POST /api/leads/capture` — **public lead-creation endpoint** (no auth, tenant_id in body), de-dupes by phone-tail or email, increments score +5 + appends source_history on duplicate, fires touchpoint engine + CRM sync via best-effort imports, respects opt-in compliance.
  - Origin allowlist enforced if configured.
- **Public widget JS:** new `/app/frontend/public/aria-widget.js` (≈3KB) — embeddable floating contact form, auto-derives endpoint from script src, fetches public-config, renders form with configured fields/consent/colour, posts to capture endpoint, captures UTM params, shows success state after submit.
- **Frontend Settings:** new `/app/frontend/src/components/settings/LeadCaptureSettings.js` — toggleable enable, title/subtitle/button label, accent colour picker (live), field chip selector (first_name/last_name/email/phone/company/message), consent checkbox + text, origin allowlist textarea, **embed snippet card** (dark theme, copy button), **live preview** toggle showing form mock with chosen colour.
- Added "Lead Capture" tab to Settings (between API & Forms and CRM).

### Verified (Iter 39 testing report)
- **Backend 12/12 pass** — all reports + admin health + trial expiries + lead-capture endpoints return correct shapes and respect tenant scoping & role gates.
- **Frontend 100% e2e** — Dashboard health gauge + stale chip render, Reports page renders KPIs + funnel + charts + PDF export download verified, Master Admin tabs all clickable + populated, Failed Messages empty state working, Lead Capture settings page + embed snippet card + preview all functional.
- One LOW console warning about `<span>` inside `<option>` flagged by testing agent was a false positive (option contents are plain text).

### Queued for Session 2 (next "continue")
- Phase 7 remaining: GA4 server-side events (Measurement Protocol), Meta Conversions API, Zapier triggers, Make.com triggers, Instantly.ai webhook, Apollo.io import, Typeform webhook, Google Ads Lead Form webhook.
- Phase 8 remaining: Dedicated `/privacy`, `/terms`, `/dpa` legal page routes, Data retention cron (delete old message content / classification log / API usage log), 360dialog webhook HMAC signature verification audit.
- Phase 3.4: Dedicated `/conversations` page with thread list + urgent-float-to-top.

---


## Iter 38 — Touchpoint Mapping as hero workspace (vertical timeline + side drawer + scoring) (Feb 2026)

**User intent:** "I want touchpoint mapping to be the biggest and most important functionality of Aria." Promoted from a buried sub-section into the main sidebar; full redesign of the editor page.

**Sidebar:** New top-level "Touchpoint Mapping" entry (`MapTrifold` icon) between **Reports** and **Integrations** in `/app/frontend/src/components/Layout.js`. Removed duplicate from the AI SALES AGENT section. Page route unchanged (`/touchpoint-journey`) so existing deep-links keep working. H1 renamed "Touchpoint Mapping".

**Backend** — extended `/app/backend/routes/touchpoints.py` with two new endpoints + new `touchpoint_ai_quality_cache` collection:
- `GET /api/touchpoints/scoring` — aggregates `lead_touchpoint_log` per `touchpoint_index`. Returns per-touchpoint `performance` (total_scheduled, sent, skipped, failed, pending, alerts, replies, reply_rate, delivery_rate, skip_rate, **effectiveness** = `0.6*reply_rate + 0.3*delivery + 0.1*(100-skip_rate)`, **grade** A/B/C/D) + `lead_fit` (hot/warm/cold counts from leads.icp_tier) + journey rollup `{score, grade, total_scheduled, total_sent, total_replies, reply_rate, skip_rate, delivery_rate, touchpoint_count}`.
- `POST /api/touchpoints/ai-quality` — Claude scoring of each message on Clarity / Personalisation / CTA / Tone-fit (1-10 each + verdict). Cached per `(tenant_id, sha256(message)[:16])`. Graceful fallback when EMERGENT_LLM_KEY missing or import fails.

**Frontend** — full rewrite of `/app/frontend/src/pages/TouchpointJourney.js`:
- **Vertical timeline** (replaces old horizontal scroll) with dashed connector line behind cards.
- **Drag-and-drop reorder** via react-beautiful-dnd. Each card has a `DotsSixVertical` grab handle.
- **Right-side detail drawer** (sticky, scrollable) auto-selects the first touchpoint on load. 4 tabs:
  1. **Details** — inline edit (day/hour/channel/type/role/condition/message + token chips + Move up/down, Duplicate, Delete).
  2. **Performance** — big effectiveness number + grade badge, 6-tile KPI grid (Scheduled/Sent/Replies/Skipped/Failed/Pending), 3 score bars (reply/delivery/skip rate).
  3. **Lead-fit** — Hot/Warm/Cold bars with counts + percentages.
  4. **AI Quality** — Claude scores via 4 score bars + verdict box. Empty state nudges user to click "Score with AI".
- **Journey score banner** at top: 84px conic gauge + grade chip + 4 stat tiles + "Score with AI" CTA.
- **Save** button starts disabled ("Saved"), turns on ("Save changes") when draft becomes dirty.
- Preserved: Template library / Version history / Document upload modals (8 universal templates, last 5 versions, .docx/.xlsx/.pdf via Claude).
- Counter bar shows N / 32 with tone shift at 28 (gold) and 32 (red).

**Verified — iter38**: Backend 9/9 pytest pass on `/scoring` + `/ai-quality` (live Claude call + cache hit path + graceful fallbacks). Frontend 100% e2e — sidebar nav, vertical layout, drawer auto-select, 4 tabs functional, drag-reorder, dirty/save cycle, add-row counter increment, all 3 modals open. Console clean after react-beautiful-dnd boolean-prop fix.

---


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

## Iter 40 — Session B: Opt-In Compliance · 3-Layer Classification · Touchpoint Engine + Journey Tab (Feb 2026)

**The biggest single iteration so far** — three intertwined feature systems shipped together.

### 1.4 — WhatsApp Opt-In Compliance (`/app/backend/routes/compliance.py`)
- `opted_out_numbers` collection (tenant-scoped) + lead-level `opted_in`/`opted_in_at`/`opted_in_source`/`opted_out` fields.
- **STOP keyword auto-handler** wired into the inbound webhook (`stop`, `unsubscribe`, `no more`, `stop messages`). Adds the sender to the blocklist + flips the matching lead off + cannot be overridden.
- `can_send_outbound(tenant_id, lead)` gatekeeper — used by the engine before every send. Returns `{allow, reason}`.
- Manual endpoints: `POST /api/compliance/lead/opt-in` (with source: `manual_confirmed` / `website_form` / `replied_first` / `imported_with_consent`), `POST /lead/opt-out`, `GET /opted-out`, `DELETE /opted-out/{phone}` (owner-admin only).
- Auto-opt-in on first inbound message (webhook flips `opted_in=true` source=`replied_first`).
- **Frontend**: `LeadOptInBanner` — yellow `lead-opt-in-warning` when not opted in, green `lead-opt-in-ok` after confirm. Onboarding Step 5 has `ob-wa-compliance-checkbox` (required to advance — Meta Business Messaging Policy disclaimer).

### 2.2 — Three-Layer Inbound Classification (`/app/backend/routes/classification.py` + `routes/contacts.py`)
- **Layer 1** — Trigger phrases. 10 default phrases (`i'm interested in`, `pricing please`, `i saw your ad`, etc.) + tenant-custom phrases via `POST /api/classification/triggers`. Match → category=LEAD with confidence 0.95.
- **Layer 2** — Phone lookup. Checks existing leads (last-10 digit fallback), then `workspace_contacts` (mapping `vendor` → VENDOR, `existing_client` → EXISTING_CLIENT, etc.), then opted-out blocklist.
- **Layer 3** — Claude classifier. Sends the message + business context to claude-sonnet-4-5 and parses JSON for `{category, confidence, reason}`. Categories: LEAD/EXISTING_CLIENT/VENDOR/OPERATIONAL/JOB_APPLICANT/UNCLEAR/SPAM/WRONG_NUMBER. Routing rules: LEAD ≥0.80 → create lead, 0.50-0.79 → create lead+needs_review, <0.50 → neutral opener; non-leads → canned response intent.
- All decisions logged to `classification_log` with action_taken + layer_resolved. Override endpoint (`POST /log/{id}/override`) flips category + marks for retraining.
- **`workspace_contacts` CRUD** with 6 contact types + tenant-scoped phone lookup.
- **New `/contacts` page** with two tabs:
  - Contacts table — add/edit/delete + filter by type + 6 colour-coded type badges.
  - Classification log — last 100 inbound events with phone/category/confidence/layer/action columns.
- WhatsApp webhook upgraded: resolves tenant from `phone_number_id` metadata, runs STOP keyword + classification, pauses pending touchpoints when an existing lead replies, auto-opts-in the lead, writes to activities + classification_log.

### Touchpoint Execution Engine (`/app/backend/routes/touchpoint_engine.py`)
- `lead_touchpoint_log` collection — one row per touchpoint per lead, with `status` ∈ {pending, paused, sent, skipped, failed, cancelled, alert_sent}, `scheduled_for`, `fired_at`, `message_sent`, `retry_count`.
- **Auto-instantiation on lead create** (server.py hooks the POST /api/leads path) — copies the tenant's active map and schedules each row using day+hour offsets from now.
- **Async background loop** (`engine_loop`) ticks every 60s, picks up to 30 pending rows where `scheduled_for ≤ now`, renders the message via Claude (claude-sonnet-4-5 with lead context + product description) and sends via `whatsapp_dispatch` (tenant-aware Meta or 360dialog) or Resend (email channel). Falls back to heuristic token substitution on Claude failure.
- **Compliance gate** — every send checks `can_send_outbound()`; if not opted in or blocklisted, row is marked `skipped` with `skip_reason`.
- **Reply-pause** — webhook calls `pause_lead(tenant_id, lead_id)` when an inbound message arrives for an existing lead.
- **Closed-Won/Lost cancellation** — lead-update endpoint detects status starting with "Closed" and calls `cancel_lead()` with reason `stage:Closed Won`.
- **Owner override endpoints**:
  - `POST /api/touchpoints/lead/{id}/action` with `{action: pause_lead | resume_lead | cancel_remaining}`.
  - `POST /api/touchpoints/touchpoint/{tp_id}/send-now` — synchronous fire of a specific row (owner/admin only).
  - `GET /api/touchpoints/lead/{id}/journey` — full per-lead timeline.
- `alert_human` touchpoints don't send; they create an entry in the `aria_alerts` collection for the team.
- **Frontend**: new `LeadJourneyTab` component mounted in `LeadDetail.js` between ARIA Agent and Details tabs. Shows full timeline with status pills (sent/pending/paused/failed/cancelled/alert_sent), expandable "View" of sent messages, "Send now" override per row, Pause/Resume/Cancel-remaining controls at top.

### Critical fix mid-iter (lead.id stamp)
- **RCA from iter31**: leads stored only `_id` (ObjectId) but compliance + engine + classification all look up by `id` (string). 4 HIGH-priority failures.
- **Fix**: `POST /api/leads` now pre-computes `ObjectId()`, stamps both `_id` and `id = str(_id)` in a single insert. Backfilled all existing leads via `migrate_to_multi_tenant.py` aggregation pipeline.

### Verified (testing_agent_v3 iter31 + iter32 + manual self-test)
- **Backend 25/25 pytest pass** — compliance (opt-in/out + STOP keyword), classification (all 3 layers + log + triggers + cross-tenant isolation), engine (instantiate + idempotent + pause/resume/cancel + send-now + Closed-Won cancel).
- **Frontend self-test verified**:
  - Lead detail Journey tab → 8 touchpoints render, Pause→Resume flow works, Send now fires #1 and renders Claude copy ("Hi there! I'm Aria, the sales assistant at GenLeadAI Demo. Thanks for reaching out! What specific challenge are you hoping our offering can help you solve?") with proper FAILED status + `not_configured` error (expected — demo has no WhatsApp creds).
  - LeadOptInBanner — green "Opted in · manual_confirmed" banner visible after API opt-in.
  - Contacts page (/contacts) — add/edit/delete flow + classification log tab.

### Deferred to Session C
- 3.5 Stale Lead Engine + Pipeline Health Score
- 3.6 Sentiment detection on every inbound
- 3.3 Conversations Take-over flow + urgent-float-to-top
- 5.5 Graceful degradation + failed_message_log + retry queue + owner alerts

## Iter 39 — Session A: Branding · Pricing overhaul · Trial · Tutorials · Troubleshooting · Limits · Claude preview (Feb 2026)

**Backend** (`/app/backend/routes/billing_plans.py` + `/app/backend/routes/touchpoint_preview.py`):
- **New plans catalog**: DIY (₹4,999) · DWY (₹12,999) · DFY (custom · min ₹29,999). Stored server-side, returned by `GET /api/plans/catalog`.
- **Trial logic**: `ensure_trial_on_tenant()` idempotently stamps `trial_started_at` + `trial_ends_at` (now + 14d) + `plan='trial'` on first `GET /api/plans/status` for any tenant missing those fields. Preserves legacy `pro`/`starter`/etc. plans untouched.
- **Plan-state endpoints**:
  - `GET /api/plans/status` — returns plan + trial_days_left + on_trial + trial_expired + locked + usage counters (active_leads, team_seats).
  - `POST /api/plans/select` — owner/admin sets `plan` field (DIY/DWY/DFY). Pure metadata switch — no card charge (Stripe still deferred).
  - `POST /api/plans/contact-sales` — logs a DFY inquiry to `dfy_inquiries` collection.
- **Touchpoint preview** (`POST /api/touchpoints/preview`): given template_id + in-progress business/persona/sales form state, calls Claude (Emergent Universal Key, claude-sonnet-4-5) to rewrite the first N (default 2) touchpoint templates into founder-specific copy. Each item has `ai_powered: bool` so UI can fall back gracefully when Claude fails. Heuristic token-substitution fallback preserved.

**Frontend**:
- **Auth pages** — Login, Signup, Invite Accept now carry the GenLeadAI wordmark/tagline (`Powered by Aria · GenLeadAI`, data-testid `genleadai-footer`). Platform "Made with Emergent" badge is platform-level and OUT OF MAIN AGENT SCOPE — user can disable via Emergent settings/plan upgrade (support agent flagged).
- **Billing rewrite** (`/app/frontend/src/pages/Billing.js`) — 3 cards side-by-side: DIY (blue border) · DWY (gold border + "Most Popular") · DFY (gradient border + "Managed"). Each card has feature/excluded lists with check/x icons, CTA buttons (Start 14-Day Trial / Talk to Us), and the trial disclaimer at the bottom.
- **TrialBanner** (`/app/frontend/src/components/TrialBanner.js`) — gold top banner for active trial showing days-left + Upgrade-now CTA + dismiss. Full-screen paywall when trial expired. Auth-context-driven retry so it picks up state after axios interceptor is hydrated (post-iter30 fix).
- **New pages** + sidebar entries:
  - `/troubleshooting` — 6-item accordion of common issues + contact section (email + Calendly).
  - `/tutorials` — 15 tutorial cards across 5 sections, guide cards expand inline, video cards open a Loom-placeholder modal.
  - `/limits` — Current plan summary with usage progress bars (gold @80%, red @95%), In-scope/Out-of-scope lists, SLA-by-plan table.
- **Settings → Workspace** — new "Plan limits & scope" link to `/limits`.
- **Onboarding Step 4** — new live Claude preview banner above the timeline: "Live preview: first 2 messages drafted by Aria using your product description". First two touchpoint cards get a gradient "AI PREVIEW" badge and ring; rendered_message shows the AI-generated copy referencing the founder's actual product (verified with a Pixelflow / Figma-to-React product). Regenerate button re-runs Claude on demand. Auto-fires on mount when product_description is non-empty.

**Verified (testing_agent_v3 iter30 + post-fix smoke screenshot)**:
- Backend 12/12 pytest pass (plans catalog/status/select/contact + touchpoint preview + Claude live call + role gating + cross-tenant isolation + trial idempotency).
- Frontend Playwright: all 5 new pages + 15 tutorial cards + 6 accordion rows + DIY/DWY/DFY cards + GenLeadAI wordmark on all 3 auth pages + sidebar entries.
- TrialBanner HIGH issue (didn't render for fresh signups) — RESOLVED by gating the fetch on `useAuth().user` change so the retry waits until axios has the X-Tenant-Id header. Re-tested: banner now correctly shows "Your free trial ends in 14 days." for a brand-new signup after onboarding completes.
- Claude live preview verified end-to-end: messages reference specific product details (e.g. "Are you looking to speed up your design-to-development workflow, or is there a specific pain point with your current Figma-to-React process?"). Token format `{{first_name}}` preserved correctly after explicit prompt instruction.

**Deferred to Session B**:
- Touchpoint execution engine (lead_touchpoint_log + scheduler + Claude runtime + Journey tab).
- `/admin/health` page with live service pings + Pre-Launch Checklist.

**Deferred to Session C** (depends on B):
- Graceful degradation (Claude timeout fallback / 360dialog retry / DB unreachable buffer) + `failed_message_log` collection.

## Iter 38 — Touchpoint Mapping Layer (Phase A · auto-template + Step 3B UI) (Feb 2026)

**Backend** (`/app/backend/routes/touchpoints.py` + `/app/backend/touchpoint_templates_seed.py`):
- 8 universal lead-journey templates seeded idempotently on import: `tpl_fast_conversion`, `tpl_warm_nurture`, `tpl_considered_sale`, `tpl_enterprise_track`, `tpl_urgency_led`, `tpl_high_intent_qualifier`, `tpl_abandoned_interest`, `tpl_standard`. Each touchpoint = `{index, day, hour, channel, message_type, aria_role, trigger, message_template}`. Channels: WhatsApp / Email / Call reminder / LinkedIn nudge. Roles: autonomous / alert_human.
- Auto-selection (`select_template`) priority: **industry override** (Events, Real Estate, E-commerce+B2C) → **market + cycle** (primary) → **deal_size** (secondary) → fallback Standard.
- New endpoints (all owner/admin gated where mutating):
  - `GET /api/touchpoints/templates` — read-only library (8 templates).
  - `GET /api/touchpoints/templates/{id}` — single template.
  - `GET /api/touchpoints/auto-select` — recommended template for the active tenant's onboarding answers, with `selection.reason`.
  - `GET /api/touchpoints/map` — active tenant's saved map (or `{map: null}`).
  - `POST /api/touchpoints/map` — save/replace. Validates channel/role/type, re-indexes 0..n-1, caps at 30 touchpoints. Used by both "Looks good — use this" and "Save my custom journey".
  - `POST /api/touchpoints/map/reset` — overwrites map with the auto-selected template; `is_customised=false`.
  - `DELETE /api/touchpoints/map` — clears the map (Aria falls back to no journey).
- Collections: `touchpoint_templates` (global), `workspace_touchpoint_maps` (tenant-scoped via `tenant_id`).

**Frontend**:
- New `TouchpointMappingStep` component (`/app/frontend/src/components/onboarding/TouchpointMappingStep.js`).
- `OnboardingWizard` now has **6 steps**: Business → Aria's Persona → Sales → **Lead Journey** → WhatsApp → Team.
- Step 4 (Lead Journey) auto-loads with the recommended template based on in-memory form state (no need to save onboarding first):
  - Header: "Aria has mapped your lead journey."
  - Gold-bordered badge: `📋 Template: <name> · N touchpoints · D-day journey`.
  - Read-only timeline: vertical scrollable card list. Each card shows channel pill (WhatsApp green / Email blue / Call orange / LinkedIn purple), day/hour label, message-type label, role pill (`Aria handles` blue / `Alert you` gold), 2-line message preview, trigger label.
  - Two primary CTAs: **Looks good — use this** (saves auto-template, `is_customised=false`) + **Customise my journey** (opens editor).
  - **Skip for now** ghost CTA advances to WhatsApp without saving a map.
- Customise editor: per-touchpoint row with up/down reorder, day+hour inputs, channel/type/role selects, message_template textarea, remove button. Bottom of panel: **Add touchpoint**, **Reset to recommended**, **Cancel** (reverts edits — fixed post-iter29 RCA), **Save my custom journey** (stamps `is_customised=true`).
- `is_customised` flag computed via structural diff against the recommended template (not just `editing` state) — survives Cancel-revert flow correctly.
- Wizard nav hides the generic Next button on Step 4 (component handles its own CTAs); shows "Choose to continue" / "Saved · advancing…" label instead.

**Verified (testing_agent_v3 iter29: backend 21/21 pytest pass, frontend Playwright 100%)**:
- Auto-select correctness across 6 industry+market+cycle scenarios.
- POST validation rejects invalid channels/roles/types, empty templates, >30 touchpoints.
- Role gating (sales_rep gets 403), cross-tenant isolation, reset/delete flows.
- E2E onboarding flow: fresh signup → 6-step wizard → Step 4 auto-shows Considered Sale → accept → advances to WhatsApp → backend GET returns saved map.
- Cancel-revert fix verified: 8 cards → customise → add row → cancel → 8 cards again → accept → `Journey activated` (not `Custom journey saved`).

**Phase B (deferred, next session):**
- `lead_touchpoint_log` instantiation on lead create.
- Async background loop firing due touchpoints, Claude runtime message generation via Emergent LLM key, send via 360dialog/Meta WhatsApp + Resend email.
- Lead drawer "Journey" tab — status icons + "Send now" override + "Pause Aria for this lead" toggle.
- Reply-detection pause + Closed-Won/Lost cancellation logic.
- Campaign-level touchpoint map override.

## Iter 37 — Real invite emails (Resend) + 360dialog WhatsApp as 2nd provider (Feb 2026)

**Backend** (`/app/backend/routes/tenants.py` + new `/app/backend/whatsapp_dispatch.py`):
- `POST /api/invitations` now sends a Resend-rendered HTML invite email (purple-gradient CTA, role blurb, expiry stamp) when `payload.email` is provided. Returns `{invite_full_url, email: {sent, id?, error?}}`. Doc captures `email_sent`, `email_send_count`, `email_last_sent_at`, `email_last_message_id`.
- `POST /api/invitations/{id}/resend` re-sends the invite email and increments the send counter. 400 on no-email invites, 409 on accepted/revoked, 410 on expired.
- `_frontend_origin(request)` resolves the invite URL host using FRONTEND_URL/APP_URL env → request.headers.origin/referer → BACKEND_URL fallback so emails always carry a clickable absolute URL.
- New WhatsApp provider config endpoints, all owner/admin-gated:
  - `GET /api/tenants/active/whatsapp` — returns `{provider, providers:{name:{phone_number, phone_number_id, configured, api_key_masked}}}`. Never returns plaintext keys.
  - `POST /api/tenants/active/whatsapp` — payload `{provider: meta|360dialog, api_key?, phone_number?, phone_number_id?}`. Encrypts api_key/access_token with Fernet (`ENCRYPTION_KEY` env), stores `api_key_last4` for masking. Switching providers without re-supplying api_key preserves the previously stored credential.
  - `DELETE /api/tenants/active/whatsapp/{provider}` — clears that provider's stored config; falls back to the other if any.
  - `POST /api/tenants/active/whatsapp/test` — live-tests credentials. 360dialog → `GET https://waba-v2.360dialog.io/health_status`. Meta → `GET graph.facebook.com/{ver}/{phone_number_id}`.
- New `whatsapp_dispatch.send_whatsapp_text(to_phone, body, tenant_id=None)` resolves the active tenant's provider and routes to either Meta Cloud API or 360dialog (`https://waba-v2.360dialog.io/messages` with `D360-API-KEY` header). Falls back to global env-based Meta when no tenant config exists; logs-only when neither is set.
- `server.py send_whatsapp_text` reduced to a thin shim around `whatsapp_dispatch`.

**Frontend**:
- `InviteTeamModal` — success view shows green `invite-email-sent-banner` "Invite emailed to {email}" when Resend confirms send. Toast variants for sent / failed / link-only.
- `PendingInvitesList` — each row with a stored email shows an "Emailed" badge + send count and a paper-plane re-send button (`invite-resend-{id}`) calling `POST /api/invitations/{id}/resend`.
- New `WhatsAppProviderSection` mounted in **Settings → Workspace** tab. Tabbed switcher between **Meta Cloud API** and **360dialog**, each with provider-specific inputs (token, phone_number_id, display number for Meta; api_key + sender phone for 360dialog). Save/Test/Remove buttons wired with success+error banners. Active-provider tab gets a green "●" dot when configured.
- All interactive elements stamped with `whatsapp-*` data-testids (per project convention).

**Verified (testing_agent_v3 — iter 28, 100% pass)**:
- Backend 17/17 pytest pass — Resend send + resend counter + role gating + WhatsApp Fernet encryption + provider switching + cross-tenant isolation + `whatsapp_dispatch` smoke (logged_only when unconfigured).
- Frontend Playwright e2e — invite modal Resend banner, pending list resend button, WhatsApp tabs, save/test/remove flow, masked-key UX.

**Operational notes**:
- Invite emails go via existing `RESEND_API_KEY` (already in env). Sender = `SENDER_EMAIL` env (default `onboarding@resend.dev`).
- Sandbox Resend mailbox `delivered@resend.dev` always returns 200 — useful for E2E without real delivery.
- 360dialog sender phone numbers must be already onboarded inside 360dialog Hub. Tenant just pastes their D360-API-KEY.

## Iter 36 — Tenant-aware ICP definition feeds Aria's Claude scoring (Feb 2026)
**Backend**:
- Added `icp_definition` to whitelisted tenant settings (`PATCH /api/tenants/active/settings`).
- `routes/ai.py /api/ai/score` now:
  - Tenant-scopes the lead lookup + update + activity insert (`tenant_id` filter).
  - Pulls `tenant.settings.icp_definition` + onboarding_config (business_name, industry, product_description, primary_market) and injects them into the Claude prompt.
  - System prompt personalises: "You are an expert B2B/B2C sales qualification assistant scoring leads for {business_name}."
  - User prompt explicitly shows "THIS BUSINESS'S ICP: {icp_definition}" so Claude's reasoning cites the tenant's own criteria.

**Frontend**:
- Replaced hardcoded `defaultValue` Workspace inputs with new `WorkspaceSettingsSection` component — read-only workspace name (pulled from `/api/tenants/active`), controlled ICP definition textarea with Save button + dirty-state detection + success/error toast.
- Removed old non-persisted "ICP Definition" field.

**Verified E2E (curl)**:
- Saved tenant-specific ICP ("Series A+ SaaS startups in India…") → AI score returned cold tier with reasoning *"Missing critical ICP qualification data… to assess fit against Series A+ SaaS startup criteria"* — proving tenant-specific injection works and Claude now genuinely uses each tenant's ICP, not a hardcoded one.
- Whitelist still rejects rogue keys (inherits from Iter 35 whitelist logic).

## Iter 35 — Demo video URL in Settings → embedded into EmptyDashboard (Feb 2026)
**Backend**:
- `PATCH /api/tenants/active/settings` — owner/admin patches whitelisted tenant-level settings (`demo_video_url`, `brand_accent_color`). Rogue keys silently dropped.
- Settings persist in `tenants.settings` JSON sub-document.

**Frontend**:
- New `DemoVideoSection` in Settings → Workspace tab — URL input + live preview iframe + auto-detect + save/clear buttons + inline success/error msg.
- `EmptyDashboard` now fetches `/api/tenants/active` on mount; if `settings.demo_video_url` is set, the "Watch 2-min demo" modal auto-embeds a `<iframe>` with autoplay. Converts share URLs → embed URLs for YouTube (`youtu.be/ID`, `youtube.com/watch?v=ID`), Loom (`loom.com/share/ID`), and Vimeo (`vimeo.com/ID`). Any other URL is passed through unchanged.
- Without a URL, falls back to the existing graceful placeholder ("Demo video not yet configured…").

**Verified (all PASS)**:
- Save → persists ✓
- Read back → matches ✓
- Rogue keys rejected ✓
- Clear → removes ✓
- Live preview iframe renders (Rick Astley test) ✓

## Iter 34 — P0 tenant scoping across critical endpoints (Feb 2026)
**Backend**:
- Added `_tf(current_user)` tenant-filter helper + `_stamp_tenant(doc, user)` writer helper in `routes/pietential.py`.
- Scoped `/api/pt/*` endpoints: leads list/get/create, companies list/get/patch, events list, tasks list/patch/delete/create, notes list/create, overview (all 25+ counters), reports weekly/monthly. All reads filter `tenant_id`; all writes stamp `tenant_id`.
- Hardened `_ensure_company()` to be tenant-scoped (lookup + insert).
- Scoped legacy server.py: `/api/aria/analytics`, `/api/aria/call-priority` (with `_compute_call_priority(tenant_id=...)` refactor).

**Verified isolation matrix (all PASS)**:
| View | /api/leads | /api/pt/overview | /api/pt/companies | /api/analytics/dashboard | /api/aria/analytics |
|------|-----------|------------------|-------------------|-------------------------|---------------------|
| Demo tenant | 88 | 0 | 0 | 88 | 30 |
| Pietential tenant (X-Tenant-Id header) | 0 | 1 | 1 | — | — |
| Fresh signup | 0 | 0 | 0 | 0 | — |

**Known remaining gaps (lower priority — not in current UI's critical path)**:
- `/api/pt/tasks POST` (stamped but verify write); /api/pt/training/signals, /api/pt/touchpoints, /api/pt/automation/logs, /api/pt/integrations, /api/pt/saleshandy/activity, /api/pt/lemlist/activity — all still global reads (used on less-trafficked Pietential pages).
- `/api/aria-agent/*` reads in `aria_agent_routes.py` — partially scoped; several still global.
- Legacy follow-ups + pipelines endpoints in server.py — still global.

## Iter 33 — Tokenized team invite flow (Feb 2026)
**Backend** (`/app/backend/routes/tenants.py`):
- New `invitations` collection.
- `POST /api/invitations` — owner/admin creates tokenized invite. Returns `{invitation, invite_url: /invite/<token>}`. Configurable role (admin/member/viewer) + expiry (1-90 days). Optional email pre-fill hint.
- `GET /api/invitations` — owner/admin lists pending/accepted/revoked invites for the active tenant.
- `DELETE /api/invitations/{id}` — owner/admin revokes a pending invite.
- `GET /api/public/invitations/{token}` — **unauthenticated** public endpoint returning safe invite info (tenant_name, role, inviter_name, expires_at, email_hint). Rejects expired/revoked/accepted.
- `POST /api/public/invitations/accept` — **unauthenticated**. Creates user (if new) + adds membership to inviter's tenant + marks invite accepted. Returns JWT + tenant so user lands logged in.
- Uses `secrets.token_urlsafe(24)` for tokens. Idempotent on re-accept (409 on already-accepted).

**Frontend**:
- New `InviteTeamModal` component (`/app/frontend/src/components/InviteTeamModal.js`) — role picker (Admin / Member / Viewer with descriptions), optional email, expiry dropdown. On create: shows copyable invite URL + one-click copy.
- New `PendingInvitesList` component (co-located) — shows all invites with active/accepted/expired/revoked status badges, one-click re-copy, one-click revoke (with confirm).
- Settings → Team tab: "Invite teammate" button (purple gradient) opens modal; `PendingInvitesList` below team members.
- New `/invite/:token` public route (`/app/frontend/src/pages/InviteAccept.js`) — renders "Join {workspace} as {role}" card, pre-fills email if hinted, collects name + email + password, calls accept endpoint, hard-reloads to dashboard. Graceful error UI for expired/revoked/invalid tokens (falls back to "Create your own workspace" CTA to `/signup`).

**Verified (curl, all PASS)**:
- Admin creates invite → returns token + URL.
- Public unauthenticated GET of invite returns safe metadata.
- Accept creates user + membership, returns JWT + tenant info.
- List shows invite as accepted after flow.

## Iter 32 — Public demo sandbox at /demo (Feb 2026)
**Frontend** (`/app/frontend/src/pages/DemoSandbox.js`):
- New public, read-only interactive dashboard sandbox at **`/demo`** that visually mirrors the real Dashboard.js layout (hero, KPI cards, ARIA Stories ring, Lead Feed with ARIA recommends boxes, Pipeline Mood card, Agent Activity feed, bottom CTA).
- Hardcoded realistic sample data — 8 leads, 4 ranked signals, 5 agent activity entries, 4 KPIs.
- Sticky "DEMO MODE — read-only sandbox" banner with "Start free" + close.
- Bottom CTA: "Your dashboard will look like this in 7 days" + "Start free" / "I have an account".
- No auth required, no API calls — bulletproof.
- Updated `EmptyDashboard.js` "Browse demo" link → `/demo` (was `/aria/demo-dashboard`).
- Existing `/aria/demo-dashboard` SEO marketing page kept untouched.

## Iter 31 — Empty state for fresh tenants + dashboard isolation (Feb 2026)
**Backend (tenant scoping)**:
- `routes/analytics.py /api/analytics/dashboard` — every count filtered by `tenant_id`. Fresh signups now get all-zero analytics; admin@demo.com still sees 88 leads.
- `server.py /api/leads/your-five-today`, `/api/leads/sleeping`, `/api/aria/feed` — all tenant-scoped.

**Frontend**:
- New `EmptyDashboard` component (`/app/frontend/src/components/EmptyDashboard.js`) — purple gradient hero with "Good {time}, {first_name}" + workspace name, 3 CTAs (Add lead / Import CSV / Watch 2-min demo), 3-step explainer cards, "What lights up" feature pills, "Browse demo" CTA, demo video modal (placeholder ready for Loom/YouTube embed).
- `Dashboard.js` short-circuits: when `analytics.total_leads === 0` → renders `<EmptyDashboard>` instead of the live widgets. No more fake "Sasha/Finley/Quinn" or "63 updates waiting" for new signups.

**Verified**:
- Fresh signup E2E → empty dashboard renders correctly (screenshot confirmed).
- admin@demo.com → real demo data still visible (no regression).

## Iter 30 — Multi-tenant SaaS Phase 2 (data isolation + tenant switcher) (Feb 2026)
**Backend**:
- `deps.get_current_user` now resolves active tenant from `X-Tenant-Id` header (fallback: user's primary membership) and attaches `tenant_id` + `tenant_role` to the user dict.
- Auto-migration on startup (`server.py`) — runs `scripts/migrate_to_multi_tenant.py` idempotently every boot. Production-deploy safe.
- Defensive: `get_active_tenant` auto-provisions a personal tenant for any user lacking membership (legacy account safety net).
- `/api/auth/register` (legacy single-tenant) returns **410 Gone** with pointer to `/api/auth/signup`. Signup is now the only funnel.
- Tenant scoping applied to: `POST/GET/PATCH/DELETE /api/leads`, `POST /api/leads/bulk`, `GET /api/leads/{id}/activities`, `POST /api/activities`, `POST/GET /api/campaigns`, `GET /api/campaigns/{id}` — all reads filter `tenant_id`, all writes stamp `tenant_id`.
- `aria_agent_routes.workspace/ask-reply/{lead_id}` Claude prompt now reads `onboarding_config.business_profile + aria_persona + sales_process` — Aria's drafts customise based on tenant onboarding answers (industry, business name, tone, language, product).

**Frontend**:
- New `TenantSwitcher` in Layout — fetches `/api/tenants/me`, renders dynamic dropdown for multi-tenant users (admin@demo.com sees "GenLeadAI Demo · Owner" and "Pietential · Owner"), static name for single-tenant users. Switching writes `active_tenant` to localStorage which is auto-forwarded by the axios interceptor.
- `/register` route now redirects to `/signup`.

**Verification (curl, all PASS)**:
- admin@demo.com on default tenant → 88 leads (ten_demo).
- admin@demo.com with `X-Tenant-Id: ten_pietential` → 0 leads (correct, isolated; pt_leads collection is separate).
- Fresh signup → 0 leads (fully isolated from demo data).
- POST /api/auth/register → 410.
- /register → /signup redirect verified in browser.
- Tenant switcher dropdown verified in dashboard screenshot.

## Iter 29 — Multi-tenant SaaS foundation Phase 1 (Feb 2026)
**Backend**:
- New `routes/tenants.py` with `tenants`, `tenant_memberships`, `onboarding_config` collections.
- `POST /api/auth/signup` — public self-service signup, creates user + tenant + owner membership.
- `GET /api/tenants/me` — list user's tenants. `GET /api/tenants/active` — current tenant + role + onboarding state.
- `GET /api/onboarding/status`, `POST /api/onboarding/complete`, `GET /api/onboarding/aria-config` — per-tenant onboarding (replaces legacy per-user). Legacy `/api/onboarding/{status,complete}_legacy` retained for back-compat.
- `get_active_tenant` dependency resolves tenant via `X-Tenant-Id` header (or user's primary tenant if absent). Used by all multi-tenant routes.
- `require_tenant_role([...])` factory for role guards.
- Migration script `scripts/migrate_to_multi_tenant.py` — idempotent, backfilled 308 docs into `ten_demo` (legacy ARIA collections) and `ten_pietential` (pt_* collections); admin@demo.com made owner of both; sarah/james members of demo only; marked both tenants `onboarding_completed=true` with sane defaults.
- `POST /api/auth/change-password` (Iter 28 Security tab) carried forward.

**Frontend**:
- `Signup.js` page (`/signup`) — workspace name + full name + email + password → calls `/api/auth/signup` → routes to onboarding.
- `OnboardingWizard.js` rebuilt — 5 steps: Business Profile, Aria Persona, Sales Process, WhatsApp, Team. Editable pipeline stages, multi-select qualification, tone & fallback pickers. Submit hard-reloads to `/` to bypass any stale gate state.
- `ProtectedRoute` enhanced — fetches `/api/onboarding/status` per route mount, redirects to `/onboarding` if tenant not onboarded. `/onboarding` route uses `requireOnboarded={false}` to avoid loop.
- `AuthContext.signup()` — stores `active_tenant` in localStorage post-signup.
- `config/api.js` interceptor — auto-sends `X-Tenant-Id` header from `active_tenant`.

**Test status**:
- Backend: 7/7 endpoints curl-verified (signup → list tenants → switch via header → onboarding status/complete → aria-config). Migration: 308 docs tagged.
- Frontend: end-to-end E2E PASS — signup → 5-step wizard → submit → Dashboard renders for new user "e2e_*" with their workspace name.
- Known gap (Phase 2): legacy `/api/leads`, `/api/conversations`, `/api/campaigns`, `/api/aria-agent/*` endpoints not yet tenant-scoped on read — new tenants currently see the demo data. Pietential `/api/pt/*` not yet scoped either. Phase 2 will add `tenant=Depends(get_active_tenant)` + `{tenant_id: tenant["id"]}` filter to every read/write.

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


## Iter 33 — Aria Confidence Dial complete (Feb 2026)
**Backend** (`/app/backend/routes/aria_confidence.py`, already shipped):
- `GET /api/aria/confidence/{lead_id}` and `POST /api/aria/confidence/batch` compute a 0–100 composite score per lead combining: 60% ICP fit, 25% touchpoint engagement (paused-on-reply = strongest signal), 15% recency (7d/14d), and stage bonus/penalty.
- Returns `{score, color (green|yellow|red), label (hot|warm|cold), factors[]}`. Batch capped at 200 IDs.

**Frontend**:
- New reusable `AriaConfidenceDial.js` SVG ring gauge (sm/md/lg sizes) with hover tooltip listing top factors.
- `LeadDetail` header renders `size="lg"` dial alongside the lead identity (prior session).
- **NEW (this iter)**: `LeadInbox` table now has an "Aria" column; batch-fetches scores via `useEffect([leads])` and renders a `size="sm"` dial in each row (testid `aria-cell-{lead_id}`). Empty/loading colSpan bumped to 10.

**Backlog (P1 next from Master Build Spec — Session C/D/E)**:
- Stale Lead Engine background job + Pipeline Health Score gauge on Dashboard
- Sentiment detection on inbound messages + sentiment-aware responses
- Conversations page (`/conversations`) with take-over flow + urgent-leads-pinned-top
- Graceful degradation: `failed_message_log` collection + retry queue
- Reports page rebuild (funnel, source perf, PDF export)
- Lead source attribution (`source_type`, utm_*, `needs_review`)
- Embeddable Lead Capture widget + Settings → Notifications tab
- Master Admin panel (`/master-admin`) + Pre-launch checklist


## Iter 34 — Sprint 1: Master Admin Revenue Panel (Feb 2026)
**Architecture decision**: User submitted a Supabase/BullMQ/Node spec; translated 1:1 to FastAPI + MongoDB per existing stack constraints. RLS replaced by `role=='admin'` master gate (tenants table is already tenant-scoped).

**Backend** (`/app/backend/routes/admin_revenue.py` — single file, 450 lines, lint clean):
- Collections (new): `subscriptions`, `payments`, `invoice_sequence` (per-year counter).
- Auto-provisions a subscription record per tenant on first read; idempotent.
- 11 endpoints under `/api/admin/revenue/*` + `/api/admin/invoices/{id}/pdf`:
  - `GET /summary` — 6 KPIs (MRR/ARR/paying clients/active trials/trial→paid %/monthly churn %) + month-over-month trend deltas.
  - `GET /by-plan?months=6` — Recharts BarChart data (DIY/DWY/DFY stacked).
  - `GET /subscriptions` — list w/ filters (status, plan, search).
  - `PUT /subscriptions/{tenant_id}` — change plan, custom_price, notes, status; mirrors plan back to `tenants.plan`.
  - `POST /subscriptions/{tenant_id}/extend` — +30 day trial extension (also bumps `tenants.trial_ends_at` when on trial).
  - `POST /subscriptions/{tenant_id}/cancel` — with reason enum (price/no_longer_needed/competitor/support_issue/other).
  - `GET /payments` — payment history list.
  - `POST /payments/manual` — record manual payment + auto-generate INV-YYYY-NNNN + advance period 30 days.
  - `GET /churn` — 12-month line series + 6-cohort retention table + churned accounts list.
  - `GET /trial-funnel` — 5-stage funnel (Signups → Onboarded → WA connected → First lead → Converted) with tenant lists per stage + "expiring soon (≤3 days)" list with onboarded/WA/lead-count badges.
  - `GET /invoices/{payment_id}/pdf` — reportlab-rendered PDF with GenLeadAI / Shillong, Meghalaya / GSTIN `17BVKPA9777N1ZP` / GST 18% breakdown / sequential invoice number.

**Frontend** (`/app/frontend/src/pages/MasterAdmin.js` + `/app/frontend/src/components/admin/RevenueTab.js`):
- New `/master-admin` route, owner-gated by `user.role === 'admin'` (else access-denied screen).
- New sidebar section "PLATFORM" with Master Admin link (only renders for admins, gold accent).
- Tabbed layout: Revenue (active), Security / Workspaces / Platform Settings (disabled placeholders for Sprint 2/3).
- Revenue tab sections: KPI row (6 cards) · Revenue by Plan bar chart · Subscriptions table + Manage modal (plan change / custom price / extend / cancel with reason / notes) · Payment history table + Add Manual Payment modal (auto-PDF download) · Churn line + retention cohort + churned accounts · Trial pipeline funnel with clickable stages + expiring-soon list.

**Testing** (iter_33): 19/19 backend pytest + 100% frontend e2e via testing agent. New regression file `/app/backend/tests/test_iter33_master_admin_revenue.py`. No critical issues.

**Next (Sprint 2)**: CRM Integration Core — `crm_integrations` + `crm_sync_log` schema, HubSpot OAuth connector, sync event engine (14 event types via asyncio queue), Take-over/Resume reflection flow, Lead Detail CRM status badge, Pipedrive API-key connector.


## Iter 34/35 — Sprint 2: CRM Integration Layer (Feb 2026)
**Architecture**: Aria is the engagement layer, CRM is the system of record. Every meaningful lead state change fires a sync event into `crm_sync_log` → asyncio background loop dispatches to the workspace's connected CRM. One active integration per tenant.

**Backend** (`/app/backend/routes/crm_sync.py` — 480 lines, lint clean):
- Collections (new): `crm_integrations`, `crm_sync_log`. Leads gain `crm_contact_id`, `crm_deal_id`, `crm_last_synced_at`, `crm_contact_deleted` (lazy-set by engine, no migration).
- 5 connectors implemented as real HTTP calls (httpx async): **HubSpot v3** (contacts/notes/stage), **Pipedrive v1** (persons/notes), **Custom Webhook** (POST JSON), **Zoho** + **Salesforce** (auth scaffolding, dispatch stubbed pending OAuth creds).
- 15 event types fully wired: `lead.created`, `lead.stage_changed`, `lead.qualified`, `lead.assigned`, `aria.paused`, `aria.resumed`, `conversation.takeover`, `meeting.booked`, `lead.closed_won`, `lead.closed_lost`, `sentiment.negative`, `sentiment.urgent`, `touchpoint.sent`, `lead.re_engaged`, `lead.data_deleted`.
- Async background loop `crm_sync_loop()` polls pending entries every 5sec (`CRM_SYNC_INTERVAL_SECONDS`), max 3 retries, status transitions pending→retrying→failed/success. Updates `leads.crm_contact_id` on first success.
- Endpoints under `/api/crm/*`: `GET /integrations`, `POST /connect`, `DELETE /disconnect`, `GET|PUT /field-mapping`, `PUT /sync-rules`, `POST /test-connection`, `GET /sync-log`, `POST /sync-log/{id}/retry`, `POST /sync-log/retry-all-failed`, `GET /leads/{id}/status`, `POST /inbound/{workspace_id}` (CRM → Aria bidirectional), `GET /oauth/{crm}/start` (HubSpot/Zoho/Salesforce authorize URL builder with `placeholder=true` when client IDs unset).
- `fire_event(tenant_id, lead, event_type, payload)` imported into `server.py` and wired into:
  - `POST /api/leads` → `lead.created`
  - `PATCH /api/leads/{id}` with status change → `lead.closed_won` | `lead.closed_lost` | `lead.stage_changed` (whitespace/dash normalized: "Closed Won" → "closed_won").
  - `POST /api/aria/takeover/{id}` → fires both `conversation.takeover` + `aria.paused` with rep name + last message.
  - `POST /api/aria/resume/{id}` → `aria.resumed`.

**Frontend**:
- `/app/frontend/src/components/CrmSettingsTab.js` — Settings → CRM tab end-to-end UX: empty state (5 CRM picker cards: HubSpot/Pipedrive/Zoho/Salesforce/Custom Webhook) → ConnectPanel (OAuth-paste-token or API key or Webhook URL) → connected state with header status row (Test Connection, Disconnect) + sub-tabs (Field Mapping editor with 10 default mappings, Sync Rules grouped in Lead lifecycle / Aria activity / Signals, Sync Log table with status filter + Retry + Retry-all-failed).
- `/app/frontend/src/components/CrmSyncBadge.js` — reusable lead-level badge (compact + full variants) — green "Synced to {CRM} · 2m ago" / yellow "Sync pending" / red "Sync failed · retry". Hidden when no CRM connected.
- `LeadDetail.js` — CrmSyncBadge rendered next to lead identity chip.

**Testing**:
- iter_34: 25/26 backend, 100% frontend. One bug found: stage "Closed Won" (with space) was firing `lead.stage_changed` instead of `lead.closed_won` due to whitespace-vs-underscore mismatch.
- Fix: normalize `lower().replace(' ','_').replace('-','_')` before comparison.
- iter_35 regression: 4/4 pass — both space and underscore variants now correctly mapped. Final: **26/26 backend + 100% frontend**.

**Known limitations (intentional per user spec)**:
- HubSpot/Zoho/Salesforce OAuth client IDs not set in env → OAuth authorize URLs return `placeholder=true`; users can paste a personal access token to connect in test mode.
- Zoho + Salesforce dispatchers return stub success (real REST calls deferred until credentials are added).

**Next (Sprint 3)**: Security & Compliance — Fernet encryption for stored CRM credentials, webhook signature verification, rate limiting, audit log, DPDP-compliant lead deletion, Privacy/Terms/DPA static pages, nightly retention jobs, Security settings tab, Data export.


## Iter 36 — Sprint 3 + Master Admin Completion (Feb 2026)
User direction: "do a + c in one session, then do the rest" → security primitives + audit + DPDP + Master Admin Workspaces / Pre-Launch / Platform Stats / Trial Expiry shipped together.

**Backend** (3 new files, all lint clean):
- `/app/backend/security/encryption.py` — Fernet helper with `encrypt() / decrypt() / encrypt_dict() / decrypt_dict()`. Idempotent + graceful fallback for legacy unencrypted values. Uses `APP_SECRET_KEY` env (stable dev fallback). Wired into `crm_sync.py` for credential storage.
- `/app/backend/routes/audit_log.py` — append-only audit log + `audit_write(tenant_id, user, action, resource_type, resource_id, metadata, request)` helper (fire-and-forget, never raises). Endpoints: `GET /api/audit-log`, `GET /api/audit-log/export.csv` (Owner/Admin only). Also houses Master Admin `/api/admin/workspaces/*` endpoints: list/detail, extend-trial, launch-checklist (13 items in 5 groups), mark-launch-ready, platform stats (9 counters), trials expiring. 24 known action types pre-registered.
- `/app/backend/routes/data_deletion.py` — DPDP Act 2023 compliant `POST /api/leads/{id}/delete-personal-data` (mode: anonymise|hard). Anonymise: name→"Deleted User", phone→`[REDACTED-{id}]`, opted_in=false, conversations cleared, activities redacted. Hard: full purge across leads/conversations/activities/touchpoint_log. Both write `data_deletion_log` (kept 7y for legal) + audit row `lead.data_purged`.

**Server.py**:
- Imports & registers 3 new routers + `slowapi` Limiter (registered globally; per-endpoint `@limiter.limit` decorators can be added later without breaking).
- CRM `connect`/`disconnect` endpoints now write audit log rows.

**Frontend** (3 new components + 3 legal pages):
- `/app/frontend/src/pages/legal/Legal.js` — Privacy / Terms / DPA exports, public routes `/privacy`, `/terms`, `/dpa`. Branded GenLeadAI dark theme. Includes DPDP-required sections (Data Protection Officer, sub-processors, retention, breach notification 72h).
- `/app/frontend/src/components/admin/WorkspacesTab.js` — Platform Stats grid (8 cells) + Trials Expiring panel (+ extend-7-days action per row) + All Workspaces table (search/plan filter/refresh) + ChecklistModal (13-item grouped checklist with force-mark-launch-ready).
- `/app/frontend/src/components/AuditLogPanel.js` — Audit log table with action filter, expandable metadata, CSV export. Rendered inside Settings → Security tab.
- `/app/frontend/src/components/DpdpDeleteButton.js` — Delete button + modal on Lead Detail. Anonymise (recommended) vs Hard delete radios. Reason dropdown + "type DELETE to confirm" gate.

**MasterAdmin.js**: Workspaces tab now enabled (was placeholder).

**Testing** (iter_36): **21/21 backend pytest pass (100%)**, frontend ~95% pass. `/app/backend/tests/test_iter36_sprint3_security.py` covers Fernet encryption round-trip, audit log RBAC + CSV export, DPDP anonymise/hard/403/404/400, all 8 master-admin endpoints. No critical/minor bugs. Two optional action items: (1) APP_SECRET_KEY env var not set in preview (using dev fallback — set before production), (2) testid naming "platform-stats" vs "platform-stats-grid" cosmetic.

**Still pending from Master Spec (parked for later sprints per user direction "do the rest")**:
- Phase 3.3 — Conversations page (`/conversations`) with take-over UI + urgent floats top
- Phase 3.5 — Stale Lead Engine (daily asyncio job) + Pipeline Health Score gauge on Dashboard
- Phase 3.6 — Sentiment detection on inbound messages + sentiment-aware response generation
- Phase 5.5 — Graceful degradation (Claude/360dialog fallback) + `failed_message_log` retry queue
- Phase 5.1 — Reports page rebuild (funnel + source perf + PDF export)
- Phase 2.1 — Touchpoint document upload (PDF/Excel/DOCX → Claude → preview table) + version history
- Phase 3.2 — Embeddable Lead Capture widget
- Sprint 4 — Real OAuth callbacks for HubSpot/Zoho/Salesforce + Historical sync on first connect + Reports Sync Log UI improvements
- Nightly retention jobs · webhook signature verification · @limiter.limit decorator applications · Data export ZIP · session management UI (placeholders only currently)


## Iter 37 — Sprint 4: Touchpoint Mapping Phase C (Feb 2026)
Master Spec Phase 2.1 completion — augments the existing onboarding step with post-onboarding power features.

**Backend** (`/app/backend/routes/touchpoints.py` extended in place):
- `MAX_TOUCHPOINTS` raised 30 → 32 (matches Master Spec)
- `_snapshot_version()` writes to new `touchpoint_map_versions` collection BEFORE every save; prunes to 5 most recent per tenant
- New endpoints: `GET /api/touchpoints/map/versions`, `POST /api/touchpoints/map/versions/{id}/restore`, `POST /api/touchpoints/import-document` (multipart PDF/DOCX/XLSX up to 10MB → pypdf/python-docx/openpyxl → Claude sonnet-4.5 → normalized preview JSON, 32-cap with `truncated:true`)
- Audit events fired: `touchpoint_map.updated`, `touchpoint_map.restored`, `touchpoint_map.imported_from_document`

**Frontend** (`/app/frontend/src/pages/TouchpointJourney.js` — new page `/touchpoint-journey`):
- Timeline view (horizontal scrollable cards) + Edit view (day/hour/channel/type/role/condition + token chips + move/duplicate/delete)
- 32-cap counter (gold @ 28, red @ 32) + warning chip
- `TemplateLibraryModal` (8 templates with preview+replace), `VersionHistoryModal` (5-version restore), `DocumentUploadModal` (3-stage upload→parsing→preview)
- New sidebar nav link "Touchpoint Journey"

**Testing** (iter_37): **17/17 backend pytest pass (100%)**, **100% frontend** — all testids present, no bugs. Regression file: `/app/backend/tests/test_iter37_touchpoint_sprint4.py`.
**Deps added**: python-docx 1.2.0, openpyxl 3.1.5.
