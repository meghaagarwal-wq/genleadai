# CLAUDE.md — GenLeadAI (ARIA) Project Reference

## Rules for AI Assistants

- **Do not change** deployment, hosting, Docker, env, secrets, or infrastructure files unless explicitly asked.
- **Do not commit directly to `main`.** Always create a new branch and open a PR.
- **Do not edit any file** outside the scope of the task at hand.
- Follow the V10 guard: all Claude/LLM calls must go through `services/claude_service.py` only. Never import Anthropic directly in route or utility files. Enforce with `scripts/check_v10.sh`.
- All interactive frontend elements must include a `data-testid` attribute.
- Match the existing dark-mode design system (see `design_guidelines.json`): `#0A0A0A` background, `#0055FF` primary blue, `#8B5CF6` AI purple, Cabinet Grotesk headings, IBM Plex Sans body.

---

## What This Project Is

**GenLeadAI / ARIA** is a multi-tenant SaaS sales automation platform. ARIA acts as an autonomous sales agent: it captures leads from any channel, enriches them via LinkedIn/web scraping, generates personalized outreach in the founder's voice, dispatches messages (email + WhatsApp), and sends daily summaries to founders.

Deployed at `https://app.genleadai.com` via Emergent (Kubernetes-backed). Two flagship tenants: `ten_demo` (demo) and `ten_pietential` (Pietential workspace).

---

## Frontend

**Stack:** React 19 · React Router v7 · Tailwind CSS v3 · shadcn/ui (Radix) · TanStack React Query v5 · Axios · Recharts · Framer Motion · Sonner · React Hook Form + Zod

**Structure:**
```
frontend/src/
├── App.js                  # Central route registry (~30+ routes)
├── config/api.js           # Axios instance — injects Bearer token + X-Tenant-Id on every request
├── context/                # AuthContext, WorkspaceContext, PlanContext, ThemeContext
├── hooks/                  # useChannelEnabled, useTtvMilestoneWatcher, use-toast
├── pages/                  # Public/auth pages: Login, Signup, /apply, /invite
├── workspace/pages/        # All /app/* dashboard pages
├── admin/                  # Master-admin panel (/admin/*)
├── components/             # Shared UI (AppLayout, AriaCommandRoom, shadcn/ui primitives)
└── public/                 # Marketing/SEO pages (/aria/*, use-cases, comparisons)
```

**Route map:**
- `/login`, `/signup`, `/apply`, `/invite/:token` — public auth
- `/demo`, `/demo-sandbox` — interactive demo
- `/aria/*` — marketing pages (SEO)
- `/admin/*` — super-admin panel (master_admin role only)
- `/onboarding*` — workspace setup wizard
- `/app/*` — main client dashboard (AppLayout shell)
  - `/app/` → CommandCenter (KPI grid, pipeline, insights)
  - `/app/leads` → Lead Inbox
  - `/app/leads/:id` → Lead 360 (5 tabs: Overview / Intel / Automation / Conversations / Activity)
  - `/app/instinct` → Intelligence Feed (Pietential B2B)
  - `/app/touchpoints` → Journey builder (32-step flowchart)
  - `/app/voice-training` → Voice seed trainer
  - `/app/integrations` → Integration hub
  - `/app/conversations` → Unified thread view
  - `/app/settings` → Workspace + user settings

**Key patterns:**
- Every API call sends `X-Tenant-Id` header for multi-tenancy.
- 401 responses auto-redirect to `/login`.
- Workspace switcher fires `aria:tenant-changed` window event → child pages refetch.
- TanStack React Query with `refetchOnWindowFocus: false` for async state.

---

## Backend

**Stack:** FastAPI 0.110 · uvicorn (port 8001) · MongoDB (pymongo sync) · Pydantic v2 · JWT (HS256) · Fernet encryption · SlowAPI rate limiting · httpx

**Entry point:** `backend/server.py`
- Registers 83 modular route blueprints via `register_all_routes(app)`.
- Starts background loops on startup (engine, polling, morning brief, EOD wrap).
- Manages CORS whitelist, exception handlers, startup migrations and index creation.

**Route organization (`backend/routes/`):**

| Category | Key Files |
|---|---|
| Auth | `auth.py`, `auth_extras.py`, `user_profile.py` |
| Tenants / Workspaces | `tenants.py`, `contact.py` |
| Leads | `pietential.py`, `pt_leads.py`, `lead_query.py`, `lead_counts.py` |
| Intelligence / Enrichment | `intel.py`, `crawl_service.py` |
| Conversations / Outreach | `conversations.py`, `touchpoints.py`, `touchpoint_engine.py` |
| Automations | `journey.py`, `automation_rules.py` |
| Integrations | `integrations_hub.py`, `oauth_integrations.py`, `oauth_providers.py` |
| Notifications | `aria_morning_brief.py`, `aria_eod_wrap.py`, `aria_approval_digest.py` |
| Billing | `billing.py`, `billing_plans.py`, `billing_upgrade.py`, `invoicing.py` |
| Admin | `admin_v3.py`, `admin_deployments.py`, `applications.py` |
| Compliance | `compliance.py`, `classification.py` |
| Voice / AI Training | `aria_training.py`, `voice_seeds.py` |

**Core architectural rules:**

1. **V10 guard** — All LLM calls must route through `services/claude_service.py`. No direct Anthropic imports elsewhere. Run `scripts/check_v10.sh` before every commit.

2. **Multi-tenancy** — Every DB query must filter by `tenant_id`, resolved via the `get_current_user()` FastAPI dependency. Cross-tenant access returns 404, never leaks data.

3. **Dual collections** — Legacy ARIA leads live in `leads`; Pietential/Lemlist leads live in `pt_leads`. Aggregation helpers in `lead_query.py` (`iter_tenant_leads`, `count_tenant_leads`) union both per tenant.

4. **Encrypted secrets** — All third-party API keys stored via Fernet encryption in the `integration_configs` MongoDB collection. Never store keys in plaintext or env-exposed variables at the route level.

5. **Unified outreach pipeline** — All message dispatch (email/WhatsApp/LinkedIn) goes through `services/outreach_dispatch.py`. Never call Resend or 360dialog directly from a route.

---

## Background Jobs (always running in production)

| Job | Cadence | Purpose |
|---|---|---|
| Touchpoint engine | Every 60s | Fires next journey step for enrolled leads |
| Lemlist poll loop | Every 5 min | Syncs campaign activity into `pt_leads` + `outbound_log` |
| Saleshandy poll loop | Every 5 min | Same for Saleshandy (skipped for Pietential) |
| Morning brief loop | Daily 8 AM (workspace tz) | Email KPI summary to founder |
| EOD wrap loop | Daily 8 PM | Evening digest email |
| Pietential intel scan | Daily | Enriches new/hot B2B leads via crawl + Claude synthesis |

---

## Integrations

UI: `frontend/src/workspace/pages/Integrations.js` — bring-your-own-key model with live validation.  
Backend: `backend/routes/integrations_hub.py`, `integrations_routes.py`, `oauth_integrations.py`

| Provider | Purpose | Auth model |
|---|---|---|
| Anthropic Claude (Sonnet / Haiku) | LLM — scoring, drafting, synthesis | Emergent universal key |
| RapidAPI LinkedIn | Prospect profile scraping | Per-tenant key |
| Serper | Web / news / Instagram / Facebook search | Per-tenant key |
| Lemlist | Outreach campaigns + webhook inbound | Per-tenant key |
| Saleshandy | Email sequences (legacy) | Per-tenant key |
| Resend | Email dispatch + system emails | Per-tenant key |
| 360dialog | WhatsApp outbound + inbound webhook | Per-tenant key |
| Google Calendar | Event lookup via ARIA agent | OAuth per-user |
| Stripe | Billing + invoice webhooks | Global account |
| Slack | Founder alerts (Pietential only) | `SLACK_WEBHOOK_URL` env var |

---

## Database Collections (MongoDB, 80+)

| Group | Collections |
|---|---|
| Core | `users`, `tenants`, `tenant_memberships`, `tenant_users` |
| Leads | `leads`, `pt_leads`, `pt_lead_scores`, `activities` |
| Intelligence | `intel_profiles`, `pt_insights`, `scan_progress` |
| Messaging | `aria_conversations`, `outbound_log`, `inbound_messages`, `voice_seeds` |
| Automation | `touchpoints`, `journey_generate_jobs`, `automation_rules`, `touchpoint_logs` |
| Integrations | `integration_configs`, `api_usage_log` |
| Billing | `invoices`, `billing_profiles`, `billing_plans` |
| Admin | `applications`, `workspace_invites`, `invitations` |
| Audit | `audit_log`, `classification_logs` |

---

## Deployment (hands-off — do not edit)

- **Platform:** Emergent (Kubernetes)
- **Frontend:** React build → port 3000
- **Backend:** FastAPI + uvicorn → port 8001 (supervisord-managed)
- **Database:** MongoDB (connection string in Emergent env)
- Production API keys are **not** synced from preview. Re-paste via `/app/integrations` UI after each deploy.
- Do not modify: Docker files, supervisord config, `.emergent/`, env variable definitions, CORS origin lists, or Fernet encryption key references.
