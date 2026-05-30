# ARIA — Complete System Intelligence

> **Purpose of this doc:** A self-contained briefing on what ARIA is, what it does, how it's wired, and where every feature lives. Paste this verbatim into any Claude (or other LLM) chat to discuss architecture, debug issues, or plan additions.

---

## 1. Product summary (the elevator pitch)

**ARIA = a fully autonomous B2C + B2B sales agent that founders run their growth on.**

- Captures leads from any channel → enriches each lead with public web/LinkedIn/social signals → drafts and sends outreach in the founder's own voice → tracks every reply → books calls → and reports back every morning and evening.
- Founders interact with ARIA the way they'd interact with a top SDR + ops manager combined: through one **Command Center**, a **Lead 360** view per prospect, a 5-tab message thread per conversation, and a **Daily/Morning Brief** stream.
- The product is multi-tenant (workspaces) with per-tenant integrations stored encrypted in a universal `integration_configs` store. The current flagship workspace is **Pietential** (consumer well-being product) deployed at `app.genleadai.com`.

---

## 2. Architecture (one-liner per layer)

| Layer | Stack | Notes |
|-------|-------|-------|
| **Frontend** | React 19 + React Router · Tailwind · shadcn/ui · Phosphor icons · Sonner toasts · `axios` | Vite-style hot reload, served on port 3000 |
| **Backend** | FastAPI on uvicorn (port 8001), supervisord-managed | 470+ endpoints across 83 route modules |
| **Database** | MongoDB (pymongo sync) with **80+ collections** | All queries are tenant-scoped via `tenant_id` |
| **LLM** | Anthropic Claude (Sonnet 4.5 + Haiku) via Emergent universal LLM key | **All LLM calls routed through `services/claude_service.py`** — enforced by `scripts/check_v10.sh` |
| **Encryption** | Fernet for all 3rd-party API keys in `integration_configs` | One symmetric key per workspace |
| **Background jobs** | Python async loops (cron-style) + `asyncio.create_task` detached tasks | Morning Brief, EOD Wrap, batch intel scans |
| **Deployment** | Emergent platform (Kubernetes-backed) · Preview + Production environments | Production = `app.genleadai.com`, preview keys do NOT sync |

### The V10 Architectural Rule (hard constraint)
> Only `/app/backend/services/claude_service.py` is allowed to import `LlmChat`, `with_model`, or call `anthropic.messages.create`. Every other file talks to Claude through this wrapper. Enforced by a pre-commit check at `scripts/check_v10.sh`.

---

## 3. Multi-tenancy model

```
User → Tenant Membership → Tenant (workspace) → All data scoped by tenant_id
                                        ↓
                  integration_configs (Fernet-encrypted keys)
                                        ↓
                   Anthropic · RapidAPI · Serper · 360dialog
                   Resend · Apollo · Saleshandy · Google Calendar
```

- **Collections that gate everything:** `tenants`, `tenant_memberships`, `tenant_users`
- **One admin user** can belong to multiple tenants (e.g., Demo + Pietential workspaces) and switches via a workspace switcher in the topbar. Switching fires `aria:tenant-changed` window event so all polling re-fetches with the new tenant context.
- **Active tenant is resolved server-side** via `routes/tenants.get_active_tenant` dependency.

---

## 4. Core features (mapped to where they live)

### 4.1 Lead capture (multi-source ingestion)

| Source | Backend route | Frontend page |
|--------|---------------|---------------|
| Public form embed | `POST /api/form/submit` (no auth) | `GET /api/form/embed-code` returns paste-ready HTML |
| Public API (Zapier/Make) | `POST /api/v1/leads` (X-API-Key header) | `routes/public_api.py` |
| CSV / XLSX import | `POST /api/leads/import-csv/preview` + `/import-csv` | "Import CSV" button on `/app/leads` (4-step modal: upload → map → preview → result) |
| Meta Ads webhook | `POST /api/webhooks/meta` | `routes/webhooks_inbound.py` |
| 360dialog WhatsApp inbound | `POST /api/webhooks/whatsapp/360dialog` | `routes/webhooks_whatsapp.py` |
| Calendly inbound | `POST /api/webhooks/calendly` | Auto-sends a pre-call brochure |
| Cold calls / referrals / etc. | Manual via "Add lead" modal | `LeadInbox.js` |

All sources de-dupe by email + phone before insert. Each insert writes an `activities` row stamped with the source channel.

### 4.2 ICP scoring + classification
- Every new lead is run through ICP scoring (`routes/classification.py`, `routes/pt_lead_scoring.py`) producing `icp_score` (0-100) + `icp_tier` (`hot` / `warm` / `cold`) + Claude-written `icp_match_reason`.
- ICPs are defined per tenant via `/app/icp` page (`routes/icps.py`).

### 4.3 Intel scanning (the killer feature)
Lives in **`services/crawl_service.py`** + **`services/intel_service.py`**.

**Pipeline:**
1. `crawl_prospect()` fans out to:
   - **RapidAPI LinkedIn Scraper** (host-aware dispatch: `linkedin-data-api.p.rapidapi.com` default, fallback to `fresh-linkedin-profile-data.p.rapidapi.com`)
   - **Serper** for web + news + Instagram + Facebook
2. `synthesise_intel()` feeds raw signals to Claude (via `claude_service.py`) and writes a structured **intel profile** to `intel_profiles`:
   - `who_they_are_now` · `what_they_re_talking_about` · `recent_signals` · `personal_interests` · `outreach_window` · `risk_signals`
3. Results are cached per lead with `last_scanned_at` + `next_scan_at`.

**UI entry points:**
- Lead 360 → **Intel tab** (single lead) — `/app/frontend/src/workspace/pages/IntelTab.js`
- Lead Inbox → **"Scan all hot leads"** button (batch, ICP ≥ 80) → `POST /api/intel/scan-hot` returns `batch_id`
- Live progress toast polls `GET /api/intel/scan-hot/status/{batch_id}` every 4s, updates "12/28 done", final toast says succeeded/failed split

### 4.4 Outreach generation + dispatch
**The drafting chokepoint** is `services/intel_service.compose_message`. Every "Draft with ARIA", "Start Outreach", Touchpoint engine send, and Morning Brief outreach goes through it.

**Personalisation layers (in order):**
1. **Lead's intel profile** (whose are they, what are they talking about, signals)
2. **Founder's voice seeds** — pasted past messages stored in `voice_seeds` collection; injected as a "TONE EXAMPLES" block. Channel-filtered (whatsapp / email / linkedin / any). Max 5 per prompt.
3. **Channel-specific rules** (WhatsApp ≤ 90 chars · Email ≤ 150 words · LinkedIn ≤ 300 chars)
4. **`user_steer`** — optional founder one-liner ("emphasise our 30-day pilot")
5. **Attempt nudges** — `attempt=1|2|3` shifts angle: default → contrarian hook → radically short direct ask

**Dispatch chokepoint:** `services/outreach_dispatch.dispatch_outreach`. Every outbound (Touchpoint engine, manual reply box, Send-via-ARIA on Intel tab) goes through it. It:
- Resolves the right provider per channel (Resend for email, 360dialog for WhatsApp, manual export for LinkedIn)
- Logs to `outbound_log` with `actor_user_id` ("aria" or "owner") for attribution
- Returns `{sent, logged_only, provider, provider_id, error}` — `logged_only=True` when no provider creds (so demos work without a paid integration)

### 4.5 Voice Training (founder's voice signature)
Page: `/app/voice-training` · file: `frontend/src/workspace/pages/VoiceTraining.js`

- Paste 3–10 past WhatsApp/email/LinkedIn messages of your own
- Each seed: `{channel, text, label, active}` · tenant-scoped · max 10
- `GET /api/voice-seeds/preview?channel=…` shows the literal TONE EXAMPLES block that's injected into Claude's prompt
- **Auto-learn:** when founder edits an ARIA-drafted message before clicking Send, a 5-second toast appears with `[Learn ✓]` button. Clicking it saves the edited version as a new seed labelled "Auto-learned <date>". So the voice gets sharper with every send.

### 4.6 Lead 360 (single-lead command surface)
Route: `/app/leads/:id` · file: `frontend/src/workspace/pages/Lead360.js`

**Sticky header:**
- Avatar · name + title + company · ICP badge · stage tag · source icon · last-activity time
- Quick actions: Send Message · **Run Intel Scan** · Book Call · **Change Stage ▾** · **Connect ▾** (Add to Journey, Enrol Sequence, Book Call, Send to Approval Queue, Suppress)

**5 tabs:**
1. **Overview** — Contact / Company / ICP-match / Source cards (left) · Notes auto-save + Tags + Assigned-to (right)
2. **Intel** — Mounts `IntelTab.js`: scan controls, signal history, Outreach Playbook (channel switcher, Send-via-ARIA, Edit+Send, Copy)
3. **Automation** — Always-visible CTA row · Active Sequences · Touchpoint Journey state · Automation rules fired
4. **Conversations** — Mounts `ConversationThread.js`: chat-style timeline newest-at-bottom, channel filter, **reply box with Draft with ARIA + variant cycling**, **keyboard shortcuts** (`j/k` nav, `r` reply, `e` send-as toggle, `d` draft, `⌘/Ctrl+Enter` send, `Esc` close)
5. **Activity** — Full audit timeline with channel icons, filter by All / ARIA / Owner / Lead / System

### 4.7 32-Touchpoint Journey builder
Page: `/app/touchpoints` · files: `JourneyFlowchart.jsx` (visual flowchart view) + `TouchpointMap.js` (parent state)

- Visual 3-column flowchart matching user's design reference (step number · channel pill · message preview · conditional logic node)
- **Drag-and-drop reorder** (HTML5 DnD, no extra deps) with `DotsSixVertical` grab handle, purple glow on drop target, source-card dim while dragging
- **Hover-only "Insert step" pill** between every pair of cards — shifts later steps' numbers +1 and creates a blank touchpoint
- **AI generation:** "Generate Journey with Claude" → calls Claude via `routes/journey.py` to produce all 32 touchpoints from the workspace's ICP + brand voice in one shot
- Templates per business type seeded from `touchpoint_templates_seed.py`
- Active leads have a `touchpoint_engine` running in the background that ticks daily and fires the next touchpoint via `dispatch_outreach`

### 4.8 Command Center (founder dashboard)
Page: `/app` · file: `CommandCenter.js`

Rows top-to-bottom:
1. **AI Summary topbar drawer** (slide-out) — overnight changes summary
2. **Daily Brief card** — "Your team captured X new leads last 24h. Y are hot. Z follow-ups overdue."
3. **4-column KPI grid** — leads / replies / calls booked / pipeline value
4. **Pipeline Snapshot row** (iter126) — 5 clickable chips: Total · Qualified · Nurturing · Needs attention · Calls this week — each navigates to `/app/leads` with the filter pre-applied
5. **Founder Command Center insights** — revenue leakage %, money at risk, hot leads untouched, first-response time, proposal graveyard, source quality, lost reasons
6. **Workspace setup health** + **Next scan** countdown

### 4.9 Approval Queue + Auto-approve
Page: `/app/approvals` · file: `routes/approvals.py`

- ARIA proposes outreach → enters `pending_outreach` collection → founder reviews + approves/edits/rejects
- **Auto-approve rules** (per channel / per ICP tier) — set via `aria_auto_approve_config` so trusted segments fire automatically
- **Approval digest email** — daily summary of approved sends + replies received

### 4.10 Morning Brief + EOD Wrap (the cron loops)
- **Morning Brief** (`routes/aria_morning_brief.py`) — runs at 8 AM workspace time, sends a 5-bullet email: new leads, hot leads, calls today, replies needing attention, top 3 actions
- **EOD Wrap** (`routes/aria_eod_wrap.py`) — runs at 8 PM, sends "today's wins" + tomorrow's top 3 prospects
- Both surfaceable in-app via `GET /api/aria/today` so the dashboard doesn't have to wait for the email

### 4.11 Integrations hub
Page: `/app/integrations` · file: `routes/integrations_hub.py`, `routes/oauth_integrations.py`, `routes/oauth_providers.py`

- **Universal `integration_configs` store** — every provider's keys live here, Fernet-encrypted, tenant-scoped
- **Real-time validation onBlur** — Connect modals fire `POST /api/integrations/{provider}/validate-key` while you type
- **Live test ping** — `POST /api/integrations/{provider}/test` hits the actual provider API to confirm
- **Holistic status** — `GET /api/integrations/status` returns one row per provider with `{configured, last_tested_at, last_test_ok}` — this feeds the **Instinct Feed page** at `/app/instinct` showing green/amber/red pills

**Supported providers:**
- LLM: Anthropic (universal key, no user setup needed)
- Crawl: **RapidAPI** (LinkedIn) — replaces deprecated Proxycurl · **Serper** (Web, News, IG, FB)
- Outreach: Resend (email), 360dialog (WhatsApp), Apollo, Saleshandy
- Calendar: Google Calendar (OAuth)
- Webhooks: Calendly, Meta Ads, generic inbound

### 4.12 Knowledge Base RAG
File: `services/kb_rag_service.py`

- Each tenant has a KB of docs (uploaded by founder via `/app/aria-resources`)
- On every Claude conversation query, top-K matching chunks are stitched into the system prompt as "KNOWLEDGE" before generation
- Currently **naive text search** (BM25-like) — embedding upgrade was scoped (iter133) but deferred because the Emergent universal key proxy doesn't expose embedding models. Will revisit at >500 doc KBs.

### 4.13 Sidebar Lead Count (live polling)
File: `components/AppLayout.js`

Below the ARIA brand header in the sidebar:
- Green dot (leads exist) / grey dot (empty) + total count
- 4 stage chips: Qualified · Nurturing · New · Cold
- Polls `GET /api/leads/counts` every 30s, re-fetches on tenant switch
- Click navigates to `/app/leads`

### 4.14 Universal AI Summary drawer
File: `components/AiSummaryDrawer.js` · topbar button on every page

- Slide-out from the right
- Asks Claude (via `claude_service.py`) "what changed since I last looked at ARIA?" — answers with a 3-5 bullet summary grounded in `activities`, `outbound_log`, `inbound_messages`, `intel_profiles`

### 4.15 Train ARIA (knowledge ingestion)
Pages: `/app/train-aria` (legacy) + `/app/train-aria-v2` (current) · files: `routes/aria_training.py`

- Founder uploads: company decks, past sales emails, FAQs, brand voice docs
- Background job: `training_extraction_jobs` → Claude extracts {company facts, tone signature, ICP definitions, sales playbook}
- Versioned in `aria_training_versions` so you can roll back

### 4.16 Onboarding + Time-to-Value
- Real-time onboarding wizard at `/onboarding` — `routes/realtime_onboarding.py`
- Per-user **TTV milestones** (signup → first lead → first ARIA conversation → first meeting booked → first deal won) — `routes/onboarding_legacy.py`

---

## 5. Database schema (collection-level overview)

**Total: 80+ collections.** Grouped by domain:

### Identity + tenant
`users` · `tenants` · `tenant_memberships` · `tenant_users` · `tenant_notification_prefs` · `invitations` · `auth_codes` · `auth_code_requests` · `workspace_contacts` · `workspace_settings`

### Lead pipeline
`leads` (legacy, ObjectId-keyed) · `pt_leads` (Pietential, string-id-keyed) · `pt_companies` · `accounts` · `icps` · `activities` · `campaigns` · `pt_campaigns` · `pt_tasks` · `pt_notes`

### Outreach + conversations
`outbound_log` · `outbound_messages` · `pending_outreach` · `inbound_messages` · `failed_message_log` · `email_delivery_log` · `conversations` · `aria_conversations` · `sequences` · `sequence_enrolments` · `outreach_campaigns` · `outreach_campaign_logs` · `outreach_touchpoints`

### Intel + crawl
`intel_profiles` · `prospect_crawl_log` · `pt_insights` · `pt_events` · `pt_training_signals`

### Touchpoint engine
`touchpoints` · `touchpoint_templates` · `touchpoint_logs` · `touchpoint_map_versions` · `touchpoint_ai_quality_cache` · `workspace_touchpoint_maps`

### ARIA brain + voice
`aria_actions` · `aria_alerts` · `aria_resources` · `aria_training` · `aria_training_versions` · `aria_settings` · **`voice_seeds`**

### Daily flows
`aria_morning_brief_config` · `aria_morning_brief_sent` · `aria_approval_digest_config` · `aria_approval_digest_sent` · `aria_auto_approve_config` · `aria_auto_approve_usage` · `eod_wrap_settings` · `daily_call_plan_settings` · `time_to_value` · `ai_summary_cache`

### Automation
`automation_rules` · `automation_rule_fires` · `pt_automation_logs` · `classification_log` · `classification_triggers`

### Integrations + admin
`integration_configs` · `integration_events` · `integration_import_logs` · `integration_key_status` · `integration_requests` · `integration_waitlist` · `crm_integrations` · `crm_sync_log` · `pt_integrations`

### Calls + billing + ops
`call_booking_settings` · `call_bookings` · `subscriptions` · `payments` · `payment_transactions` · `billing_*` · `audit_log` · `api_keys` · `api_usage_log` · `beta_feedback` · `contact_requests` · `contact_rate_limit` · `contact_campaign_status` · `dfy_inquiries` · `data_deletion_log` · `platform_config` · `webhook_replay_seen`

---

## 6. The keyboard shortcuts (Conversations tab)

| Key | Action |
|-----|--------|
| `j` / ↓ | Next message |
| `k` / ↑ | Previous message |
| `Home` | First message |
| `End` / `G` | Last message |
| `/` | Focus filter input |
| `r` | Focus reply textarea |
| `d` | Draft with ARIA (cycles attempts 1→2→3) |
| `e` | Toggle Send-as ARIA ⇄ Send-as me |
| `⌘/Ctrl + Enter` (inside textarea) | Send |
| `Esc` | Cascaded: blur textarea → clear filter → drop active row |

---

## 7. Iteration history (last 10 ships)

| Iter | What shipped |
|------|--------------|
| iter125 | **server.py refactor** — 3,254 → 2,382 lines. Extracted Founder Command Center, Public API, API keys, Audit log + exports, Onboarding-legacy + TTV into separate route modules. |
| iter126 | **Lead 360 (5-tab view)** + **Sidebar lead count strip** + **Command Center Pipeline Snapshot row** + **CSV import button** + **Journey insert-blank**. |
| iter127 | **"Scan all hot leads"** batch action — async background tasks, ICP ≥ 80 floor, configurable cap. |
| iter128 | **Conversation reply box** + first keyboard shortcuts (`r`, `e`, `⌘/Ctrl+Enter`). Wired through `dispatch_outreach` for owner/ARIA attribution. |
| iter129 | **Draft with ARIA** button — single-shot draft using channel-adaptive composer + intel profile. Refusal-guard fallback for prospects with no intel. |
| iter130 | **Draft variants** — `attempt: 1\|2\|3` cycles default → contrarian hook → radically short direct ask. Button morphs: "Draft with ARIA" → "Try another (1/3)" → "Variant 3/3" (disabled). |
| iter131 | **Voice Training page** — paste 3–10 past messages per channel. TONE EXAMPLES block injected into compose_message. Channel-filtered + 10-seed cap. |
| iter132 | **Auto-learn voice** — when founder edits ARIA's draft before sending, a 5s toast with `[Learn ✓]` saves the edit as a new voice seed. |
| iter133 | **DEFERRED** — embedding RAG. Emergent universal LLM key proxy doesn't expose embedding models. Keeping naive keyword search until KB grows past 500 docs. |
| iter134 | **Scan progress toast** — sticky `toast.loading` polls `/api/intel/scan-hot/status/{batch_id}` every 4s, shows "12/28 done", final toast diagnoses succeeded/failed split. |

---

## 8. Hot paths Claude can help debug

### "Drafts feel generic"
- Check the lead has an `intel_profile` row → if not, run Intel scan first
- Check `voice_seeds` collection for that tenant — if empty, drafts use default ARIA voice
- Inspect `tone_block` via `GET /api/voice-seeds/preview?channel=…`

### "Outreach didn't send"
- `outbound_log` row should exist with `actor_user_id` + `status`
- If `logged_only=True` → provider creds missing in `integration_configs`
- If `error` field populated → check provider returned message (Resend domain limit, 360dialog template approval, etc.)

### "Intel scan returns 403"
- Almost always RapidAPI account not subscribed to "Real-Time LinkedIn Scraper" tier
- Check `integration_key_status.last_test_ok` for the RapidAPI row

### "Sidebar lead count empty on production"
- 30s polling — wait one cycle on hard refresh
- Tenant context: confirm active tenant in workspace switcher has leads

### "Drafts not adopting my voice"
- Verify `active=True` on seeds
- Verify seed channel matches draft channel (or set to `any`)
- Verify `intel_service.compose_message` is actually being reached (not a fallback path)

---

## 9. Files Claude should know about (top 20)

| File | Why it matters |
|------|----------------|
| `/app/backend/services/claude_service.py` | **The only Anthropic chokepoint.** Every LLM call passes through here. |
| `/app/backend/services/intel_service.py` | `synthesise_intel()` + `compose_message()`. The brain of every draft. |
| `/app/backend/services/crawl_service.py` | RapidAPI + Serper dispatcher. Host-aware fan-out. |
| `/app/backend/services/outreach_dispatch.py` | The only outbound chokepoint. Email/WhatsApp/LinkedIn unified. |
| `/app/backend/services/kb_rag_service.py` | Knowledge-base retrieval (currently keyword scoring). |
| `/app/backend/routes/intel.py` | Intel endpoints + `/scan-hot` batch + status polling. |
| `/app/backend/routes/conversations.py` | Send + Draft + Draft-variants endpoints. |
| `/app/backend/routes/voice_seeds.py` | Voice Training CRUD + `render_tone_block` helper. |
| `/app/backend/routes/journey.py` | 32-Touchpoint CRUD + Claude generation + reorder. |
| `/app/backend/routes/lead_counts.py` | Sidebar strip + Pipeline Snapshot aggregator. |
| `/app/backend/routes/integrations_hub.py` | Universal `integration_configs` store. |
| `/app/backend/routes/approvals.py` | Pending outreach + auto-approve rules. |
| `/app/backend/routes/aria_morning_brief.py` + `aria_eod_wrap.py` | The two cron loops founders feel daily. |
| `/app/backend/server.py` | App composition; mostly thin now after iter125 split (2,382 lines). |
| `/app/frontend/src/workspace/pages/Lead360.js` | The 5-tab single-lead command surface. |
| `/app/frontend/src/workspace/pages/IntelTab.js` | Scan + signals + Outreach Playbook. |
| `/app/frontend/src/workspace/pages/ConversationThread.js` | Reply box + Draft with ARIA + shortcuts + auto-learn. |
| `/app/frontend/src/workspace/pages/VoiceTraining.js` | Voice signature CRUD. |
| `/app/frontend/src/workspace/pages/JourneyFlowchart.jsx` | 32-Touchpoint visual builder. |
| `/app/frontend/src/components/AppLayout.js` | Sidebar (with lead-count strip), topbar, theme toggle, tour. |

---

## 10. What's NOT yet built (open backlog)

| Pri | Item | Why deferred |
|-----|------|--------------|
| P2 | Embedding-based RAG (Voyage / OpenAI / Cohere) | Needs separate paid key — Emergent universal key proxy doesn't expose embedding models. Keyword search adequate <500 docs/KB. |
| P3 | LinkedIn Sales Navigator integration | Larger lift; needs RapidAPI endpoint variant + filter-save UI. |
| Cleanup | Legacy linting errors in `routes/aria_agent_routes/brain.py` | Pure hygiene, no UX impact. |

---

## 11. The single most important thing about ARIA

**ARIA is opinionated about *how* it sends.**

Most "AI SDR" tools generate templated messages and blast them. ARIA refuses to draft without ground truth — that's why:
- Every draft is gated on the lead's `intel_profile` (signals from web/social)
- The voice-seed system means every send sounds like *the founder*, not like default ARIA
- The auto-learn loop closes the gap automatically — every manual edit becomes a tone signal
- The 32-Touchpoint Journey + Approval Queue + Auto-Approve rules let founders dial autonomy from "review every send" to "fully hands-off for ICP=hot" without rewriting the engine

That tight loop — **real signals → founder voice → channel-adaptive draft → tracked send → auto-learn from edits** — is what separates ARIA from generic AI sales tools.

---

*Generated by E1 (Emergent main agent) · iter134 snapshot · 2026-02-29*
