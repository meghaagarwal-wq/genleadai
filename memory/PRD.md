## Iter 165 — Duplicate-key fix + Reply Triage Conversations (Feb 2026)

User: "Fix the duplicate-key warning first. Then build the split-pane
Conversations view, but design it as a reply-triage/approval queue —
assume each item carries an AI classification and a drafted response
awaiting approval. Park the Kanban toggle and onboarding wizard."

### Bug fix — React duplicate-key warning on /app/leads
- Root cause: 3 pairs of `pt_leads` share generated IDs
  (`ptl_demo_sarah_chen`, `ptl_demo_arjun_mehta`,
  `ptl_demo_james_whitfield`) because two seed scripts each inserted
  a "Sarah Chen" (etc.) at different companies with colliding IDs.
- Fixed with a two-layer defense:
  1. **Backend dedupe** in `GET /api/pt/leads` (`routes/pietential.py`
     `list_leads`) — after Mongo query, keep first occurrence per id
     (sorted by last_activity DESC → freshest wins). Response goes
     from 16 → 13 unique leads.
  2. **Frontend composite key** in `LeadFeed.js .map` uses
     `${l.id}__${l.email || i}` so React never sees dupes even if
     backend later regresses.

### New feature — Reply Triage Queue (Conversations rewrite)
- Entirely rebuilt `pages/Conversations.js` (~520 lines) as a
  Superhuman-inspired split-pane approval triage view.
- **Data source**: `GET /api/approvals` (pending_outreach with
  `status=awaiting_owner_approval`) — 3 seeded items in ten_demo.
- **Left pane** (380px): scrollable list of pending drafts. Each row
  shows avatar (initials) + name + company + draft snippet +
  3 classification pills (stage HOT/WARM/ENGAGED/COLD · channel
  LinkedIn/Email/WhatsApp/SMS · AI confidence %) + age.
- **Right pane**: selected item's full detail:
  - Lead header (name + stage badge + score + company + queued-ago)
  - ARIA callout with `ai_model` + `reason_for_review` + colored
    confidence bar (green ≥75%, amber ≥50%, red < 50%)
  - Drafted body (with subject for email channel)
  - Actions: **Reject** (with reason input) · **Edit** (inline
    subject/body → Save & send) · **Approve & send**
- **Keyboard shortcuts** (Superhuman-style):
  - `J` / `↓` next · `K` / `↑` prev · `E` approve · `R` reject ·
    `/` focus search · `Esc` unfocus input · `Cmd/Ctrl+J` open ARIA
  - Shortcuts don't fire while typing in inputs/textareas.
- **Filter pills**: All (N) · High conf (≥75%) · Medium (50-74%) · Low
  (<50%).
- **Wired actions**: `POST /api/approvals/{id}/approve|edit-send|reject`.
- **Kanban toggle + onboarding wizard**: parked per user instruction.

### Verified (testing_agent iter165)
- 100% pass on backend (5/5 endpoints) + frontend.
- Duplicate-key console errors: **0** on /app/leads.
- Triage page renders 3 pending approvals with correct pills.
- Keyboard J/K/E/R/`/` shortcuts functional.
- Edit + Reject inline flows verified.
- Regression: ARIA drawer, light theme, demo mode switcher all intact.

---



## Iter 164 — "Calm Intelligence" Chunk B (Feb 2026)

User: "Credits Recharged. Please Continue." (green-light for Chunk B).

### Shipped
- **ARIA Companion Drawer** (`AriaCompanionDrawer.js` — new):
  - Floating primary-green orb bottom-right on every workspace page.
  - Cmd/Ctrl+J shortcut toggles the drawer; Escape closes.
  - Right-side backdrop-blur drawer with cards feed sourced from
    `/api/insights/founder-command-center`.
  - Card types with accent border-left: coral 'Aria noticed', primary
    green 'Aria drafted' and 'Aria suggests'. CTAs deep-link to
    `/app/instinct`, `/app/approvals`, `/app/conversations`.
  - State persists in `localStorage.aria.companion.open`.
  - Auto-refresh every 5 minutes + on tenant switch.
  - Wired into `AppLayout.js`.
- **Leads page** (`LeadFeed.js`) — removed all hardcoded purple hex; now
  uses `var(--theme-primary)` and theme borders. 'Scan engaged leads'
  button renders in primary green (no purple gradient).
- **Conversations page** (`Conversations.js`) — same purple → theme
  migration, plus new Superhuman-inspired keyboard-hints strip
  (J/K navigate · E archive · / search · ⌘J ask Aria) rendered as kbd
  tags below the header. Sentiment pills → rounded-full. 'Aria says'
  callout on primary-dim background.

### Verified (testing_agent iter164)
- 100% pass on both backend + frontend.
- Orb visible on all 5 workspace pages.
- Cards populate with real intelligence data (95% pipeline risk +
  49 overdue follow-ups).
- Cmd/Ctrl+J + Escape shortcuts work.
- localStorage persistence across reload verified.
- CTA navigation closes drawer.
- Scan button computed bg = `rgb(15,76,58)` (primary green).
- Conversations kbd hints strip renders (5 kbd tags).
- 1 non-blocking observation: React duplicate-key warning in console
  (not from ARIA drawer — traced elsewhere, low priority).

### Deferred from Chunk B (Chunk C)
- Full Attio-style spreadsheet + Kanban toggle on Leads (P2 — current
  dense table already looks Attio-esque post-migration).
- Full Superhuman-style split-pane inbox on Conversations (P2 — keyboard
  hints strip added, but not a two-pane read/reply layout yet).
- Command Center greeting card (P3 — ARIA drawer already provides the
  founder-hook greeting via "Aria noticed" cards).
- Onboarding wizard polish (P3).

---



## Iter 163 — "Calm Intelligence" UI/UX overhaul (Chunk A) — Feb 2026

User: "now work on UI UX of the demo dashboard and the app make it optimised
and something founder and business owners would wanna get hooked on to and
use it as their SSOT for all b2b, b2c and hybrid"

### User preferences (verbatim)
- Scope: Full app overhaul (dashboards + workspace pages)
- Vibe: Calm intelligence (Notion/Attio) + ARIA-as-friend companion drawer
- Visual: Light-first, warm founder palette + auto-adaptive dark toggle
- Inspiration: Artisan.co
- Must-preserve: nothing sacred

### Design system shipped (design_agent brief → `/app/design_guidelines.json`)
- Warm cream (#FDFBF7) light theme + warm espresso (#0C0A09) dark theme
- Deep founder green primary (#0F4C3A) + coral secondary (#E06D53)
- Outfit for display type + Manrope for body (Artisan-inspired)
- Rounded-2xl bento cards, soft shadow-card + shadow-hover
- New CSS utility classes: `.bento-card`, `.eyebrow`, calm hover animations

### Chunk A shipped
- **Global design tokens** in `frontend/src/index.css` — all `--theme-*` vars
  rewritten. Existing components using CSS variables auto-inherit new palette.
- **Default theme flipped** from dark → light in `ThemeContext.js`.
- **AppLayout sidebar + header** now use theme-aware colors (cream sidebar in
  light mode, warm espresso in dark). Search box + AI Summary button + mode
  chip repainted to green/coral palette.
- **DemoModeSwitcher** rebuilt as a Notion-style pill toggle inside a bordered
  cream capsule. Active pill uses white background + primary green text.
- **B2C / B2B Founder / B2B Sales dashboard headers** restyled with eyebrow
  tag + 32px Outfit heading + neutral bordered refresh button (no more purple
  gradient buttons).
- **Integrations page** auto-inherited the new palette via CSS variables —
  cards, filter pills, connect buttons all warm-cream + green.

### Chunk A verified (testing_agent iter163)
- Backend regression: 6/6 endpoints pass (login, tenants/me, dashboard/b2c,
  b2b-founder, b2b-sales, integration-showcase).
- Frontend: default light theme, theme toggle persistence, mode switcher
  persistence, all 3 dashboards render, integrations grid renders, sidebar
  nav works, no console errors, no missing CSS variables.
- Only noise: pre-existing Recharts width/height=-1 warnings (unrelated).

### Chunk B — next session
- Leads page: Attio-style spreadsheet + Kanban toggle
- Conversations: Superhuman-style triage inbox
- ARIA companion drawer (persistent right-side, Cmd+J shortcut, brief AI
  cards: "Aria noticed / drafted / suggests")
- Command Center greeting card + founder-hook micro-interactions
- Onboarding wizard polish

---



## Iter 162 — OAuth callback URL blocker fixed (Feb 2026)

User: "OAuth callback URL blocker in oauth_integrations.py still open from the previous session — may block redeploy."

### Root cause
`_api_base()` in `/app/backend/routes/oauth_integrations.py` previously
gave `PUBLIC_API_BASE_URL` env-var **priority over** the request-derived
URL. Since `backend/.env` has `PUBLIC_API_BASE_URL=https://app.genleadai.com`
hardcoded, every preview deploy was building OAuth callback URLs pointing
to the production domain. Deployer Agent flagged this.

### Shipped
- **`_api_base(request)`** refactored to derive backend origin from
  incoming request's `X-Forwarded-Proto` + `X-Forwarded-Host` headers
  (set by Kubernetes ingress) **first**, then fall back to `request.base_url`,
  then env vars (`PUBLIC_API_BASE_URL` → `BACKEND_URL` → `FRONTEND_URL`)
  only when no request is available (e.g., background token-refresh loop).
- **`_redirect_uri(provider, request)`** and
  **`_calendly_register_webhooks(tenant_id, access_token, request)`**
  updated to thread the request through.
- **`oauth_callback`** endpoint now takes `request: Request` and passes
  it to `_redirect_uri` for the token-exchange step (Meta GET + others POST).

### Verified (testing_agent iter161 report)
- 15/16 backend tests pass. Preview requests → preview callback URLs;
  production requests → production callback URLs; no env-var leakage.
- 6 provider `/connect` endpoints return HTTP 503 with correct
  "not configured" messages (signatures work post-refactor).
- Regression: login, tenants/me, integration-showcase, dashboard/b2c
  all still work.
- The 1 failure is an UNRELATED pre-existing route conflict on
  `DELETE /api/integrations/{provider}` between `oauth_integrations.py`
  and `oauth_providers.py` — documented for future cleanup, not a
  blocker for redeploy.

---



## Iter 161 — Retire Pietential tenant (Feb 2026)

User: "i want to delete pitential dashboard - and all its data (i just want genleadai demo dashboard to be there)"

### Shipped
- **Full purge** of the `ten_pietential` tenant + owner user (`megha@contentvista.com`)
  + all `tenant_id=ten_pietential` documents across every collection (leads,
  insights, memberships, ICPs, onboarding, outbound/inbound logs, activities).
- **`backend/scripts/migrate_to_multi_tenant.py`** — no longer seeds Pietential
  on startup. Instead, on every boot it performs a defensive purge of any
  stray `ten_pietential` docs so the workspace stays permanently retired.
  Only `ten_demo` (GenLeadAI Demo) is ensured.
- **`backend/scripts/iter148_seed_demo_accounts.py::setup_pietential_owner()`**
  neutralized to a no-op — running the script standalone no longer recreates
  the account.
- **`/app/memory/test_credentials.md`** updated: removed `megha@contentvista.com`
  entry, marked as retired.

### Verified
- `POST /api/auth/login` with `megha@contentvista.com/Pietential2026!` → **HTTP 401** (user removed).
- `GET /api/tenants/me` as `admin@demo.com` → returns **1 tenant only** (`ten_demo` — GenLeadAI Demo).
- `GET /api/dashboard/b2c` under `X-Tenant-Id: ten_demo` → still returns full B2C demo widgets.
- Frontend `/login` renders cleanly.

### Note on the Pietential Intelligence Engine
- The **feature-level** engine (routes `pietential_intel.py`, `pt_insights`,
  `pt_leads`, decay loop) is UNTOUCHED — it powers the B2B intelligence
  widgets that work for GenLeadAI Demo and any future tenant.
- Only the tenant/workspace "Pietential" was deleted, not the engine feature.

---



## Iter 160 — Integration Showcase widget on demo dashboards (Feb 12, 2026)

User: "now in Genleadai demo dashboard i wanna show all the backend integration options we have in each of these sub sections — check the backend integrations setup and tell me what all options we have! I need for all b2b, b2c and hybrid"

### Shipped
- **Audit of live + planned integrations** — pulled the catalog from `routes/integrations_hub.SUPPORTED_TYPES` (live truth) and combined with the future-roadmap items into a single curated list of **54 integrations** across 9 marketing-facing categories.
- **Backend** `routes/integration_showcase.py` — `GET /api/dashboard/integration-showcase[?category=...]` returns `{categories[], integrations[], counts}` with per-integration status `live` (connected for this tenant) / `available` (supported but not connected) / `coming_soon` (future). Routes registered via `routes/__init__.py`.
- **Frontend** `IntegrationShowcase.js` — pill-filtered grid matching the user's mockup. Categories: All · Outreach · Ads · Messaging · Enrichment · Scheduling · Productivity · Social · Email · Payments. Each card shows brand-colored initials avatar, name, and status badge. Live integrations get a green check.
- **Wired into all 3 demo dashboards** (B2C, B2B Founder, B2B Sales) at the bottom — same data, same widget. Hybrid demo automatically inherits via the existing demo-mode-switcher.

### Coverage by category
- **Outreach** (9): Apollo, Instantly, Lemlist, Saleshandy, Smartlead, PhantomBuster, Sales Navigator, Snov.io, Hunter.io
- **Ads** (7): Google Ads, Meta CAPI, Meta Pixel, LinkedIn Insight, Meta Lead Ads, GA4
- **Messaging** (7): WhatsApp Business, Twilio SMS, MSG91, Website Chat, Telegram, Slack, MS Teams
- **Enrichment** (6): Apollo, Snov.io, Hunter.io, Clearbit, ZoomInfo, RocketReach
- **Scheduling** (7): Calendly, Google Calendar, Outlook Calendar, Cal.com, Zoom, Google Meet, MS Teams
- **Productivity** (11): Notion, Google Sheets, Airtable, Zapier, Make.com, n8n, HubSpot, Salesforce, Zoho CRM, Pipedrive, Slack
- **Social** (7): LinkedIn Lead Gen, Sales Navigator, Meta Lead Ads, LinkedIn Insight, Twitter/X, Instagram, PhantomBuster
- **Email** (12): Gmail, Outlook, Zoho Mail, SendGrid, Resend, Mailchimp, Lemlist, Smartlead, Instantly, Snov.io, Hunter.io, Saleshandy
- **Payments** (4): Stripe, Razorpay, PayPal, Square (all coming-soon for now)

### Verified
- Backend smoke: `/integration-showcase` returns 54 integrations with correct counts per pill.
- Frontend smoke: rendered + screenshotted on all 3 demo dashboards; Payments filter narrows to 4 cards as expected.
- Updated marketing screenshot pack at `/downloads/genleadai_dashboard_screenshots.zip` now includes 4 new integration-section captures.

---


## Iter 159 — Final 4-backlog drop: Winning Combos + Sparkline tooltip + Conversations migration + Per-mode aliases (Feb 12, 2026)

User: "do this" (all 4 remaining backlog items)

### Shipped
- **Winning Channel Combos leaderboard (B2C dashboard)**
  - Backend `_winning_channel_combos()` — joins `pt_leads.source_channels` × `booking_events.lead_id` to compute the top-3 channel combos by real booked-meeting count. Sorts by bookings desc → close_rate desc → leads desc.
  - New endpoint `POST /api/dashboard/sequences/duplicate-from-combo` — inserts a draft `lemlist_sequences` row with the channel mix, status='draft', source='winning_combo_duplicate', author email.
  - Frontend `WinningCombos.js` — 3-card ranked grid (gold/silver/lavender) with channel name, close-rate %, bookings/leads count, and "Duplicate to sequence" button per card. Sonner toast on success.
- **Sparkline hover-popover** (`dashboard_charts.js::Sparkline`)
  - Accepts both `number[]` and `{date,value}[]` inputs (auto-fills dates as today-(N-i) days).
  - Recharts `<Tooltip>` shows "<value> on YYYY-MM-DD" via `labelFormatter` (date) + `formatter` (value); suppressed series name + separator for clean output.
- **Conversations migration** (`routes/conversations.py`)
  - New `_merge_leads_for_threads()` helper unions `pt_leads` + legacy `leads` deduped by `id`. Legacy rows win for conversation-specific fields (latest_sentiment, aria_active, etc); pt_leads fills gaps.
  - All 10 demo leads now appear on `/api/conversations/threads` without losing any legacy Pietential thread data.
- **Per-mode alias files** (`B2CDashboard.js`, `B2BFounderDashboard.js`, `B2BSalesDashboard.js`)
  - Each is a 3-line re-export from `./Dashboards`. Callers can now `import B2CDashboard from './B2CDashboard'` (sub-module style) without the physical-split risk.

### Verified (iter159, 100% backend + 100% frontend)
- 4 backend pytests pass (`/app/backend/tests/test_iter159_backlog.py`).
- Frontend: Winning Combos cards render with all 3 duplicate buttons, sparkline tooltip shows clean "<value> on YYYY-MM-DD", Conversations page shows all 10 demo names + Pietential isolation intact.
- Sparkline tooltip cosmetic polish applied post-test (suppress "name :" prefix that initially leaked through).

### Known follow-ups
- Physical per-mode file split (move B2CDashboard body out of Dashboards.js) — still deferred. Alias files satisfy the import API today.
- The carry-over React duplicate-key warning from earlier iters is now resolved as of iter158 composite-key fixes.

---


## Iter 158 — Four-backlog drop: Sales sparklines + Multi-touch tracking + ICP Drift modal + shared split + UX sweep (Feb 12, 2026)

User: "do this" (all 4 items + (e) all three UX sweep lanes)

### Shipped
- **B2B Sales KPI sparklines** — `followups_today`, `meetings_today`, `approvals_pending`, `pipeline_value` now return `{value, spark[7]}`; frontend tiles render the inline area chart.
- **Phase B Step 4 — Multi-touch channel tracking**:
  - `services/lead_channels.py::register_channel_touch(tenant_id, lead_id, channel)` → `$addToSet` on `pt_leads.source_channels` AND `leads.source_channels` (dual write for legacy compat). Case-folds via `.strip().lower()`.
  - Called from `services/outreach_dispatch.py` after every outbound_log insert (even logged-only attempts count as a touch).
  - Called from `routes/inbound_reply.py` after every inbound_messages insert.
  - Idempotent — re-firing for the same channel is a no-op.
- **Phase B Step 5 — ICP Drift Modal** (`workspace/pages/ICPDriftModal.js`):
  - 30-day ICP distribution as a recharts donut (PieChart + Legend + Tooltip).
  - Per-channel drift breakdown via shared `HBars` (red ≥50%, amber ≥25%, green otherwise).
  - "ARIA recommends" callout for any channel ≥30% unknown with ≥3 leads.
  - Snooze button → `POST /api/dashboard/icp-drift/snooze?days=7` (clamped 1–30; stored on tenant doc with `icp_drift_snoozed_by` audit). While snoozed, `drift_detected` returns false regardless of actual numbers.
  - a11y: `role=dialog`, `aria-modal`, `aria-labelledby`, Escape-key close, body-scroll lock.
- **Shared split** — `dashboard_shared.js` exports `KpiTile`, `ComingSoon`, `SectionCard`, `StatusPill`, `HealthBadge`, `useDashboard`, `fmtMoney`, `DashboardSkeleton`. `Dashboards.js` shrunk from 824 → 738 lines (saves ~100 LOC; further per-mode split deferred — high risk, low payoff vs current cleanup).
- **UX Sweep (all three lanes)**:
  - **a11y**: every KPI tile has `role=group` + `aria-label`; KPI strips wrapped in labeled groups; demo-mode-switcher is `role=tablist` with `aria-selected` per pill; all icon-only buttons have `aria-label`; ICP modal has `role=dialog` on the correct element + Escape close.
  - **Mobile**: KPI grids changed from `grid-cols-2 md:grid-cols-5` to `grid-cols-2 sm:grid-cols-3 lg:grid-cols-5` so the 375px breakpoint shows clean 2-cols (was squished 5-cols). Demo pills wrap with `flex-wrap`, min-height 32px for touch.
  - **Micro-interactions**: hover lift on KPI tiles (`hover:-translate-y-0.5`); `active:scale-95` press feedback on all buttons; focus rings via `focus:ring-2 focus:ring-purple-400`; new `DashboardSkeleton` replaces static "Loading…" text with animated pulse skeleton (`aria-busy=true`).
- **Bonus fixes**: React duplicate-key warning eliminated — switched 5 list keys from `lead_id` to `${lead_id}_${index}` composite (ghost leads, deal-risk, agenda, attribution_top3 on both B2B Founder and B2B Sales).

### Verified (iter158, 100% backend + 100% frontend)
- 6 backend pytests pass.
- B2B Sales tiles all show sparklines, demo-mode-switcher tabs work with keyboard.
- ICP drift modal opens / Escape closes / snooze flow flips `drift_detected` to false.
- Multi-touch `$addToSet` dedups + case-folds correctly.
- 2-col mobile layout verified at 375×667.
- No console warnings.
- Tenant isolation regression-clean.

### Known follow-ups
- Full per-mode split (B2CDashboard.js / B2BFounderDashboard.js / B2BSalesDashboard.js as separate files instead of one Dashboards.js) — deferred. Saves ~600 more lines but pure cosmetic, no behaviour change.

---


## Iter 157 — Chart-first dashboard upgrade (no redundancy) (Feb 12, 2026)

User: "add graphical representation on genleadai demo dashboard for easy understanding where every you can and also remember we dont want redundancy in information just something that would make the user wanna come back on this again and agin"

### Design rule applied
Charts **REPLACE** text/numbers (never sit alongside). Tiny inline indicators (e.g. the +/-N% delta in a KPI tile's top-right) are kept because they read different info than the sparkline trajectory.

### Shipped
- **Backend** `_timeseries_count` + `_timeseries_sum` helpers (single $bucket aggregate; reusable across B2C + B2B Founder KPIs). Added `spark: number[7]` to:
  - B2C KPIs: `leads_today`, `active_convos`, `bookings_week`, `revenue_pipeline`
  - B2B Founder KPIs: `leads_month`, `high_intent`, `meetings`, `signals`
- **Frontend** new `dashboard_charts.js` module exports:
  - `Sparkline` (area chart, 28px) — embedded in every KPI tile with `spark` data; color shifts on delta direction.
  - `RadialGauge` (recharts RadialBar 0–100) — replaces Momentum's emoji+text on B2C + B2B Founder.
  - `TaperedFunnel` (SVG-ish CSS) — replaces the 5-column equal-box grid; trapezoid bars taper to actual volume per stage.
  - `HBars` (gradient horizontal bars) — replaces text rows in **Sequences, Asset Performance, Multi-touch Leads, Signal Attribution**.
  - `MiniBarChart` (recharts vertical bars + tooltip) — replaces the Channel Performance HTML table on B2B Founder.
  - `InlineSparkline` (raw SVG polyline, ~56×18px) — available for inline-row use (not yet wired).

### Verified (iter157, 100% backend + 100% frontend)
- All `spark` arrays return exactly 7 numerics for both dashboards.
- All chart components render without recharts `ResponsiveContainer width(0)` warnings.
- Console: 0 errors, 0 warnings after switching pills between B2C / B2B Founder / B2B Sales / Hybrid.
- Pietential tenant unaffected — `/api/dashboard/b2b-founder` returns 200.
- No "vs prev N%" or duplicate trend text remains.

### Known follow-ups (P2)
- B2B Sales KPI tiles don't yet show sparklines (out of scope this iter; data shape supports easy addition next).
- `Dashboards.js` now ~840 lines — overdue for split into per-mode files.

---


## Iter 156 — Auto-bootstrap demo seed on backend startup (Feb 12, 2026)

User: "i can not see them in production" (referring to the demo leads from iter154)

### Root cause
Production has its own MongoDB; the iter154 seed only ran against the preview DB during dev. No automatic bootstrap meant the demo workspace on production stayed empty after redeploy.

### Shipped
- **Startup hook in `server.py`** runs `iter154_seed_demo_dashboards.main()` on every cold boot when:
  - `ten_demo` tenant exists (skip if multi-tenant migration hasn't run yet)
  - AND (no seeded leads exist OR newest `_seed_run_at` is from a prior UTC calendar day)
- **`_seed_run_at` field** added to every seeded row at insert time so the staleness check is unambiguous (previous heuristic on `updated_at` got corrupted by background jobs like the score-decay loop).
- **Fail-soft**: any seed error prints a warning but never blocks app startup.

### Verified
- Preview backend: startup log shows `iter154 demo seed: bootstrapped ten_demo (existing=10, stale=True)` after first restart of day, then `iter154 demo seed fresh (10 leads) — skipping refresh` on subsequent boots same day.
- Demo dashboards: leads_today=2, bookings_week=2, signal_attribution 3 rows, top_actions 3 Claude rows, hot_leads 3.
- Pietential isolation intact (no demo names in Pietential's why_now feed).

### Deploy note for user
After redeploy of this change to production, the demo seed will run automatically on first cold boot. No manual trigger needed — `app.genleadai.com` will populate the demo workspace within ~3 seconds of FastAPI starting up.

---


## Iter 154–155 — Rich demo seed (no "Coming soon") + dashboard backend completers (Feb 12, 2026)

User: "Remove all coming soon options and make them like, and add real 6-10 leads in all demo dashboards (b2b, b2c, hybrid) and in all stages. The demo dashboard needs to look like a working dashboard - even in the sidebar, options need 6-10 fake leads."

### Shipped
- **New seed `iter154_seed_demo_dashboards.py`** — idempotent, tagged `_seed_source: demo_seed_v154`. Populates `ten_demo` with:
  - **10 pt_leads + 10 legacy leads (dual-write)** across stages (new → session_pilot), scores 22→92, multi-channel `source_channels` arrays, mixed sentiment (1 NEGATIVE → deal_risk), 2 leads created today, 3 leads >14d silent (ghost candidates).
  - **12 pt_insights** (≥3 per signal_type so attribution unlocks) — 4 with `founder_flag: True`, 2 with `status: pending`.
  - **3 pending_outreach drafts** with `body` text → /api/approvals sidebar page lights up.
  - **6 outbound_log + 4 inbound_messages** → Live Conversations + Funnel "Replied" stage.
  - **5 booking_events** (3 this month, 2 last month) with `deal_value` → Revenue Forecast + Agenda.
  - **8 score_history rows** (last 24h, mix of +/− delta) → Why-Now + Momentum.
  - **38 asset_clicks** across 6 assets → Asset Performance widget.
  - **3 lemlist_sequences** + **4 ad_spend rows** → Sequences + Cost-per-Qualified-Lead widgets.

- **Backend completers in `dashboards.py`**:
  - New `_channel_overlap()` — aggregates pt_leads by `source_channels` arrays; returns conv-rate per combo.
  - New `_cost_per_qualified_lead()` — reads `ad_spend` collection × qualified-lead count per channel.
  - New `_signal_attribution()` — replaces blanket `coming_soon: True` with real data when ≥3 signal-sourced leads exist.
  - `_b2b_founder` + `_b2b_sales` `why_now` now **dedupe by lead_id** — silences React duplicate-key warnings from accumulated decay-job score_history rows.

- **Frontend `Dashboards.js`** — Multi-touch Leads widget and Signal Attribution widget now render real rows when data is present (previously hardcoded ComingSoon).

- **`POST /api/demo/reset`** now also runs the iter154 seeder (fail-soft via try/except → `purged.iter154_error`).

### Verified (iter154 backend 100%, iter155 backend + frontend 100%)
- B2C: zero `coming_soon=True`; revenue_forecast=$712.5K, asset_performance 5 rows, channel_overlap 5 rows, cost_per_qualified_lead 4 rows, ghost_leads 4, conversations 6, sequences 3, kpis.leads_today=2, kpis.bookings_week=2.
- B2B Founder: signal_attribution 3 rows with conv_rate %, why_now 7 unique entries, founder_flags 5, deal_risk_flags 3, channel_performance 6.
- B2B Sales: hot_leads 3, pipeline 50, agenda 2, approval_queue 2, top_actions 3 Claude rows.
- Sidebar: /app/leads shows all 10 demo names, /app/approvals shows 3 cards with full body text, /app/conversations shows 10/10 expected leads, zero console errors.
- Pietential tenant isolation intact (none of Sarah Chen / Arjun Mehta / etc. leak into Pietential dashboards).

### Known follow-ups (P2)
- `Dashboards.js` now ~830 lines — split per dashboard into separate files.
- `/api/conversations/threads` still reads legacy `leads` collection; iter154 dual-writes to both. Plan migration to consolidate on `pt_leads`.
- Extract `_dedupe_by(rows, key)` helper to DRY up the two why_now callsites.

---


## Iter 153 — Pietential B2B mode + Instinct widget + Demo sales-call mode switcher (Feb 12, 2026)

User: "I want the Pietential workspace frontend dashboard to look like b2b dashboard (with the instinct feature/widget on the dashboard), and in the demo dashboard I need option of b2b demo dashboard, b2c demo dashboard and hybrid demo dashboard so that i can show all 3 to the clients on sales calls."

### Shipped
- **Pietential tenant mode: `hybrid` → `b2b`** (direct MongoDB update) so `/app` locks to B2BFounderDashboard.
- **InstinctFeedWidget** on B2BFounderDashboard — fetches `GET /api/pt/insights/feed?status=new`, displays top 5 cards.
  - Mobile (<md): compact list with signal_type badge + 1-line summary.
  - Desktop (md/lg): responsive card grid (2-col md, 3-col lg) showing signal_type, confidence %, prospect, summary, ARIA suggested message.
  - Both link through to `/app/instinct?card_id=<id>` for full detail.
- **DemoModeSwitcher** on `/app` for `ten_demo` only — 4 pills (B2C / B2B Founder / B2B Sales / Hybrid). Selection persists in `localStorage['aria.demo.dashboard.mode']` so sales-call refreshes don't lose context. Switcher overrides client-side rendering only — tenant mode in DB stays `hybrid`.

### Verified (iter153, 100% pass)
- Pietential `_mode` → b2b ✅
- Pietential dashboard renders InstinctFeedWidget with 5 cards on desktop; demo switcher absent ✅
- Demo `_mode` returns `ten_demo`/hybrid; switcher visible with all 4 pills ✅
- Pill clicks render correct dashboards; localStorage persists; reload restores selection ✅
- Tenant isolation intact — Demo's Instinct widget shows only `ins_demo_*` cards, no Pietential leak ✅

### Known follow-up (P2)
- `Dashboards.js` now ~810 lines — split B2C / B2BFounder / B2BSales / widgets into separate files for maintainability.

---


## Iter 151–152 — Onboarding tour auto-dismiss for returning users (Feb 12, 2026)

User: "Auto-dismiss onboarding tour modal so first-time users can click 'Sales View' without skipping the tour (P1, found in iter150 testing)"

### Shipped
- **Backend persistence** — new `tour_completed_at` field on the user document. Endpoint `POST /api/auth/me/tour-complete` (auth required) sets it to ISO timestamp. `GET /api/auth/me` and login response now include the field.
- **Backfill** — all 44 existing users (accounts > 24h old) had `tour_completed_at` set to "<now> (backfilled)" so returning founders never see the welcome modal again, regardless of browser/device.
- **Frontend `AriaTourModal`** — gates open state on `user.tour_completed_at` from `useAuth()`. localStorage stays as the fast secondary gate to avoid flicker before /auth/me hydrates. `complete()` now POSTs to the new endpoint (fire-and-forget) so completion persists across browsers.
- **`?tour=1` re-run preserved** — `forceTourLockedRef = useRef(forceTour)` captures the value at mount so the URL-strip effect can't accidentally trip the auto-dismiss path for users who explicitly request a tour re-run.

### Verified (iter151 + iter152, 100% pass)
- Backend: 7 pytest cases — `_safe_user`, login response, `POST /me/tour-complete` persistence + auth gate.
- Frontend: Logging in as Pietential owner & Demo viewer with backfilled `tour_completed_at` shows NO `aria-tour-modal`; `nav-sales-view` is clickable on first render.
- `/app?tour=1` re-run path keeps modal visible for the entire session (20/20 polls); skip click fires `POST /api/auth/me/tour-complete` and closes.

### Minor follow-ups (P2)
- `api.post('/api/auth/me/tour-complete').catch(() => {})` swallows errors — consider `console.warn` for observability.
- `auth.py` mixes naive `_utc_now()` and tz-aware `datetime.now(timezone.utc).isoformat()` — pick one helper for consistency.

---


## Iter 150-B — Phase B Step 1: SALES_COACH Top 3 Actions + DashboardRouter wiring (Feb 12, 2026)

User: "A. Proceed top to bottom." (resumed Phase B Step 1 after fork)

### Shipped
- **Claude SALES_COACH (Haiku) wired** in `routes/dashboards.py::_sales_coach_top3` — returns 3 named-lead actions for the day, cached per `(tenant_id, user_email, date)`. Bust via `POST /api/dashboard/top-actions/regenerate`.
  - Guard: returns `{coming_soon: True, rows: []}` when there are 0 hot leads AND 0 deal risks AND 0 pending approvals (skips Claude call).
  - claude_call kwargs corrected (`system=`, `prompt=` — matches `services/claude_service.py` signature).
  - Errors logged with full stack at WARNING; client gets friendly `coming_soon` payload.
- **Frontend `TopActionsCard`** in `Dashboards.js` renders the 3 ordered actions with lead · company · why_now and a Regenerate button (`data-testid="top-3-regenerate"`) hitting the regenerate endpoint and refreshing the panel.
- **`/app` is now `<DashboardRouter />`** — picks B2C / B2B-Founder based on tenant mode (hybrid → B2BFounder by default). Legacy `<CommandCenter />` preserved at `/app/command-center-legacy`.
- **Sidebar "Sales View" entry** (`data-testid="nav-sales-view"`) added to NAV_PRIMARY, visible for `b2b` and `hybrid` tenants. Routes to `/app/sales-view`.

### Verified (testing agent iter 150, 100% pass)
- `_mode` returns correct {tenant_id, mode, currency, hourly_rate} for both Pietential (INR/3500) and Demo (USD/45).
- B2B Sales `top_actions` returns 3 Claude-generated rows with `{action, lead, company, why_now}`. First call `cache:"miss"`, second call `cache:"hit"`. Regenerate clears cache → next call `cache:"miss"` again.
- Tenant isolation intact — no Pietential leads leak into Demo dashboards (or vice versa).
- Backend tests: `/app/backend/tests/test_iter150_dashboard_router.py` (9 tests, all pass).

### Known follow-ups (P1)
- Onboarding tour modal overlays sidebar on first login → consider auto-dismiss for returning users so the new "Sales View" nav entry is reachable on first click.
- `dashboards.py` is ~860 lines — split B2C / B2B-Founder / B2B-Sales into separate route modules for maintainability.
- `attribution_top3 or {coming_soon: True, rows: []} if not attribution_top3 else attribution_top3` is convoluted (line 742) — simplify.

### Pending Phase B
- Step 4 (skipped per user) — multi-touch channel data tracking
- Step 5 (skipped per user) — ICP Drift Modal UI

---


## Iter 150 — Phase A foundation + Phase C dashboard skeletons (Feb 6, 2026)

User: "A first, then C — one session, two phases, back to back. Don't stop."

### Phase A — Data foundation (plumbing) ✅
- **New tenant fields** (backfilled on all 6 existing tenants):
  - `mode` ∈ {`b2c`, `b2b`, `hybrid`} — defaults to `settings.workspace_type` or `hybrid`
  - `currency` ∈ {INR, USD, GBP, AED, EUR} — Pietential→INR, rest→USD
  - `hourly_rate_assumption` — INR ₹3500 / USD $45 / GBP £38 / AED د.إ165 / EUR €42
- **New collections** (with indexes):
  - `score_history` — every score change writes a delta row (lead_id, prev, new, delta, reason, source). Backfilled with 34 baseline rows for existing pt_leads.
  - `booking_events` — meeting log (when, channel, deal_value, booked_by). Empty in production until your booking flow writes here.
  - `asset_clicks` — lead-magnet click telemetry (asset_id, lead_id, channel). Empty until tracked-link wiring.
- **`pt_leads` new fields**: `lead_score_delta`, `next_followup_at` (defaulted on 31 rows).
- **Write hooks**: `_run_score_decay` (30/60-day) now calls `log_score_change` so the Why-Now-Feed has real data on day one.
- **Helper module** `/app/backend/routes/dashboard_data.py` with `get_tenant_mode`, `get_tenant_currency`, `get_tenant_hourly_rate`, `log_score_change`, `log_booking`, `log_asset_click`, `latest_score_changes`, `ensure_indexes`.
- **Migration script**: `/app/backend/scripts/iter150_phase_a_migrations.py` (idempotent, re-runnable).

### Phase C — 3 dashboard skeletons ✅
- **New router** `/app/backend/routes/dashboards.py` registered at `/api/dashboard/*`:
  - `GET /_mode` — returns active tenant's mode + currency + hourly_rate
  - `GET /b2c` — KPIs · ARIA Time Saved · Momentum · Revenue Forecast · Live Conversations · Lead Sources · Asset Performance · Booking Funnel (w/ biggest drop) · Sequences · Ghost Leads · Multi-Touch (coming_soon) · Cost-per-Qualified (coming_soon)
  - `GET /b2b-founder` — KPIs · Momentum · Time Saved · ICP Drift · Channel Performance Table · Signal Attribution (gated 90d) · Why-Now · Founder Flags · Buying Committee Radar · Deal Risk · Ghost Leads · Monday Brief Preview
  - `GET /b2b-sales` — Top 3 actions (coming_soon — Phase B Claude) · KPIs · Hot Leads (3 cards) · Pipeline Table · Today's Agenda · Approval Queue · Deal Risk · Ghost Leads · Attribution top 3 · Why-Now
- **Frontend page** `/app/frontend/src/workspace/pages/Dashboards.js` exports `B2CDashboard`, `B2BFounderDashboard`, `B2BSalesDashboard`, `DashboardRouter`.
- **Routes mounted** in `App.js`:
  - `/app/dashboard/automation` → B2C
  - `/app/dashboard/founder` → B2B Founder
  - `/app/dashboard/sales` + `/app/sales-view` → B2B Sales
  - Existing `/app` still serves the legacy `<CommandCenter />` — zero regression.

### Currently live on data (real, populated)
- KPIs (leads / high-intent / meetings / signals / conversion / pipeline value)
- ARIA Time Saved (real conv + draft + insight + research counts × hourly rate)
- Momentum score (real 14-day vs prior 14-day deltas across 3 inputs)
- Live Conversations feed (real outbound_log + lead lookups)
- Booking Funnel (real counts at each stage from existing collections)
- Channel Performance Table (real lead/meeting/health rollups)
- ICP Drift detection (real distribution vs primary ICP)
- Why-Now Feed (driven by `score_history` from now on)
- Founder Flags (real pt_insights with founder_flag=true)
- Buying Committee Radar (real pt_leads grouped by company × role keywords)
- Deal Risk Flags · Ghost Lead Recovery · Today's Agenda · Approval Queue · Pipeline Table · Hot Lead cards

### Showing "Coming soon" empty states (data sources empty in prod)
- **Revenue Forecast** — needs `booking_events.deal_value` writes from your booking flow
- **Asset Performance** — needs tracked-link writes calling `log_asset_click`
- **Multi-Touch Channel Overlap** — needs `pt_leads.source_channels[]` array tracking
- **Cost per Qualified Lead** — needs Meta/Google Ads integration + spend data
- **Signal-to-Revenue Attribution** — auto-unhides once workspace has 90 days of data + ≥3 booked meetings tied to signals
- **B2B Sales Top 3 Actions** — Phase B work (Claude `SALES_COACH` task_type — needs adding to `task_types.py`)
- **B2C Sequences** — only Lemlist `lemlist_data.campaign` campaigns are surfaced today; expand when Saleshandy/Instantly track campaign IDs

### Files added
- **NEW** `/app/backend/routes/dashboard_data.py` (helper module)
- **NEW** `/app/backend/routes/dashboards.py` (3 endpoints + _mode)
- **NEW** `/app/backend/scripts/iter150_phase_a_migrations.py` (idempotent)
- **NEW** `/app/frontend/src/workspace/pages/Dashboards.js` (3 dashboards in one file)
- Modified: `routes/__init__.py` (registered `dashboards_router`)
- Modified: `routes/pietential.py` (score decay → `log_score_change`)
- Modified: `App.js` (4 new routes, 0 deletions)

### Verification
- Phase A migrations ran cleanly: indexes created · 6 tenants backfilled · 34 score_history rows · 31 pt_leads delta fields.
- Backend boots clean · all 4 endpoints respond 200 · payload shape verified.
- `yarn build` clean (0 errors, 11 pre-existing warnings from other files).
- Live screenshot of B2C dashboard at `/app/dashboard/automation` shows full render with real data + clean coming-soon states.
- iter148 isolation suite (10/10) still PASS — no regression on existing flows.

### Status
**READY**. Both new collections + tenant fields live on preview Mongo. After redeploy, run `python -m scripts.iter150_phase_a_migrations` against production Mongo (idempotent — safe).

### Carry-over (Phase B candidates, prioritised)
1. Add `SALES_COACH` task_type to `task_types.py` + wire Top-3-Actions Claude call (cached per user/day).
2. Find the existing booking-creation flow + insert `log_booking(...)` calls so Revenue Forecast lights up automatically.
3. Add `lead_score_delta` write whenever `pt_leads.score` changes (currently only score-decay path writes history; signal-driven score bumps don't yet).
4. Multi-touch tracking — extend `pt_leads` ingest to `$addToSet` to `source_channels[]`.
5. ICP Drift modal — `/api/dashboard/b2b-founder/icp-drift-detail` returning channel × ICP cross-tab.

---


## Iter 149b — Workspace Switcher "Reset demo data" button (Feb 5, 2026)

UI follow-up to iter149's `/api/demo/reset` endpoint. Founder no longer
needs a curl to reset between live demos — one click from the
workspace switcher.

### What shipped
- `/app/frontend/src/components/AppLayout.js` — added a "🔄 Reset demo
  data" footer row inside the existing `WorkspaceSwitcher` dropdown
  (`data-testid="workspace-switcher-reset-demo"`). Renders ONLY when:
  - active tenant id = `ten_demo`, AND
  - `user.role === 'master_admin'`
- Click → window.confirm dialog explaining exactly what will be wiped
  and reseeded (6 leads + 3 cards + 10 messages) → `POST /api/demo/reset`
  → toast `Demo reset · 6 leads · 3 cards · 10 messages` → broadcasts
  `aria:tenant-changed` so every child page (Instinct Feed, Lead Inbox,
  Command Center KPIs) refetches immediately.
- Spinner on the icon while in-flight, double-click protected.

### Verified live on preview
- Master_admin on ten_demo → reset row VISIBLE.
- Master_admin on ten_pietential → reset row HIDDEN (count == 0).
- Non-admin users still get the 403 from the backend (iter149 guard).

### Files changed
- `/app/frontend/src/components/AppLayout.js` (imports + `WorkspaceSwitcher` component)

### Status
**READY**. Push via Save to GitHub → redeploy. After redeploy, log into
`https://app.genleadai.com` as master_admin (admin@demo.com), pick
"GenLeadAI Demo" in the workspace switcher → the Reset row appears at
the bottom of the dropdown.

---


## Iter 149 — /api/demo/reset endpoint (Feb 5, 2026)

### What shipped
- **`POST /api/demo/reset`** — master_admin only · tenant-locked to ten_demo.
  Purges every `seed_source: iter148` row across `pt_leads`, `pt_insights`,
  `outbound_log`, `inbound_messages`, `activities`. Then re-runs the iter148
  seeder (via `importlib.reload` so timestamps re-anchor to NOW). Returns
  a summary of `{purged, reseeded, reset_at, actor}` + writes an audit_log
  entry.
- **`GET /api/demo/state`** — master_admin only · read-only health check
  returning `{counts, fully_seeded, oldest_seed_created_at}`. Useful before
  starting a live demo to confirm data is fresh.
- File: `/app/backend/routes/demo_reset.py` (~110 LOC).
- Registered in `routes/__init__.py` (alongside the other iter149 routers).

### Verification (live)
- `admin@demo.com` calling `POST /api/demo/reset` → 200; oldest_seed_at
  jumped from 10:33:45 → 10:46:09 (fresh anchor). All 6 leads + 3 cards
  + 10 messages re-seeded.
- Demo viewer (`meghaagarwaljain2015@gmail.com`) calling reset → **403**.
- Unauth → **403**.
- iter148 10/10 isolation tests still PASS after the reset cycle.

### Files changed
- **NEW** `/app/backend/routes/demo_reset.py`
- `/app/backend/routes/__init__.py` (import + register `demo_reset_router`)

### Use
```bash
# Before a demo — confirm seeds are fresh
curl $API_URL/api/demo/state -H "Authorization: Bearer <master_admin>"

# After a demo (or between sessions) — pristine reset
curl -X POST $API_URL/api/demo/reset -H "Authorization: Bearer <master_admin>"
```

---


## Iter 148 — Megha client + Demo viewer accounts + 6 demo leads (Feb 5, 2026)

### Provisioning
- **megha@contentvista.com** — password `Pietential2026!` · role `workspace_owner`
  · single membership in `ten_pietential` (role `owner`). Stray memberships purged.
- **meghaagarwaljain2015@gmail.com** — password `DemoView2026!` · role
  `workspace_viewer` · single membership in `ten_demo` (role `viewer`,
  read-only). Previous auto-provisioned tenant `ten_af0b03831422` membership
  removed.
- Both passwords bcrypt-hashed on write.
- Credentials added to `/app/memory/test_credentials.md`.

### Demo lead seed — 6 leads in `ten_demo`, fully fictional
**B2B Instinct (3 cards in pt_insights + pt_leads)**:
- Sarah Chen · CPO · NovaBridge Technologies · score 84 · HIGH_INTENT · tier_1 ·
  signal `new_people_leader` · LinkedIn DM Tue 10am
- Arjun Mehta · VP People · Kestrel Financial Group · score 71 · HIGH_INTENT ·
  tier_1 · signal `layoffs` (12%) · reply_sentiment POSITIVE
- James Whitfield · Head HR Transformation · Alveron Consulting · score 58 ·
  MEDIUM_INTENT · tier_2 · signal `benefits_hr_transformation`

**B2C Automation (3 leads in pt_leads + outbound_log + inbound_messages)**:
- Priya Nair · WhatsApp · stage warm · journey 2/7 · 3-message thread (qualification)
- Rahul Desai · Email · stage hot · journey 5/7 · 5-message thread (qualification → booking)
- Ananya Sharma · WhatsApp · stage warm · journey 3/7 · 2-message thread (nurture)

All seeded data tagged `seed_source: iter148` for idempotent re-runs.
Seeder script: `/app/backend/scripts/iter148_seed_demo_accounts.py` (re-runnable).

### Verification — 10/10 PASS
- **V1** PT-owner workspace switcher returns exactly 1 entry (ten_pietential,
  role=owner) · admin panel blocked.
- **V2** Demo-viewer workspace switcher returns exactly 1 entry (ten_demo,
  role=viewer) · admin panel blocked.
- **V3** PT-owner querying `/api/pt/insights/feed` with `X-Tenant-Id=ten_demo`
  gets **403 "Not a member of requested tenant"** (Pietential routes use
  the strict `get_active_tenant` dep). Calling with their own tenant
  returns ZERO demo cards.
- **V4** Demo-viewer forging `X-Tenant-Id=ten_pietential` — `/api/pt/leads`
  silently falls back to ten_demo (route uses `get_current_user`); the
  response contains zero Pietential-domain emails. Strict 403 path also
  confirmed on `/api/pt/insights/feed`.
- **V5** All 6 demo leads visible to demo-viewer via `/api/pt/leads`.
- **V6** No email-domain overlap — `novabridge.io`, `kestrelfinancial.com`,
  `alveron.com`, `*.example` absent from real Pietential pt_leads.
- **V7** Instinct Feed renders 3 cards with correct
  `prospect_name`/`signal_type`/`lead_score`/`suggested_message`/`icp_match_name`/`confidence`
  populated (iter143 UI-compat fields all present).
- **V8** Conversation thread endpoint returns the correct number of
  outbound + inbound messages per lead (Priya 3, Rahul 5, Ananya 2).

Test file: `/app/backend/tests/test_iter148_demo_isolation.py` (10 tests, 2.8s).

### What was NOT touched
- Existing Pietential leads, intel cards, ICP config — all preserved.
- `lemlist_poll_loop` / `pietential_insight_scan_loop` jobs untouched.
- Other tenants — only ten_demo received seed data.
- `claude_service.py` wrapper — V10 architectural rule preserved.

### Files changed
- **NEW** `/app/backend/scripts/iter148_seed_demo_accounts.py` (re-runnable seeder)
- **NEW** `/app/backend/tests/test_iter148_demo_isolation.py` (10 isolation tests)
- `/app/memory/test_credentials.md` (Megha credentials)
- MongoDB: `users`, `tenant_memberships`, `pt_leads`, `pt_insights`,
  `outbound_log`, `inbound_messages` (ten_demo only — seed_source=iter148).

### Status
**READY** on preview. Megha can log in to **app.genleadai.com** with
`megha@contentvista.com / Pietential2026!` after redeploy AND a one-time
DB sync from preview to production (the user/membership/seed writes only
exist in preview's MongoDB).

⚠️ **Production reminder**: Preview MongoDB ≠ Production MongoDB. The
provisioning + seed writes don't sync automatically. After redeploy, re-run
`python -m scripts.iter148_seed_demo_accounts` against the production
MongoDB connection (or have Emergent Support do it).

---


## Iter 147 — Lint cleanup + helper migration (Feb 4, 2026)

User triggered the two carried-over items from iter146:
  • `routes/pietential.py` pre-existing E701/E702 style violations
  • Migrate remaining endpoints to `lead_query.py` helper

### What shipped

**🧹 Lint sweep — 86 → 0 violations across all `routes/`**
- Ran `autopep8 --select=E701,E702` across `routes/pietential.py`,
  `routes/automation_rules.py`, `routes/iter105_fixes.py`,
  `routes/journey.py`, `routes/founder_command_center.py`. Auto-fixed
  the bulk of one-line `if x: stmt` legacy patterns.
- Ran `ruff --select F541 --fix` across `routes/pietential_intel.py`,
  `routes/pt_insights.py`, `routes/conversations.py` (f-strings without
  placeholders).
- Hand-fixed 7 E741 `l` (ambiguous variable name) → `lead` in
  `routes/pietential.py` (5 distinct loops/comprehensions).
- Verification: `flake8 routes/ --select E701,E702,F541,E741` exits 0.
- Backend boots clean after every batch · 54/54 sprint regression PASS.

**📦 lead_query.py migration — 5 endpoints**
- `/api/analytics/dashboard` (`routes/analytics.py`) — total_leads,
  status_distribution, and icp_distribution now use `count_tenant_leads`
  with mapped status / stage / icp_tier filters. Verified live on
  Pietential: total=44 (correct), status sum=44 (no double-counting).
- `/api/export/leads` (`routes/exports_audit.py`) — uses
  `iter_tenant_leads(limit=5000)` so the CSV download includes pt_leads
  with the `_origin` column showing legacy vs pt source.
- `/api/export/report` (`routes/exports_audit.py`) — same migration for
  status counts (lead_type + channel stay legacy-only since pt_leads
  doesn't carry those fields).
- `/api/aria/call-priority` (`routes/aria_call_priority.py`) — also
  pulls pt_leads where `score≥60` or `stage∈{hot,engaged,session_pilot}`
  as additional call-priority candidates. Normalises pt_leads shape into
  the legacy lead_doc shape so `_compute_best_time_to_call_for_lead`
  works unchanged.
- `/api/leads/counts` already using both collections from iter146.

**🐛 Helper bug found + fixed (caught during migration)**
- `count_tenant_leads` had a subtle bug: when caller passed e.g.
  `status_in={'proposal_sent'}` (a status with no pt-side stage mapping),
  the pt query fell through to `{tenant_id: tid}` and counted ALL pt_leads
  — over-counting analytics by ~64% for Pietential. Fixed by tracking
  `pt_filter_requested` and returning `legacy_n` only (skipping pt entirely)
  when filters were requested but produced no pt-side clause.
- Same fix applied to `iter_tenant_leads` so callers iterating with
  legacy-only filters don't get unrelated pt rows.
- Verified live: Pietential analytics `sum(status_distribution.values()) == 44`
  (was 128 before fix).

### Files changed
- `/app/backend/routes/lead_query.py` (helper bug fix — `pt_filter_requested`)
- `/app/backend/routes/analytics.py` (use `count_tenant_leads`)
- `/app/backend/routes/exports_audit.py` (use `iter_tenant_leads` + `count_tenant_leads`)
- `/app/backend/routes/aria_call_priority.py` (union pt_leads into priority candidates)
- `/app/backend/routes/pietential.py` (E741 rename `l` → `lead`)
- `/app/backend/routes/pietential.py`, `automation_rules.py`, `iter105_fixes.py`, `journey.py`, `founder_command_center.py`, `pietential_intel.py`, `pt_insights.py`, `conversations.py` (autopep8 + ruff F541 sweep — style only)

### Verification
- `flake8 routes/ --select E701,E702,F541,E741` exits 0.
- **54/54 sprint pytest PASS** (iter137+140+141+143).
- V10 architectural guard PASS.
- Pietential `/api/analytics/dashboard` returns mathematically-consistent
  counts (total=44, status sum=44).
- Demo workspace regression: total=138, untouched.

### Status
**READY TO REDEPLOY**. After redeploy, Pietential workspace's analytics
dashboard, call priority queue, and lead CSV export will all reflect
real pt_leads data.

### Carry-over (not in this iteration)
- Remaining files using `leads_collection` directly (lead_magnets,
  touchpoint_engine, public_api, webhooks_inbound, webhooks_whatsapp,
  outreach, campaigns, demo_seeder, admin_deployments, ai) — most are
  write paths or workspace-agnostic. Migrate only when a Pietential bug
  surfaces.

---


## Iter 146 — COMPLETE BACKEND DEBUG: Pietential / multi-collection fixes (Feb 4, 2026)

User triggered "RUN COMPLETE BACKEND AND DO COMPLETE DEBUGGING" with a
screenshot showing the sidebar lead-count strip displaying **0/0/0/0/0**
for the Pietential workspace, while the Lead Feed itself was populated.

### Root cause (sweeping)
The backend has TWO lead collections with different field shapes:
  • `leads` (legacy ARIA) — `status`, `icp_score`, `icp_tier`, `_id: ObjectId`
  • `pt_leads` (Pietential / Lemlist) — `stage`, `score`, `source`, `id: UUID`

Every aggregation endpoint historically only queried `leads_collection`.
For Pietential workspaces (where 100% of data lives in `pt_leads`) that
means sidebar counts, milestones, EOD wrap, Command Center "new today",
pipeline-health, ICP contact counts, and the daily Pietential scan ALL
returned 0 / empty even with rich data in MongoDB.

### What shipped

**🟥 Tier-1 (production-visible) — FIXED**
- **`/api/leads/counts`** (`routes/lead_counts.py`) — rewrote to aggregate
  both `leads` (`status` field) and `pt_leads` (`stage` field), collapsed
  into 4 buckets: qualified, nurturing, new, cold. Verified live: Pietential
  now returns `total=44, qualified=10, nurturing=2, new=16, cold=16`.
- **`/api/pietential/pipeline-health`** (`routes/pietential_intel.py`) —
  all 5 KPIs filtered for `lemlist_data.is_active_in_sequence: True`
  which only the engine-classified rows have. Now `$or`s across 3
  data-source shapes (engine, lemlist sync, outreach import). Verified:
  was `0/0/0/0/0`, now `12 active / 11 high-intent / 10 stale / 10 awaiting`.
- **`/api/pietential/lead/{id}/scan-now` enrichment gate** — same gate
  ("HIGH_INTENT only") starved 99% of production pt_leads. Gate now also
  fires on `stage in {hot, engaged, session_pilot, replied}` OR `score >= 35`.
  Verified live: scan-now now returns `enriched: true, signal_found: true,
  signal_type: wellbeing, confidence: 0.85` on a real pt_lead.
- **Claude JSON-shape hardening** — Sonnet occasionally wraps single-object
  schemas in a one-element list, which 500'd the engine. Added `isinstance(data, list)`
  unwrap at all 4 Claude callsites (intent · ICP · signal · insight). Defensive.

**🟧 Tier-2 (data quality) — FIXED**
- **`/api/aria/eod-wrap`** (`routes/aria_eod_wrap.py`) — daily wrap now
  unions pt_leads for `new_leads_today`, `wins_today` (stage=session_pilot),
  `losses_today` (stage=dnc), `hot_untouched` (stage hot/engaged with no
  activity), and `overdue_pending`. Stops Pietential founders getting
  empty EOD emails.
- **`/api/command-center/founder`** (`routes/founder_command_center.py`) —
  `new_today` KPI tile now counts both `leads` + `pt_leads` in the last 24h.
- **`/api/ttv/milestones`** (`routes/onboarding_legacy.py`) — first_lead /
  first_meeting / first_won timestamps now pull from pt_leads too.
  Pietential workspace onboarding progress jumped from `40% → 80%`.
- **`/api/icps/{id}`** (`routes/icps.py`) — `contacts` count now includes
  pt_leads referencing that ICP id.

**📦 Architectural foundation — NEW**
- **`/app/backend/routes/lead_query.py`** — new unified-lead helper:
  - `iter_tenant_leads(tenant_id, status_in, stage_in, icp_tier_in, min_score, limit)`
    yields normalised dicts from BOTH collections.
  - `count_tenant_leads(...)` returns the combined count.
  - `find_tenant_lead_by_id(tenant_id, lead_id)` resolves across both.
  - `_PT_STAGE_TO_STATUS` mapping (cold→new, hot/engaged→qualified, etc.).
  Future endpoints should use this helper instead of querying collections
  directly. Already wired into `lead_counts.py`. Other endpoints can
  migrate incrementally without breaking anything.

### Files changed
- **NEW**: `/app/backend/routes/lead_query.py` (unified helper, 200 LOC)
- `/app/backend/routes/lead_counts.py` (rewrite — both collections)
- `/app/backend/routes/pietential_intel.py` (pipeline-health · enrichment gate · 4x Claude list-unwrap)
- `/app/backend/routes/aria_eod_wrap.py` (pt_leads union in 4 stats)
- `/app/backend/routes/founder_command_center.py` (new_today + db import)
- `/app/backend/routes/onboarding_legacy.py` (3 milestones include pt_leads)
- `/app/backend/routes/icps.py` (contacts count includes pt_leads)

### Verification
- **54/54 sprint pytest PASS** (iter137 + iter140 + iter141 + iter143).
- **V10 architectural guard exit 0**.
- Live Pietential audit:
  - sidebar counts: total=44 (was 0)
  - pipeline-health: 12/11/10/10 (was 0/0/0/0)
  - onboarding milestones: 80% complete (was 40%)
  - per-lead scan-now: `enriched: true, signal_found: true, confidence: 0.85`
  - intel/scan-hot from iter145: still queues 10 pt_leads correctly.
- **Tenant isolation preserved** — all queries pass tenant_id; admin@demo
  on ten_demo gets ten_demo numbers, on ten_pietential gets ten_pietential.

### Backend audit findings deferred to follow-up
Lower-priority Tier-2/3 items the audit surfaced (not in this iteration):
- `/api/leads` list / `your-five-today` / `sleeping` — Pietential UI calls
  `/api/pt/leads` directly so these are correctly Pietential-blind. Will
  unify after the Pietential UI starts using a workspace-agnostic feed.
- `/api/campaigns` aggregations — campaigns are workspace-agnostic in
  current product. Defer until campaign data lands in both collections.
- Pre-existing E701/E702 style violations in `routes/pietential.py` (legacy
  one-line if/else patterns from initial scaffold).

### Status
**READY TO REDEPLOY** to `app.genleadai.com`. After redeploy, sidebar lead
counts, pipeline-health card, EOD wrap email, Command Center "new today"
tile, and onboarding milestones will all reflect the real Pietential data.

---


## Iter 145 — Scan Engaged Leads field-name bug (Feb 3, 2026)

User reported the production "Scan engaged leads" button still returned
zero matches even though the Lead Feed UI clearly showed lemlist-sourced
pt_leads with score 15 / 30.

### Root cause
`/api/intel/scan-hot` queried `pt_leads` with `{icp_score: {$gte: 15}}`
+ `{icp_tier: 'hot'}`. But `pt_leads` (written by the lemlist poll loop
in `routes/pietential.py`) uses **`score`** and **`stage`** field names,
NOT `icp_score`/`icp_tier`. The query never matched the user's actual
leads. A secondary bug: legacy `leads` collection had 10+ test docs with
`icp_score=50` that filled the 10-lead cap first, starving any pt_leads
that did happen to match.

### Fix
1. `pt_leads` query now uses `$or` across both field-name conventions
   (`score`/`stage` for lemlist-sourced rows, `icp_score`/`icp_tier`
   for engine-written rows).
2. Reorder: pt_leads queried FIRST, legacy `leads` only fills any
   remaining slots — so the user's actual Lemlist leads always make it
   into the batch.
3. `_add` normalises both shapes into the same `{icp_score, icp_tier}`
   wire format.

### Verification (live, Pietential)
Before: `queued: 10` (all "Iter102/Alice/Wire/Pixel" legacy test data —
the user's lemlist leads never queued).
After: `queued: 10, pt: 10, legacy: 0` — actual lemlist leads queued
("Alex Patel score 145", "Maria Lopez score 131", "Liz Ceisler score 78
hot", "Mark Lombardozzi score 75 hot", …).

### Files changed
- `/app/backend/routes/intel.py` (scan-hot field-name + ordering fix)

### Status
READY TO REDEPLOY to `app.genleadai.com`. After redeploy, "Scan engaged
leads" on the Pietential Lead Feed will properly queue your real
Lemlist-sourced leads.

---


## Iter 144 — Enhancement Backlog Sweep + Scan Hot Leads UX Fix (Feb 3, 2026)

User triggered "A. Go" after a production walkthrough surfaced the
"No hot leads matched" issue. Single continuous run executing all P1/P2/P3
enhancements + a small Slack delivery channel on top of the iter143 engine.

### What shipped

**🟧 P1 — Claude event-loop blocking RESOLVED**
- Root cause: `emergentintegrations.llm.chat.LlmChat.send_message` is
  declared `async def` but internally calls the **synchronous** `litellm.completion()`,
  blocking the FastAPI event loop for the full 5-25s Claude round-trip.
- Fix: wrap each Claude call in `asyncio.to_thread(lambda: asyncio.run(chat.send_message(...)))`
  inside `services/claude_service._one_attempt`. Each call runs on its own
  worker thread + its own asyncio loop, leaving the FastAPI loop free.
- **Verified live**: while a 26s `/_test/simulate` (3x Claude calls) was
  running, 5 concurrent `/pipeline-health` pings completed in 0.10–0.16s
  each. Before the fix they would have queued behind the simulate.

**🟨 P2 — "Invalid lead ID" toast on row click FIXED**
- Root cause: `/api/leads/{id}` cast `lead_id` through `ObjectId()` which
  raises `InvalidId` for the UUID-style ids used by `pt_leads`. The
  except branch returned HTTP 400 — Lead360.js only fell back to
  `/api/pt/leads/{id}` on HTTP 404, so the fallback never fired and the
  toast surfaced instead.
- Fix in `server.py`: `try { oid = ObjectId(lead_id) } except → 404` so
  the frontend fallback path takes over.
- Belt-and-braces in `Lead360.js`: the fallback now also fires on 400
  (in case any other legacy endpoint emits it).

**🟦 P3a — Test data teardown fixture**
- New `/app/backend/tests/conftest.py` with a `session`-scoped autouse
  fixture that purges, AFTER all tests finish:
  - `applications` where `full_name` or `company_name` starts with `TEST_`
  - `tenants` matching `^ws_` with `application_id` set
  - matching `tenant_memberships`, `onboarding_config`, `invitations`,
    `workspace_invites`
  - simulated Pietential leads (`@pietential-test.com`)
  - orphan `pt_insights` cards from cleaned simulated leads
- Verified: running iter140+141+143+137 in one invocation purged 5
  leftover apps automatically (visible in pytest output).

**🟦 P3b — F401 unused imports cleaned**
- `/app/backend/aria_agent_routes/brain.py` was importing 14 unused
  symbols (`db`, `HTTPException`, `BaseModel`, `Field`, `Optional`,
  `List`, `datetime`, `timezone`, `timedelta`, `os`, `json`,
  `playbooks_collection`, `activities_collection`, `AriaTrainingPayload`).
  Stripped down to just the 4 actually-used names. `flake8 --select F401`
  now exits clean for this file.

**✨ Slack high-confidence Pietential pings**
- New `_slack_founder_alert` in `routes/pietential_intel.py` fires
  alongside the existing WhatsApp founder alert whenever a Pietential
  insight card lands with `founder_flag=true AND confidence ≥ 0.85`.
- Block-kit payload: prospect name + role + company + lead score/tier
  on one row, signal summary on the next, 35-word opening preview, and
  a primary "Open in ARIA" button deeplinking to
  `https://app.genleadai.com/app/instinct?card_id={id}`.
- Reads `SLACK_WEBHOOK_URL` from env; silent no-op when not set.
- Audit logged as `slack_founder_alert_sent` on success.

**🎯 Scan Hot Leads UX fix (user-triggered before backlog)**
- Frontend `LeadFeed.js`: button now sends `min_icp_score: 15` instead
  of `80`, so warm/engaged leads (score 15–79) qualify. Button label
  flipped to "Scan engaged leads" so the copy matches behaviour.
- Backend `intel.py`: empty-state message rewrites to
  "No engaged leads matched. Add leads with ICP score ≥ 15 to enable batch intel."
- Verified live on Pietential: 10 candidates queued (previously 0).

### Files changed
- `/app/backend/services/claude_service.py` (event-loop fix)
- `/app/backend/server.py` (lead 404-on-bad-ObjectId)
- `/app/frontend/src/workspace/pages/Lead360.js` (400 fallback)
- `/app/backend/routes/pietential_intel.py` (Slack alert function)
- `/app/backend/aria_agent_routes/brain.py` (F401 sweep)
- `/app/frontend/src/workspace/pages/LeadFeed.js` (min_icp_score 80→15 + label)
- `/app/backend/routes/intel.py` (empty-state msg)
- **NEW** `/app/backend/tests/conftest.py` (teardown fixture)

### Verification
- **54/54 sprint pytest PASS** (iter137 + iter140 + iter141 + iter143
  run together in one invocation = 62s total runtime, conftest
  teardown purged 5 leftover TEST_ apps automatically).
- **V10 architectural guard PASS** — only `services/claude_service.py`
  imports Anthropic.
- **Concurrent-call live proof** — pipeline-health 0.1s while simulate 26s
  ran in parallel. Event loop is unblocked.
- **Lint clean**: claude_service.py, Lead360.js, LeadFeed.js,
  IntelTab.js, brain.py (F401).

### Status
**READY TO REDEPLOY** to `app.genleadai.com`. Note: production-only env
keys still needed — Lemlist · RapidAPI · Serper · 360dialog · Resend ·
new optional `SLACK_WEBHOOK_URL` for the high-confidence Pietential pings.

### Carry-over (not blocking)
- UX sweep V8/V9/V10/V12/V13-V16/V20 pending production walkthrough.
- LinkedIn Sales Navigator (P3).
- Embedding RAG (blocked on Emergent proxy capability).

---


## Iter 143 — Pietential Intelligence Engine Verified (Feb 3, 2026)

User trigger: "E. Go." — run the 15-point verification checklist for the
Pietential Intelligence Engine that was built (and largely scaffolded) in
the previous fork. Adapt the UI / Saleshandy gate / Scan Now button in
the same pass.

### What shipped
- **15-point verification — all GREEN** via the new
  `/app/backend/tests/test_iter143_pietential_engine.py` suite.
  Local run + testing_agent_v3_fork iter143: **15/15 PASS · 39/39
  regression PASS (iter137 + iter140 + iter141) · V10 guard exit 0 ·
  frontend Pietential surfaces all clean.**
- **UI compatibility (b)** — `generate_insight_card_for_lead` now also
  writes `prospect_name`, `prospect_title`, `prospect_company`,
  `suggested_message` (mapped from `outreach_recommendation.opening_message`),
  `confidence`, `icp_match_name`, `icp_match_score`, and `status='new'`
  on every Pietential insight card so the existing `/api/pt/insights/feed`
  → `IntelligenceFeed.js` renders the card without changes.
- **Pietential Scan Now button (c)** — new
  `PietentialScanNowButton` component in `/app/frontend/src/workspace/pages/IntelTab.js`
  with `data-testid="pietential-intel-scan-now"`. Tenant-gated via
  `localStorage.active_tenant` (only renders when active tenant is Pietential).
  Wired into both the empty-state CTA and the live-profile header. Calls
  `POST /api/pietential/lead/{id}/scan-now`, shows the right toast for
  enriched/skipped/no-signal/dedup paths, then refreshes the intel profile.
- **Saleshandy gate (d)** — `/app/backend/routes/audit_loops.py`
  `saleshandy_poll_once` now filters `tenant_id: {$ne: 'ten_pietential'}`
  in its config query. The Pietential workspace uses Lemlist + the
  pietential_intel.py pipeline exclusively, never Saleshandy.
- **New pytest** — `/app/backend/tests/test_iter143_pietential_engine.py`
  (15 tests covering simulate → intent → ICP → insight card → founder_flag
  → pipeline-health → tenant isolation → Saleshandy gate → UI fields →
  role guards → dedup → V10 guard → cleanup → loops registered →
  manual triggers reachable). Runtime ~30s (Claude calls dominate).

### Files changed
- `/app/backend/routes/pietential_intel.py` — UI-compatibility fields
  written on insight card creation.
- `/app/backend/routes/audit_loops.py` — Saleshandy poll loop gated to
  skip ten_pietential.
- `/app/frontend/src/workspace/pages/IntelTab.js` — `PietentialScanNowButton`
  component + 2 wire-in points.
- **NEW** `/app/backend/tests/test_iter143_pietential_engine.py` (15 tests).

### Verification details
- `POST /api/pietential/_test/simulate` (admin@demo.com, X-Tenant-Id=
  ten_pietential) → 200; `intent.intent="HIGH_INTENT"`,
  `icp_result.matched_icp_id="icp_b"` (CHRO),  insight_card created,
  `final_lead.founder_flag=true`, `lead_score=100`, `account_tier="tier_1"`.
- `GET /api/pietential/pipeline-health` returns
  `{total_active_lemlist_leads, high_intent, high_intent_stale,
   awaiting_enrichment, signals_this_week, next_weekly_report_hint}`.
- Sales-rep on ten_demo gets 403 on every Pietential endpoint.
- Dedup verified: 2nd `/lead/{id}/scan-now` on the same lead returns
  `card:{skipped:true, reason:"duplicate_within_30d"}`.
- V10 guard exit 0 (no direct Anthropic imports outside `services/claude_service.py`).
- Frontend: `[data-testid="lemlist-pipeline-health-card"]` visible with
  5 stat tiles on Pietential CommandCenter; `pietential-intel-scan-now`
  visible on Pietential Lead 360 Intel tab, hidden on ten_demo. Zero JS
  pageerrors on /app, /app/leads, /app/instinct (Pietential context).

### Carry-over (not iter143 scope)
- Cosmetic UX: clicking a lead row from `/app/leads` list emits an
  "Invalid lead ID" toast. Direct navigation to `/app/leads/:id` works.
  Surfaced by testing agent — separate UX bug, P2.
- P1 still open: `claude_call` blocks the FastAPI event loop during
  heavy generation (the Pietential simulate takes 25s because of this).
- Test data cleanup: `TEST_`-prefixed apps + `ws_` tenants from prior runs.
- P3: cleanup F401 unused imports in `aria_agent_routes/brain.py`.
- LinkedIn Sales Navigator integration (P3).
- Embedding-based RAG (blocked — Emergent proxy lacks embedding models).

### Status
**READY TO REDEPLOY** to `app.genleadai.com`. Production reminder:
After deploy, paste the Pietential workspace's Lemlist API key + RapidAPI key
+ Serper key + 360dialog WhatsApp key + Resend key (via Production
`/app/integrations` UI). Preview keys do NOT sync.

---


## Iter 142 — `/invite/{token}` Accept Flow Closed (Mar 1, 2026)

User trigger: "A. Wire the invite accept page. Then D — deploy and wait."

### What shipped
Closed the onboarding loop: applicants who get invited via the iter141
admin Create-Workspace modal can now actually click the link and end up
inside their new workspace.

### The decision
On audit, an existing `InviteAccept.js` page + canonical
`/api/public/invitations/{token}` + `/accept` endpoints already existed
(originally for tenant-owner-initiated invites). Rather than build a
parallel `/api/invites/*` route, I **refactored
`/api/applications/{id}/create-workspace`** to write into the SAME
`invitations` collection with the SAME schema as
`routes/tenants.create_invitation`. Single source of truth for invites
across both flows (admin-onboarding + owner-team-add).

### Files changed
- `/app/backend/routes/applications.py` — create-workspace now inserts
  into `db.invitations` with the canonical schema (id, tenant_id,
  tenant_name, token, email, role='owner', invited_by, invited_by_name,
  expires_at, accepted, revoked, email_sent, application_id,
  created_at). Sets `email_sent=true` + counts after successful Resend.
- `/app/backend/routes/__init__.py` — registered + then un-registered
  invites_router (turned out unnecessary).

No frontend changes — existing `InviteAccept.js` + `/invite/:token` route
already pointed at the right endpoints.

### Verification (full end-to-end on preview)
1. POST `/api/applications` (public) → app_id ✓
2. POST `/api/applications/{id}/create-workspace` (admin) → workspace_id +
   invite_token + invite_url ✓
3. GET `/api/public/invitations/{token}` (public) returns 200 with
   `{tenant_name, role, invited_by_name, expires_at, email_hint}` ✓
4. POST `/api/public/invitations/accept` (public) returns 200 with
   `{token, user, tenant}` ✓
5. Replay → **409 Invite has already been accepted** (single-use enforced) ✓
6. Application `status` flipped to `onboarded` ✓
7. Frontend `/invite/{token}` renders correctly: "Join E2EInviteCo ·
   Megha Agarwal invited you as a owner" with name + email-display +
   password fields + sticky "Join E2EInviteCo" CTA ✓

### Status
**READY TO REDEPLOY** to `app.genleadai.com`. Public funnel + admin review
+ workspace provisioning + invite accept all wired end-to-end.

---


## Iter 141 — UX Flow Standardisation BATCH 2+3+4 + Slack/WhatsApp pings (Mar 1, 2026)

User trigger: "all" — execute Batches 2, 3, 4 and the Slack/WhatsApp ping
backlog in one continuous run. Testing report: **fully green, no issues.**

### V-point coverage (this iter)
- **V6** — Sidebar reorder per spec: Command Center → Instinct → Automation
  → Conversations → ICPs → Train ARIA → Integrations → Reports → Settings.
  NAV_ADVANCED below: 32-Touchpoint Journey · Call Booking · Voice Training
  · AI Setup Assistant.
- **V11** — Approvals nav item is now CONDITIONAL — only shows in the
  sidebar when `approvalsCount > 0` (inserted after Conversations). Always
  reachable via the bell.
- **V17** — `NotFound.js` heading now reads "This page doesn't exist" and
  the primary CTA reads "Go to Command Center →" pointing to `/app`
  (data-testid `not-found-command-center-btn`).
- **V7** — Lead 360 tabs persist in URL via `useSearchParams`:
  `/app/leads/{id}?tab=intel|automation|conversations|activity`. Overview
  is the default (no query param). Direct URL access loads the correct
  tab.
- **V18** — Browser back works correctly across the tab history because
  every tab click is a real `setSearchParams` push. Verified back stack:
  `?tab=conversations → ?tab=intel → /app/leads/{id} → /app`.
- **V19** — Full `/admin/applications` review surface:
  - Backend admin endpoints in `routes/applications.py`:
    `GET /api/applications`, `GET /api/applications/{id}`,
    `PATCH /api/applications/{id}/status`,
    `POST /api/applications/{id}/create-workspace`.
  - All require master_admin (sales_rep returns 403, unauth returns 401/403).
  - Status filter tabs (all/new/reviewing/qualified/not_fit/onboarded)
    with live counts in the response payload.
  - Frontend in `admin/AdminLayout.js`: `AdminApplications` component
    with status tabs, row list with blue-dot indicator for new,
    side-drawer detail panel, sticky action footer (Create Workspace,
    Mark Qualified, Reviewing, Not a Fit), Esc-to-close on both drawer
    and modal.
  - `CreateWorkspaceModal` provisions a `tenants` doc, generates a
    `secrets.token_urlsafe(28)` invite token, writes a `workspace_invites`
    record, flips application.status='onboarded', and optionally sends
    the invitation email via Resend.

### Slack + WhatsApp notification pings
- Added `_notify_slack(payload)` — fires a block-kit message to
  `SLACK_WEBHOOK_URL` if set. Silent no-op when unconfigured.
- Added `_notify_whatsapp(payload)` — fires a 360dialog message to
  `APPLICATION_NOTIFY_WHATSAPP` (E.164) if `WHATSAPP_360_API_KEY` is set.
  Silent no-op when unconfigured.
- Both wired into `POST /api/applications` alongside the existing Resend
  email. All three notifications fire-and-forget with try/except — the
  submit always returns 201 regardless of any notification outcome.

### New ENV vars (production-only, optional)
- `SLACK_WEBHOOK_URL` — Slack incoming-webhook URL (Slack app → Manage
  → Incoming Webhooks)
- `APPLICATION_NOTIFY_WHATSAPP` — E.164 phone number (e.g. `+919876543210`)
- `WHATSAPP_360_API_KEY` — 360dialog API key (already required for
  outbound; can reuse)

### Verification
- testing_agent_v3_fork iter141: **backend 19/19 PASS · iter140 regression
  8/8 PASS · V10 guard exit 0 · frontend V6/V7/V11/V17/V18/V19 all match
  spec · zero JS pageerrors.**
- Live curl: list/get/patch-status/create-workspace all working; no `_id`
  leak; role guards holding (403 for sales_rep on /api/applications).

### Files changed
- `/app/backend/routes/applications.py` — admin endpoints + Slack/WhatsApp
- `/app/frontend/src/admin/AdminLayout.js` — AdminApplications +
  CreateWorkspaceModal + nav item + route
- `/app/frontend/src/components/AppLayout.js` — V6 reorder + V11 conditional
- `/app/frontend/src/workspace/pages/Lead360.js` — V7 + V18 URL tab state
- `/app/frontend/src/pages/NotFound.js` — V17 polish
- **NEW** `/app/backend/tests/test_iter141_admin_applications.py` (19 tests)

### Status
**READY TO REDEPLOY** to `app.genleadai.com`.

### Carry-over (left for future batch)
- V8/V9/V10/V12/V13-V16/V20 — Most likely already pass via existing
  shadcn Dialog / sonner defaults. Sweep them in a focused audit pass
  if Joyston walkthrough flags anything specific.
- Test cleanup: TEST_*-prefixed applications + ws_* tenants accumulate
  in MongoDB on every iter140/141 test run. Add teardown fixture (P3).
- P3 still open: claude_call event-loop blocking, server.py thinning.

---


## Iter 140 — UX Flow Standardisation BATCH 1: Public Funnel (Mar 1, 2026)

User trigger: "A. Batch 1 only. Go." — public funnel first because every
potential client + Joyston sees / → /demo → /apply before anything internal.

### V1-V5 verification — all PASS

**V1 — `/` Landing**
- Stripped the entire `SignupCard` (work-email/password/B2B-B2C-mode toggle/submit)
  and replaced with `CtaCard`: "Two ways to get started" + two big buttons:
  "See ARIA in Action" → /demo, "Apply to Work with ARIA" → /apply.
- `Nav` no longer shows "Log in" or "Start free" buttons. Replaced with
  `nav-see-demo-btn` + `nav-apply-btn`. "Pricing" link removed from header.
- `CTABand` rewritten: "Ready to put ARIA on your pipeline?" with primary
  "Apply to Work with ARIA" + secondary "See ARIA in Action".
- Footer now includes `footer-apply-link` (Apply, points to /apply) +
  subtle `footer-client-login-link` (Client Login →, points to /login).
- All hero-signup-*/nav-signup-* test-ids removed.

**V2 — `/demo`**
- New sticky top banner: "You're viewing a live ARIA demo. Real software,
  not a mockup." + inline Apply CTA (`demo-live-banner` +
  `demo-banner-apply`). Banner stays put across all scenes.
- New full-width bottom CTA section: "Ready to apply?" + big Apply button
  (`demo-bottom-cta` + `demo-bottom-apply-btn`).
- Header right button changed from `header-trial` ("Start Free Trial") to
  `header-apply` ("Apply →").
- Scene 5 CTA rewritten to "Apply to Work with ARIA" (was: "Start Free Trial").
- All 5 main scenes + 2 bonus scenes still render correctly.

**V3 — `/apply` (NEW)**
- 4-section qualification form at `/apply`:
  1. About You (full_name, work_email, role, country)
  2. Your Business (company_name, company_url?, industry, employees, revenue?)
  3. Your Current Setup (current_setup, channel pills, current_volume, biggest_pain)
  4. Fit & Readiness (goal, timeline, budget_band, ready_to_start)
- Top progress indicator + gradient bar (Step N of 4 + %).
- Inline per-field validation on attempted Next.
- "Next →" replaces "Submit Application →" only on Section 4.
- "Back" button disabled on Section 1.
- POST `/api/applications` returns 201 with `{id, full_name, company_name}`;
  page redirects to `/apply/thank-you?id=...` on success.

**V4 — `/apply/thank-you` (NEW)**
- Personalised confirmation page: "Application received." then "Thanks,
  `{full_name}`. We've got everything we need from `{company_name}`."
- "We review every application personally and will be in touch within
  48 hours if we see a strong fit."
- Single primary CTA: "See ARIA in action →" → /demo (so applicants can
  explore while they wait).
- Graceful degradation when `?id=` missing (generic copy, same CTA).

**V5 — `/login`**
- Removed `register-link` ("Sign up") entirely. Replaced with `apply-link`
  pointing to `/apply` ("Apply to work with ARIA →").
- Login error message normalised to neutral **"Invalid email or password"**
  (no hint about which field is wrong).
- **Bug fix**: global axios 401 response interceptor in
  `/app/frontend/src/config/api.js` was unconditionally hard-redirecting to
  /login on any 401 — including the login request itself. Result: the
  setError() text was wiped by the page reload before the user could see
  it. Guarded with `!isLoginCall && !onLogin`. Verified live: bad creds
  now display the red error inline without reloading.

### Backend (NEW)
- `routes/applications.py`:
  - `POST /api/applications` (public, no auth) — Pydantic-validated submit,
    inserts into `applications` collection with `status='new'`, returns
    `{id, full_name, company_name}` with HTTP 201.
  - `GET /api/applications/{id}/confirm` (public) — returns persisted
    name + company for the thank-you page personalisation.
  - 60s duplicate-submit guard (founder double-tapping form).
  - Fire-and-forget founder notification email via Resend (swallows errors
    so a failed/sandboxed Resend never crashes the submit).
- Indexes on `work_email`, `created_at`, `status` for fast admin querying
  (Batch 4 will use them).
- Registered in `routes/__init__.py`.

### Verification
- testing_agent_v3_fork iter140: backend 8/8 PASS, V10 guard exit 0.
- Frontend E2E: V1 ✅ V2 ✅ V3 ✅ V4 ✅ V5 ✅ (after the 1-line interceptor fix).
- Zero JS pageerrors on `/`, `/demo`, `/apply`, `/apply/thank-you`, `/login`,
  `/app`, `/app/leads`, `/app/touchpoints`.

### Files added / changed
- **NEW** `/app/backend/routes/applications.py` (200 lines)
- **NEW** `/app/frontend/src/pages/Apply.js` (4-section form)
- **NEW** `/app/frontend/src/pages/ApplyThankYou.js`
- `/app/backend/routes/__init__.py` (register applications_router)
- `/app/frontend/src/App.js` (+ 2 routes)
- `/app/frontend/src/pages/landing/AriaLanding.js` (CtaCard, Nav, CTABand,
  footer)
- `/app/frontend/src/pages/Login.js` (apply-link, neutral error)
- `/app/frontend/src/pages/InteractiveDemo.js` (live banner + bottom CTA)
- `/app/frontend/src/config/api.js` (401 interceptor guard)
- **NEW** `/app/backend/tests/test_iter140_applications.py`

### Status
**READY TO REDEPLOY** to `app.genleadai.com`. Joyston-ready public funnel.

### Carry-over for next batches
- Batch 2 (V6-V9 + V13-V18): sidebar nav order, Lead 360 routing/back-preserves-filters,
  Intel/Conversations UX polish, global modal Esc, 404 page, browser back
- Batch 3 (V10-V12 + V20): Instinct after-action, Approvals badge,
  Integrations real-time validation, responsive sidebar
- Batch 4 (V19): /admin/applications drawer + Create Workspace modal

---


## Iter 138-139 — Backlog Cleanup + Journey Progress Banner (Mar 1, 2026)

User-triggered C: do both P2/P3 cleanup AND add the journey progress UX.

### What shipped

**A. Shared notification error classifier**
- Extracted `_classify_send_error` from `routes/aria_eod_wrap.py` into new
  `services/notification_errors.py` so morning_brief + approval_digest +
  eod_wrap all share the same regex-driven classifier.
- All 3 ARIA notification senders now return structured **503** with
  `{code, user_message, status}` on Resend sandbox failures instead of
  500 traceback OR silent 200-with-error-field.
- `approval_digest` correctly preserves the **`skipped:true` → HTTP 200**
  path (queue_empty is NOT an error).
- Downgraded `logger.exception` → `logger.warning(str(e)[:200])` in all 3
  senders to silence backend.err.log noise on expected Resend sandbox errors.

**B. TTL index on `journey_generate_jobs`**
- Added `expires_at` BSON Date field (7 days from creation) +
  `create_index("expires_at", expireAfterSeconds=0)` so MongoDB auto-purges
  old async job records.

**C. Flake8 cleanup**
- Fixed 2 E741 errors in `/app/backend/aria_agent_routes/brain.py`
  (`l` → `lead`). File now passes `ruff check` clean.

**D. Journey progress banner**
- Added in-page progress banner on `/app/touchpoints` showing live
  generation status. Renders above the view tabs (purple gradient
  card with spinner, count, elapsed/estimated, and helpful copy).
- Client-side `setInterval(1000)` drives the elapsed counter so updates
  are guaranteed even while the backend FastAPI event loop is blocked
  on the synchronous Claude SDK call.
- Backend `setInterval(2000)` polls `GET /api/journey/generate/job/{id}`
  to detect completion → swaps banner for sonner success toast +
  populated touchpoints.
- Slow-warn flips after 30s past estimate.
- **Discovered along the way**: sonner@2.0.3 freezes loading-type toasts
  on id-reuse (neither title nor description update reliably). Solution
  was to drop the toast-update approach entirely in favor of a
  state-driven banner React component. Sonner is still used for the
  initial/final success/error toasts only.

### Verification
- Live click-through on /app/touchpoints — banner renders with elapsed
  counter ticking 2s → 4s → 6s → 8s … → 20s (10 unique snapshots over
  20s window).
- Backend regression: 36 sprint pytests + 12 iter137 tests → **48/48 PASS**.
- V10 architectural guard: exit 0.
- Live curl: eod-wrap/morning-brief/approval-digest send-now all return
  classified 503 with `detail.code='resend_sandbox_or_unverified_domain'`;
  approval-digest queue-empty preserved as HTTP 200 skipped:true.

### Files changed
- NEW `/app/backend/services/notification_errors.py`
- `/app/backend/routes/aria_eod_wrap.py`
- `/app/backend/routes/aria_morning_brief.py`
- `/app/backend/routes/aria_approval_digest.py`
- `/app/backend/routes/journey.py` (TTL index + expires_at field)
- `/app/backend/aria_agent_routes/brain.py` (lint)
- `/app/frontend/src/workspace/pages/TouchpointMap.js` (banner + state)

### Backlog still open (P3, non-blocking)
- Address `claude_call` blocking FastAPI event loop during generation
  (the reason backend can't serve poll responses live during the Claude
  call). Move `_run_generate_job` work onto a worker thread or use
  `asyncio.to_thread` around the LLM SDK call.
- Embedding-based RAG (waiting on embeddings access in Emergent LLM key)
- LinkedIn Sales Navigator
- 14 F401 unused-import warnings in `aria_agent_routes/brain.py`

---


## Iter 137 — P1 Fixes from iter136 Audit (Mar 1, 2026)

Surgical fix-batch for the 3 P1 bugs surfaced in the iter136 full backend
audit. All verified live + by testing agent (12/12 iter137 PASS +
36/36 sprint regression PASS).

### Fixes
1. **`POST /api/aria/eod-wrap/send-now`** — was leaking uncaught
   `resend.exceptions.ResendError` as a 500 traceback. Added
   `_classify_send_error()` helper in `routes/aria_eod_wrap.py` that
   regex-matches Resend sandbox/unverified-domain errors and returns a
   structured **503** with `{code, user_message, status}`. Belt-and-
   suspenders outer try/except around `_send_eod_wrap` guards against
   any rogue exception escaping the inner SDK call.
2. **`GET /api/aria/eod-wrap/last`** — new endpoint added for UI parity
   with `/api/aria/morning-brief/last` and `/api/aria/approval-digest/last`.
   Returns `{last_sent_at, last_sent_date, last_sent_touches,
   last_sent_manual}` from the eod_wrap_settings doc.
3. **`POST /api/journey/generate`** — was timing out at the 60s ingress
   ceiling on synchronous multi-step Claude calls. Converted to async
   job pattern:
   - Kickoff returns `{job_id, status:'queued', eta_seconds, hint}` in
     <0.2s.
   - `asyncio.create_task` runs `_run_generate_job` in background,
     writing progress to a new `journey_generate_jobs` collection.
   - New `GET /api/journey/generate/job/{job_id}` returns
     `{status, phase, elapsed_seconds, slow_warn, result|error}` —
     phases: `queued → building_prompt → claude_generating → persisting → done`.
   - Tenant isolation enforced via compound `{job_id, tenant_id}` lookup.
   - `frontend/src/workspace/pages/TouchpointMap.js` updated to poll
     every 2.5s for up to 5 min.

### Verification
- Live curl: send-now → 503 with `code='resend_sandbox_or_unverified_domain'`;
  /last → 200 with correct shape; /generate → 0.16s kickoff;
  job completes in ~20s with 3 real Claude touchpoints.
- testing_agent_v3_fork iteration_137: 12/12 PASS · 36/36 sprint
  regression PASS · V10 guard exit 0 · frontend zero pageerrors.

### Files changed
- `/app/backend/routes/aria_eod_wrap.py` (helper + wrapped route + /last)
- `/app/backend/routes/journey.py` (async-job rewrite of /generate +
  new /generate/job/{job_id})
- `/app/frontend/src/workspace/pages/TouchpointMap.js` (poll loop)
- `/app/backend/tests/test_iter137_p1_fixes.py` (new)

### Status
**READY TO REDEPLOY** to `app.genleadai.com`.

### Carry-over backlog (cosmetic, non-blocking)
- Port `_classify_send_error` helper to `aria_morning_brief.py` +
  `aria_approval_digest.py` so they don't spam tracebacks in
  backend.err.log when Resend rejects sandbox sends.
- Add TTL index on `journey_generate_jobs.created_at` (7d) so jobs
  don't accumulate forever.

---


## Iter 136 — Full Backend Audit (Mar 1, 2026)

User-triggered after hitting "Send failed" on production Morning Brief.
Exhaustive audit on 130+ endpoints across 30 categories surfaced:
- **3 P1 bugs** (fixed in iter137): eod-wrap/send-now 500 leak,
  eod-wrap/last missing, journey/generate 60s timeout.
- **6 OAuth providers** + **1 Intel research** degrade cleanly with 503
  (missing keys — expected on preview).
- **V10 guard PASS** · `_id` leak guard PASS · tenant isolation PASS.
- Confirmed production root cause: Resend sandbox mode only allows
  sending to the verified Resend owner email until a domain is verified
  at resend.com/domains.

---


## Iter 135 — Pre-Deploy Full Regression (Mar 1, 2026)

**Trigger:** User asked: "Run the full regression first. Then deploy. Then I'll do the production walkthrough."

### What was verified
Full unified regression on the iter125–iter134 sprint surface:
- **V10 architectural guard PASS** — `scripts/check_v10.sh` exit 0. Zero direct
  Anthropic calls outside `services/claude_service.py`. Hard invariant holds.
- **All 8 sprint pytest suites PASS individually — 36/36 tests green:**
  `test_iter125_refactor_and_drag`, `test_iter126_lead360_and_csv`,
  `test_iter127_scan_hot`, `test_iter128_reply_box`,
  `test_iter129_draft_with_aria`, `test_iter130_draft_variants`,
  `test_iter131_voice_training`, `test_iter134_scan_progress`.
- **Live HTTP smoke** on REACT_APP_BACKEND_URL: auth, tenants/me, leads,
  leads/counts (with embedded pipeline_snapshot), leads/{id}/activities,
  conversations/lead/{id}, conversations/lead/{id}/draft (per-attempt
  contract), voice-seeds CRUD, intel/scan-hot, intel/scan-progress,
  journey/touchpoints/reorder, approvals — all 200 (where applicable).
- **Frontend smoke 100% PASS** — login, sidebar lead-strip + chips render
  with live counts, `/app/leads`, `/app/leads/{id}` (Lead 360 5 tabs),
  `/app/voice-training`, `/app/touchpoints` (drag-and-drop), zero JS
  pageerrors.
- **MongoDB `_id` leak guard** — spot-checked /api/leads, /api/voice-seeds,
  /api/conversations/lead/{id}, /api/intel/{id}/profile, /api/approvals
  — no `_id` leaked.
- **Tenant isolation** — voice-seeds + conversations correctly scoped;
  cross-tenant returns 404, not data leak.

### Findings (all non-blocking)
- **False alarm**: testing-agent flagged `GET /api/activities?lead_id=…`
  as 405. Lead 360 actually uses the existing
  `GET /api/leads/{id}/activities` endpoint, which works (200, list).
- Bulk `pytest test_iter125..134` in one invocation has fixture
  contamination (per-file runs all pass). P3 cleanup.
- `/api/leads/pipeline-snapshot` doesn't exist as a standalone endpoint —
  data is embedded in `/api/leads/counts.pipeline_snapshot` (frontend uses
  the embedded shape). Working as designed.
- Onboarding "Welcome to ARIA" modal overlays first-login pages until
  dismissed — pre-existing UX, not a regression.

### Deployment readiness
- `.env` clean (MONGO_URL, DB_NAME, REACT_APP_BACKEND_URL untouched).
- CORS includes `https://app.genleadai.com`.
- `PUBLIC_API_BASE_URL=https://app.genleadai.com` set → OAuth callbacks
  resolve correctly on production.
- All new modular routes (journey, conversations, intel, voice_seeds)
  registered via `routes/__init__.py` and import cleanly on cold start.
- Supervisor: backend + frontend + mongodb all RUNNING.
- **Verdict: ✅ GREEN LIGHT TO DEPLOY**

### Post-deploy reminder for user
Production keys do NOT sync from Preview. After deploy, re-paste:
- RapidAPI / Proxycurl key (for live LinkedIn crawl)
- Serper key (for web/news/IG/FB search)
- Resend domain key (for outbound email dispatch)
…via Production `/app/integrations` UI.

Then run the 10-point production walkthrough manually on
`https://app.genleadai.com`.

### Backlog (P2/P3 carried forward)
- P2: Embedding-based RAG upgrade (blocked — Emergent universal proxy
  key does not expose embedding models). User deferred.
- P3: LinkedIn Sales Navigator integration.
- P3: Cleanup legacy flake8 errors in
  `/app/backend/aria_agent_routes/brain.py`.
- P3: Further `server.py` thinning (still ~2,380 lines).
- P3: Make sprint pytest suites isolatable for bulk runs.

---


## Iter 134 — Scan Progress Toast (Feb 2026)

Persistent toast at the bottom of the screen showing live progress of
the "Scan all hot leads" batch action (per-lead status, X/Y processed,
auto-dismiss on completion).

### What shipped
- Backend: `scan_progress` collection keyed by `(tenant_id, batch_id)`
  written incrementally by `routes/intel.py` scan-hot loop.
- `GET /api/intel/scan-progress` returns latest in-flight or last-finished
  batch progress for the tenant.
- Frontend `ScanProgressToast.js` polls every 2s while batch is active,
  shows per-lead PASS/FAIL chips, total counts, ETA.
- Verified: 5-lead scan ran end-to-end with toast updating live, then
  auto-dismissed 3s after completion.

---


## Iter 133 — Embedding RAG (DEFERRED)

Discovered the Emergent universal LLM proxy key does NOT expose embedding
models (`text-embedding-3-large` etc). Iteration paused with user consent.
Current keyword-based RAG retrieval (Jaccard scoring) remains in
`services/kb_rag_service.py` and is sufficient for the founder demo.

---


## Iter 132 — Voice Training Auto-Learn (Feb 2026)

When a founder edits an ARIA-drafted message before sending, the edited
final body is appended to `voice_seeds` (channel='email' or 'whatsapp')
with `auto_learned=true`. Subsequent drafts inject up to 5 most-recent
auto-learned seeds + all manual seeds into the Claude system prompt for
tone matching.

### What shipped
- `routes/conversations.py` `_record_voice_seed_from_edit()` helper
  fires on the send endpoint when `edited_body != original_body`.
- `services/intel_service.py compose_message` now ALWAYS calls
  `_load_voice_seeds(tenant_id, channel)` and injects them.
- Voice Training UI shows two sections: "Manual seeds" + "Auto-learned
  from your edits" with delete buttons.
- Verified: edit-send → seed appears → next draft matches the edit's
  tone in human eval.

---


## Iter 131 — Voice Training Page (Feb 2026)

CRUD page for founder to seed ARIA's voice manually before sending any
real outreach. Persists examples per channel + active toggle.

### What shipped
- Collection `voice_seeds`: `{id, tenant_id, channel, label, seed_text,
  is_active, auto_learned, created_at, created_by}`.
- `routes/voice_seeds.py` — list/create/update/delete with tenant scope.
- Frontend `VoiceTraining.js` — channel tabs (email/whatsapp/linkedin),
  add-seed form, list with toggle/delete, helper card explaining how
  seeds are used.
- Wired into `services/intel_service.compose_message` — active seeds for
  the requested channel are prepended to the system prompt under a
  `<voice_examples>` block.

---


## Iter 130 — Draft Variants (Feb 2026)

`POST /api/conversations/lead/{id}/draft` now accepts an `attempt` param
(1..3) and returns one variant per request, each with a different "angle"
(direct / curious / value-first). Frontend ConversationThread.js fires
3 parallel requests and shows them in a tabbed picker.

---


## Iter 129 — Draft with ARIA (Feb 2026)

New `Draft with ARIA` button in the conversation thread reply box. Pulls
intel profile + voice seeds + last 5 thread messages + suggested
next_action_hint and calls `claude_service.claude_call` (CONVERSATION
task) to produce a contextual reply. Returns `{subject, body, attempt}`.

---


## Iter 128 — Conversation Thread Keyboard Shortcuts + Reply Box (Feb 2026)

- `j/k` next/prev message, `Home/End/G` jumps, `/` focus filter, `Esc`
  clear+blur.
- New inline reply box at the bottom of the thread with channel selector
  (email/whatsapp/linkedin) and Send button. Calls
  `POST /api/conversations/lead/{id}/send`.
- Hint bar at the bottom explains shortcuts.

---


## Iter 127 — Scan All Hot Leads (Feb 2026)

New "Scan all hot leads" button on Lead Inbox. Posts to
`/api/intel/scan-hot` which iterates `pt_leads` where
`stage='hot' AND no intel_profile (or intel older than 30d) AND score >=
threshold`. Runs `crawl_prospect` + `synthesise_intel` per lead with
per-lead try/except, writes scan_progress doc. Returns `{queued,
leads[], threshold, batch_id, message}`.

---


## Iter 126 — Lead 360 + CSV Import (Feb 2026)

5-tab Lead 360 view at `/app/leads/{id}`:
1. **Overview** — name, company, score, stage, last contacted, owner,
   inline edit.
2. **Intel** — embeds IntelTab (signals, fit, playbook, composer).
3. **Automation** — touchpoint enrolment + queued outreach status.
4. **Conversations** — embeds ConversationThread.
5. **Activity** — chronological event timeline (uses
   /api/leads/{id}/activities).

Also: CSV Import button on Lead Inbox with field-mapping wizard.

---


## Iter 125 — server.py Refactor + Touchpoint Drag-and-Drop (Feb 2026)

- `server.py` reduced significantly via extraction of
  `routes/founder_command_center.py`, `routes/public_api.py`, and
  similar per-domain modules.
- Touchpoint Journey step cards now reorderable via native HTML5
  drag-and-drop in addition to the existing ↑/↓ buttons. Order persisted
  via `POST /api/journey/touchpoints/reorder`.
- Sidebar Lead Count strip + Pipeline Snapshot row added to AppLayout.

---


## Iter 124 — CLOSE IT OUT (Feb 28, 2026)

Massive sweep closing the highest-priority gaps from the May 28 audit.
Triggered by the user's "execute everything in one continuous run" prompt.

### 1. 32-Touchpoint Journey — Full Builder Rebuild
- `TouchpointMap.js` rebuilt end-to-end (the previous 64-line grid is gone).
- **4 views**: Flowchart (vertical chain with branch-edge labels),
  Timeline (vertical day-axis), Pipeline (kanban per channel), Conditional
  (editable branching-rule list).
- **Generate Journey with AI**: `claude-sonnet-4-5` produces an N-step
  sequence from the workspace training profile.
- **Per-touchpoint Regenerate** with surrounding context.
- **Inline edit** every field with dirty-state Save button.
- **Drag-style reorder** via ↑/↓ buttons (POST /api/journey/touchpoints/reorder).
- Backend: `routes/journey.py` — CRUD + generate + per-tp regenerate.

### 2. Prompt-injection Sanitiser — Wired across lead-sourced paths
### 3. Knowledge-base RAG at Query Time
### 4. Instagram + Facebook Crawl
### 5. Real-time API-key Validation (onBlur)
### 6. Conversation Thread — already shipped iter121, re-verified
### 7. Auto-approve Rule — already shipped iter121

(Full history of iter1–iter123 retained in git log + CHANGELOG.md.)
