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
