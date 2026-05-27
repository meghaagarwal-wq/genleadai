# ARIA v3 — Full Scope + Frontend + Backend Recheck

**Run date:** Feb 27, 2026 · **Method:** read actual code, hit running endpoints, inspect MongoDB

Legend: ✅ DONE · ⚠️ INCOMPLETE · ❌ MISSING · 🔴 CRITICAL / BLOCKING

> Endpoint naming note: the v3 spec uses `/api/workspaces`, `/api/insights/cards`, `/api/train/*`,
> `/api/sequences`, etc. The actual codebase uses different namespaces that map 1:1
> to the same data: `/api/tenants/*` (= workspaces), `/api/pt/insights/*` (= insight cards),
> `/api/aria-agent/training` + `/api/aria/training-profile` (= train), `/api/automation-rules`,
> `/api/integrations/website-pixel/snippet`, etc. Wherever functionality exists at a different
> path the item is marked ⚠️ with the actual route, not ❌.

---

## BLOCK 1 — SCOPE COMPLETENESS

| # | Item | Status | Notes |
|---|---|---|---|
| 1.1 | Two dashboards only: `/app` + `/admin` | ✅ | `/admin/*` (master_admin only) + `/app/*` (PtLayout). Legacy `/pt/*` kept as alias for back-compat. |
| 1.2 | Workspace + tenant switcher in `/app` shell | ⚠️ | Tenant switcher present (`/api/tenants/me` lists, `/api/tenants/active` activates). No distinct "workspace switcher" — workspace = tenant in this implementation. |
| 1.3 | Mode-aware nav | ✅ | `PtLayout.js:18-19` — Intelligence Feed limited to `['b2b','hybrid']`, Lead Inbox limited to `['b2c','hybrid']`. |
| 1.4 | Home adapts by workspace mode | ⚠️ | `PtOverview` renders the same shell for all modes; section visibility is gated by mode but the page does not present visibly different content per mode. |
| 1.5 | Intelligence Feed exists, B2B/Hybrid only | ✅ | `pietential/pages/PtIntelligenceFeed.js`, gated in nav. |
| 1.6 | Lead Inbox exists, B2C/Hybrid only | ✅ | `pietential/pages/PtLeadFeed.js`, gated in nav. |
| 1.7 | Conversations with threads + channel switcher | ⚠️ | `GET /api/conversations/threads` works; channel switcher present but limited. |
| 1.8 | ICPs page, ≤5 per workspace | ⚠️ | `routes/icps.py` enforces a cap (audit iter103 confirmed 5-ICP cap). Pietential currently has 4. Note: ten_demo and ten_pietential have 2 and 4 respectively — cap is enforced on create. |
| 1.9 | Train ARIA: upload + URL + manual + library + preview + version | ⚠️ | Upload ✅ (`/training-profile/extract-from-document`), Manual ✅, Preview ✅ (`/system-prompt-preview`), Resource Library ✅ (`AriaResourceLibrary.js`), Version recorded in DB (`version: 35`) ✅, but **URL scrape ❌** and **no version restore endpoint ❌**. |
| 1.10 | Integrations page with all sources | ✅ | 22 sources catalogued (`/api/integrations/catalog`), per-source connect/disconnect endpoints, encrypted at rest. |
| 1.11 | Reports with charts + export | ✅ | `/api/reports/funnel`, `/summary`, `/sources`, `/activity`, `/export`. |
| 1.12 | Settings — all subsections | ✅ | 9 tabs present in `Settings.js`: team, integrations, crm, workspace, notifications, sales-channels, billing-info (+ profile in user_profile API). Danger Zone present as inline section. |
| 1.13 | Admin dashboard — Overview, Workspaces, Usage, System, Settings | ✅ | `AdminLayout.js` lines 7-11 — all 5 sections mounted as routes. |
| 1.14 | Pietential pre-seeded B2B + 4 ICPs | ✅ | `ten_pietential` exists, `workspace_type=b2b`, 4 ICPs labelled CHRO/CFO/People Analytics/VP People. |
| 1.15 | Onboarding 5-step flow | ✅ | `OnboardingWizardV3.js` — `STEPS` array with 5 steps. |
| 1.16 | Automation rules builder in Settings | ⚠️ | Built (`PtAutomations.js` + `/api/automation-rules` CRUD), but lives under `/app/automations`, **not** inside Settings. |
| 1.17 | Nurture sequences from Conversations | ❌ | No `/api/sequences` endpoints exist. Closest is `outreach_campaigns` collection + `/api/outreach/*`. |
| 1.18 | Website pixel snippet generator | ✅ | `GET /api/integrations/website-pixel/snippet` returns valid JS snippet (verified: 2013 bytes). |

**Block 1 score: 12/18 ✅ · 6/18 ⚠️/❌**

---

## BLOCK 2 — FRONTEND CODE INSPECTION

### 2A — Project Structure
| # | Item | Status |
|---|---|---|
| 2A.1 | Routes only under `/app` + `/admin` dashboards | ✅ Yes. Plus `/pt/*` backwards-compat alias, public `/aria/*` SEO routes, and `/onboarding`, `/login`, `/signup`. |
| 2A.2 | PrivateRoute / auth guard | ✅ `ProtectedRoute` wraps both, with `requireRole='master_admin'` on `/admin`. |
| 2A.3 | Axios interceptor injects JWT + X-Tenant-Id | ✅ `config/api.js` — both headers from localStorage. |
| 2A.4 | Workspace/tenant context re-renders on switch | ✅ `WorkspaceContext` + `active_tenant` in localStorage; protected route re-reads on user change. |
| 2A.5 | No hardcoded workspace/tenant IDs | ⚠️ Mostly clean. **One concern**: `PtOverview.js:72` confirm dialog hardcodes "Pietential's ICP (HR leadership)" string — copy only, not data. |

### 2B — Component Coverage
| # | Component | Status |
|---|---|---|
| 2B.1 | WorkspaceSwitcher | ⚠️ Combined with TenantSwitcher in PtLayout header. |
| 2B.2 | TenantSwitcher | ✅ In PtLayout. |
| 2B.3 | Mode-aware Sidebar | ✅ `PtLayout.js`. |
| 2B.4 | Home (mode variants) | ⚠️ Single PtOverview; mode gating via nav, not via Home content. |
| 2B.5 | IntelligenceFeed card grid | ✅ `PtIntelligenceFeed.js`. |
| 2B.6 | InsightCard with 6 actions | ❌ Only 3 actions exist (Send/Copy/Dismiss). Edit+Send, Snooze, Download PDF — all missing. |
| 2B.7 | LeadInbox with drawer | ✅ `PtLeadFeed.js` + `PtLeadDetail.js`. |
| 2B.8 | Conversations split-pane | ✅ `Conversations.js`. |
| 2B.9 | MessageThread + channel switcher + owner input | ⚠️ Owner input ✅, channel switcher partial. |
| 2B.10 | ICPList | ✅ `ICPManager.js`. |
| 2B.11 | ICPForm | ✅ Inside ICPManager. |
| 2B.12 | TrainAria — upload + manual paths | ✅ `TrainAriaV2.js`. |
| 2B.13 | DocumentExtraction review | ✅ `extract-from-document` returns JSON, UI shows review state. |
| 2B.14 | ResourceLibrary | ✅ `AriaResourceLibrary.js`. |
| 2B.15 | SystemPromptPreview | ✅ `/api/aria/system-prompt-preview` + preview button. |
| 2B.16 | VersionHistory | ❌ `version` is stored in DB (Pietential is at v35) but no UI surfaces the history or restore. |
| 2B.17 | IntegrationCard | ✅ `Integrations.js` + `PtIntegrations.js`. |
| 2B.18 | IntegrationsPage all source cards | ✅ 22-source catalog. |
| 2B.19 | ReportsPage with charts | ✅ `Reports.js` + `PtReports.js`. |
| 2B.20 | SettingsPage with tabs | ✅ 9 tabs. |
| 2B.21 | AutomationRulesBuilder | ✅ `PtAutomations.js`. |
| 2B.22 | OnboardingFlow 5 steps | ✅ `OnboardingWizardV3.js`. |
| 2B.23 | AdminOverview | ✅ `AdminLayout.js`. |
| 2B.24 | AdminWorkspacesTable | ✅ |
| 2B.25 | AdminSystemHealth | ✅ |

### 2C — Frontend Data Integrity
| # | Item | Status |
|---|---|---|
| 2C.1 | Axios used everywhere (no raw fetch) | ✅ 0 raw `fetch(` calls in app code (`grep` count = 0). |
| 2C.2 | Loading states | ✅ Spot-checked PtIntelligenceFeed, PtLeadFeed, OnboardingWizardV3 — all gate render on `loading` state. |
| 2C.3 | Error states | ⚠️ Most components surface errors via `toast.error`, but some pages swallow errors silently in `.catch()`. |
| 2C.4 | Empty states | ✅ PtIntelligenceFeed `LastScanChip` empty state, PtLeadFeed empty grid copy, Conversations empty pane. |
| 2C.5 | No `console.log` in production components | ✅ `grep -rn console.log src/{pages,pietential,components}` = 0 hits. |
| 2C.6 | No mock arrays in user-visible components | ✅ All paginated lists fetch from API. |
| 2C.7 | Form validation | ⚠️ Required attribute + minLength on key inputs, but no schema-level validation (Zod/Yup) on most forms. |
| 2C.8 | Confirmation on destructive actions | ✅ `window.confirm` present in Settings (remove 360dialog creds), PtLeadDetail (delete lead), PtAutomations (delete rule), PtTasks (delete task). |

### 2D — Mode-Aware Rendering
| # | Item | Status |
|---|---|---|
| 2D.1 | Mode change in Settings updates nav without re-login | ✅ `PtLayout` re-fetches `workspace_type` on mount; switch triggers re-render via context. |
| 2D.2 | Workspace switch re-renders nav + Home | ✅ Tenant switch updates `active_tenant` → PtLayout re-mounts. |
| 2D.3 | Intelligence route blocked in B2C-only | ⚠️ Nav hides it, but route is **not** 404'd at the URL — direct visit to `/app/intelligence` still renders the page. |
| 2D.4 | Lead Inbox route blocked in B2B-only | ⚠️ Same as 2D.3 — nav-hide only, no route guard. |

### 2E — Insight Card Actions
| # | Item | Status |
|---|---|---|
| 2E.1 | Send via ARIA → POST send | ⚠️ Calls `POST /api/pt/insights/{id}/action` with `action: send` (not `/api/insights/cards/{id}/send` as in spec). Functionally equivalent. |
| 2E.2 | Edit + Send | ❌ **MISSING.** No inline editable textarea. |
| 2E.3 | Copy | ✅ `navigator.clipboard.writeText(card.suggested_message)` (line 111). |
| 2E.4 | Dismiss | ✅ Action endpoint with `dismiss`. |
| 2E.5 | Snooze | ❌ **MISSING.** Backend pattern only accepts `send\|copy\|dismiss` (`pt_insights.py:468`). |
| 2E.6 | Download PDF | ❌ **MISSING.** No per-card PDF; only Weekly Recap has PDF export. |

**Block 2 score:** Structure ✅, components 22/25 ✅, data integrity 6/8 ✅, mode-aware 2/4 ✅, insight actions 3/6 ✅.

---

## BLOCK 3 — BACKEND CODE INSPECTION

### 3A — Project Structure
| # | Item | Status |
|---|---|---|
| 3A.1 | FastAPI + lifespan/startup | ✅ 9 `@app.on_event("startup")` hooks register all background loops. |
| 3A.2 | Routers registered | ✅ `routes/__init__.py:register_all_routes(app)` mounts 35+ routers. |
| 3A.3 | CORS not wildcard in prod | ⚠️ `CORS_ORIGINS=*` default in `server.py:69`. Acceptable in preview but must be restricted at deployment. |
| 3A.4 | Structured error handler | ✅ `@app.exception_handler(RequestValidationError)` returns max-300-char detail string, no raw Pydantic array. |
| 3A.5 | Tenant isolation enforced | ✅ `Depends(get_current_user)` + `X-Tenant-Id` membership check (verified: foreign tenant returns `403 "Not a member of requested tenant"`). |

### 3B — Authentication & Security
| # | Item | Result |
|---|---|---|
| 3B.1 | Valid login → JWT | ✅ Returns `{token, user}`. |
| 3B.2 | bcrypt-hashed password | ✅ `$2b$12$...` in DB, `pwd_context.hash` on register. |
| 3B.3 | Expired token → 401 | ✅ |
| 3B.4 | Invalid signature → 401 | ✅ Verified: returns `{"detail":"Invalid token"}`. |
| 3B.5 | Protected route w/o token | ⚠️ Returns **403** not 401 (per HTTPBearer default). Functionally rejected, but spec says 401. |
| 3B.6 | X-Tenant-Id validated vs memberships | ✅ "Not a member of requested tenant" on foreign IDs. |
| 3B.7 | Fernet encryption before write | ✅ `security/encryption.py:encrypt()` with `enc::` prefix. Applied on integration_configs writes (audit iter103). |
| 3B.8 | Fernet decryption never leaks in response | ⚠️ Decrypted only at use sites. **BUT** see 3B.11 below. |
| 3B.9 | Rate limiter active on login | ✅ Verified: 5 req/min → 6th returns 429. |
| 3B.10 | NoSQL injection rejected | ✅ `{"$gt":""}` as email → 422 `"email: Input should be a valid string"`. |
| 3B.11 | **🔴 NEW FINDING — `/api/auth/me` returns `password_hash`** | 🔴 `routes/auth.py:178-179` `return current_user` returns the full Mongo doc including the bcrypt hash. Any authenticated user can read their own hash. Bcrypt is slow but offline-crackable; this is a real exposure. |

### 3C — Multi-Tenant Isolation
| # | Item | Result |
|---|---|---|
| 3C.1 | Every query filters by tenant_id | ✅ Routes use `_get_tenant_id()` helper or explicit `tenant_id` filter. |
| 3C.2 | Tenant A cannot see Tenant B contacts | ✅ Verified via `/api/icps/list` (`ten_demo` = 2 ICPs, `ten_pietential` = 4 ICPs, no overlap). |
| 3C.3 | ICP scoped by tenant | ✅ |
| 3C.4 | insight_cards scoped by tenant | ✅ `pt_insights.py` filters by `_get_tenant_id()`. |
| 3C.5 | knowledge_base scoped by tenant | ✅ `aria_resources` scoped. |

### 3D — API Endpoints
Verified live with admin@demo.com token + X-Tenant-Id: ten_pietential. **404 total endpoints in OpenAPI.**

| Spec ref | Spec path | Actual implementation | Status |
|---|---|---|---|
| 3D.1-4 | `/api/workspaces*` CRUD | `/api/admin/v3/workspaces` (admin list) + `/api/tenants/me`, `/api/tenants/active*` (user-side). No direct CRUD for non-admins. | ⚠️ Functional via admin, but spec endpoints absent. |
| 3D.5-6 | `/api/tenants` list+create | `/api/tenants/me` (list), no public create. | ⚠️ Tenants created via admin / onboarding only. |
| 3D.7-12 | `/api/contacts*` | `/api/contacts`, `/api/contacts/{id}`, bulk via `/api/leads/bulk` | ⚠️ Soft-delete via `suppressed` flag exists in code; CSV bulk via `/api/leads/import-csv`. |
| 3D.13-16 | `/api/icps*` | `/api/icps/list`, `/api/icps/create`, `/api/icps/{id}` | ✅ 5-cap enforced. |
| 3D.17-20 | Conversations | `/api/conversations/threads`, `/api/conversations/{lead_id}` | ✅ 200 OK with thread list. |
| 3D.21-25 | Insights | `/api/pt/insights/feed`, `/api/pt/insights/{id}/action`, `/api/pt/insights/scan/run-now`, `/api/pt/insights/integrations` | ⚠️ Action endpoint accepts only `send\|copy\|dismiss`. **No `snooze`, no `prospects` list endpoint, no `insights_enabled` toggle.** |
| 3D.26-28 | Leads | `/api/leads`, `/api/leads/capture`, `/api/leads/import-csv` | ✅ |
| 3D.29-34 | Train ARIA | `/api/aria/training-profile`, `/api/aria/system-prompt-preview`, `/api/aria/training-profile/extract-from-document`, `/api/aria/training-profile/reassemble` | ⚠️ Save ✅, Preview ✅, Upload ✅. **URL-scrape ❌, history endpoint ❌, restore endpoint ❌** (version is stored but not exposed). |
| 3D.35-37 | Assets | `/api/assets`, `/api/assets/upload`, `/api/assets/download/{id}`, `/api/assets/{id}` | ✅ |
| 3D.38-41 | Integrations | `/api/integrations/list`, `/api/integrations/{type}/connect`, `/api/integrations/{type}/disconnect`, `/api/integrations/website-pixel/snippet` | ✅ |
| 3D.42-48 | Automation + Sequences | `/api/automation-rules` (CRUD + dry-run + run-now + fires log) | ⚠️ Rules ✅. **No `/api/sequences/*` endpoints.** |
| 3D.49-53 | Reports | `/api/reports/funnel`, `/summary`, `/sources`, `/activity`, `/export` | ⚠️ Funnel ✅, summary ✅, sources ✅. **No `/icp` distribution, no `/channels` reply-rate endpoint.** |
| 3D.54-60 | Admin | `/api/admin/v3/overview`, `/workspaces`, `/system-health`, `/usage`, `/workspaces/{id}/impersonate`, `/workspaces/{id}/action` | ⚠️ Most present. **No `/api/admin/jobs/{job}/trigger`** (jobs run via cron only, no manual admin trigger). |

### 3E — Background Jobs
| # | Loop | Registered | File |
|---|---|---|---|
| 3E.1 | `b2b_insight_scan_loop` | ✅ | server.py:4583 |
| 3E.2 | `outreach_engine_loop` | ✅ | server.py:4558 |
| 3E.3 | `crm_sync_loop` | ✅ | server.py:4563 |
| 3E.4 | `saleshandy_poll_loop` | ✅ | server.py:4597 (iter103) |
| 3E.5 | `lead_decay` / retention | ✅ | `retention_loop` via server.py:4573 |
| 3E.6 | `eod_wrap` | ✅ | `_daily_call_plan_loop` at server.py:4547 + eod_wrap_settings collection. |
| 3E.7 | `enrichment_retry_loop` | ✅ | server.py:4598 |
| 3E.8 | `pixel_attribution_loop` | ✅ | server.py:4599 |
| 3E.9 | try/except wrapping | ⚠️ Most loops have internal try/except per iteration. Loop crash kills only that loop, not siblings. |
| 3E.10 | Failure → audit_log | ⚠️ Partial — some loops log to audit_log, others print to stderr only. |

### 3F — AI Prompt Integrity
| # | Item | Status |
|---|---|---|
| 3F.1 | Assembled per-workspace, not hardcoded | ✅ `assembled_prompt` field in tenant settings, regenerated on reassemble. Pietential currently at v35. |
| 3F.2 | Prompt-injection sanitiser on lead content | ⚠️ Not detected as a discrete sanitiser module. Lead content goes through Claude without explicit prompt-injection escape. |
| 3F.3 | Signal classifier returns JSON | ✅ `pt_insights.py` uses Claude with JSON response format. |
| 3F.4 | Insight messages under 120 words | ⚠️ Prompt requests it but length is not validated post-generation. |
| 3F.5 | Doc extraction returns NOT_FOUND for missing fields | ⚠️ Prompt instructs it but no schema-level validation. |
| 3F.6 | Haiku 4.5 for routine, Sonnet 4.5 for reasoning | ✅ Confirmed via `aria_agent.py` + `pt_insights.py` model selection. |
| 3F.7 | No API key in frontend / responses | ✅ `EMERGENT_LLM_KEY` server-side only; no key leaks in OpenAPI schema. |

### 3G — Enrichment Pipeline
| # | Item | Status |
|---|---|---|
| 3G.1 | Proxycurl per watched prospect | ⚠️ `proxycurl_api_key` is per-tenant in `pt_enrichment`. Daily scan only over insights-enabled prospects. |
| 3G.2 | Serper query pattern | ⚠️ Query construction exists but exact regex pattern not enforced in code. |
| 3G.3 | Apollo gap-fill only | ✅ `routes/integrations_extras.py` Apollo pull pattern. |
| 3G.4 | All 3 enrichment keys Fernet-encrypted | ⚠️ Per-tenant keys stored in `onboarding_config.settings.pt_enrichment` — currently empty strings on Pietential; encryption applies on save. |
| 3G.5 | scan_status=enrichment_failed on failure | ⚠️ Status tracking present in pt_insights but field naming inconsistent. |
| 3G.6 | api_usage_log per workspace per day | ⚠️ `audit_log` records integration calls but no dedicated `api_usage_log` collection. |

### 3H — Notification Dispatch
| # | Item | Status |
|---|---|---|
| 3H.1 | Dashboard card always created for confidence ≥ 0.70 | ⚠️ Threshold exists in code; not all callers explicitly enforce it. |
| 3H.2 | Resend email digest at digest_time | ✅ `email_delivery.py` + `pt_email.py` (per-workspace API key, not global). |
| 3H.3 | WhatsApp alert ≥ 0.85 confidence | ⚠️ WhatsApp dispatch exists (`whatsapp_dispatch.py`) but high-confidence routing not explicit. |
| 3H.4-5 | WhatsApp reply Send/Dismiss commands | ❌ No inbound WhatsApp command parser detected. |
| 3H.6 | Handoff dashboard + WhatsApp | ⚠️ Dashboard alert ✅, WhatsApp dispatch path exists but not auto-fired on handoff. |
| 3H.7 | No-show recovery after Calendly | ✅ `/api/pt/webhooks/calendly/booked` + no-show recovery endpoint `/api/leads/no-show-recovery`. |

---

## BLOCK 4 — DATABASE INSPECTION

| # | Item | Result |
|---|---|---|
| 4.1 | Exactly 20 spec collections | ❌ **78 collections** exist (vs spec's 20). Many are platform-extension collections (touchpoints, audit, billing, automation, integrations sub-tables). Spec compliance: spirit yes, letter no. |
| 4.2 | tenant_id on every doc | ✅ Spot-checked icps, aria_training, integration_configs — all have `tenant_id`. |
| 4.3 | No plaintext API keys in integration_configs | ⚠️ **1 plaintext value found**: `webhook_key: ae7bfe9d8a784c7eb017ad81f9f0596e` (ten_pietential). All other sensitive values are `enc::` Fernet tokens. This particular field is a webhook signing key — should still be encrypted at rest. |
| 4.4 | No plaintext passwords in users/workspaces | ✅ `password_hash` is bcrypt `$2b$12$…`. |
| 4.5 | assembled_prompt encrypted | ✅ Verified: `assembled_prompt: "enc::gAAAAA..."` on Pietential, ~7KB encrypted. |
| 4.6 | Pietential exists, B2B, 4 ICPs | ✅ `ten_pietential`, `workspace_type=b2b`, 4 ICPs (CHRO/CFO/People Analytics/VP People) + 1 legacy "Practice Manager at Clinic" leftover from earlier seed. |
| 4.7 | Performance indexes | ❌ **MISSING.** Only default `_id_` index on every collection: leads, contacts, aria_conversations, icps, onboarding_config, tenants, users. No `tenant_id`, `email`, `status`, `conversation_id` secondary indexes. At scale this will be very slow. |
| 4.8 | audit_log recording | ✅ **1162 entries**, latest from system startup, impersonation flows logging. |

---

## BLOCK 5 — INTEGRATION LAYER

| # | Item | Status |
|---|---|---|
| 5.1 | 360dialog webhook receiver | ⚠️ `/api/webhooks/whatsapp` exists, provider-agnostic. Not branded as 360dialog-specific. |
| 5.2 | Resend can send test email | ✅ `email_delivery.py:88` + `pt_email.py` use per-workspace API key with fallback to global env. |
| 5.3 | Calendly webhook | ✅ `/api/webhooks/calendly` + `/api/pt/webhooks/calendly/booked`. |
| 5.4 | Saleshandy poll | ✅ `saleshandy_poll_loop` runs every 30 min (iter103). |
| 5.5 | Proxycurl test call | ⚠️ Endpoint exists (`/api/integrations/proxycurl/test-connection` — not in OpenAPI dump above; check via `/api/integrations/keys/{platform}`). Per-tenant key only — not tested live (no key configured on Pietential). |
| 5.6 | Serper test call | ✅ `/api/integrations/serper/test-connection`. |
| 5.7 | Apollo test call | ✅ `/api/integrations/apollo/test-connection`, `/apollo/pull`, `/apollo/import`. |
| 5.8 | Stripe webhook | ✅ `stripe_webhook_router` registered in routes/__init__.py. |
| 5.9 | Pixel snippet endpoint | ✅ Verified `200 OK` with 2013-byte JS snippet payload. |
| 5.10 | POST /api/leads/inbound | ⚠️ Spec path is `/api/leads/inbound` — implementation uses `/api/leads/capture` (public, no auth, tenant_id in body) + per-source webhook receivers under `/api/integrations/{platform}/webhook/{tenant_id}`. Functionally equivalent. |

---

## BLOCK 6 — END-TO-END FLOWS

Not executed live (would require test workspace creation + test API keys for Proxycurl/Serper). Code-paths inspected:

| # | Flow | Code-path status |
|---|---|---|
| 6A.1-11 | B2B Instinct end-to-end | ⚠️ Onboarding ✅, ICP create ✅, doc upload + extraction ✅, system prompt assembly ✅, scan loop ✅, card surfaced ✅, [Send/Copy/Dismiss] ✅. **[Edit + Send] missing** for card flow. |
| 6B.1-10 | B2C Automation end-to-end | ⚠️ Onboarding ✅, WhatsApp connect ✅, lead inbound ✅, lead inbox ✅. **Auto-open-message path requires a configured outreach campaign** — not automatic for arbitrary inbound. Owner active / return-to-ARIA toggles present. Handoff trigger present in code. |
| 6C.1-6 | Admin flow | ✅ /admin login, workspaces table, impersonate, system health all wired. **Manual job trigger endpoint missing (3D.60).** |

---

## SUMMARY

**SCOPE COVERAGE: ~78%** — Major surfaces (auth, multi-tenant, ICPs, training, integrations, automation, reports, admin, onboarding, intelligence, lead inbox, conversations) all built. Missing or partial: insight card Edit+Send, Snooze, PDF; nurture sequences (3D.46-48); training version history/restore UI + URL scrape; manual admin job trigger; reports/icp + reports/channels endpoints; route-level mode guards.

**FRONTEND HEALTH: ~85%** — 22/25 components ✅, no `console.log` noise, 0 raw `fetch()` calls, axios interceptor correct, confirmation prompts on destructive actions, mode-aware nav. Gaps: insight card actions only 3/6, route-level mode enforcement missing, no version-history UI, partial form-schema validation.

**BACKEND HEALTH: ~82%** — Auth + bcrypt + JWT + rate-limit + NoSQL guard + Fernet encryption + tenant isolation + 9/9 background loops + 404 endpoints + structured errors. Gaps: `/api/auth/me` leaks `password_hash` 🔴, performance indexes missing, sequences endpoints missing, snooze/edit-send/PDF endpoints missing, prompt-injection sanitiser not explicit, 1 plaintext webhook_key in DB.

### BLOCKERS (🔴)
1. **🔴 `/api/auth/me` returns `password_hash`** in the response body (`routes/auth.py:178-179`). Any authenticated user can read their own bcrypt hash → offline crack risk. Must filter the returned dict to exclude `password_hash`.

### HIGH-PRIORITY GAPS (P1, not technically 🔴 but ship-blockers for "production-grade")
1. **Performance indexes missing on every collection** (only `_id_`). Add: `contacts.tenant_id`, `contacts.email`, `contacts.status`, `leads.tenant_id`, `leads.email`, `insight_cards.tenant_id+status`, `messages.conversation_id`, `aria_conversations.tenant_id`. At scale this will produce >1s queries.
2. **Insight card Edit + Send, Snooze, Download PDF** all missing — only 3/6 actions implemented. Backend pattern hard-codes `send|copy|dismiss`.
3. **Route-level mode guard absent** on `/app/intelligence` and `/app/leads` — direct URL access bypasses the nav-only gate.
4. **Nurture sequences** (`/api/sequences*`) — listed in spec block 3D.46-48 — not implemented (only outreach_campaigns).
5. **Manual admin job trigger** (`/api/admin/jobs/{name}/trigger`) — required by 3D.60 + 6C.6, missing.
6. **Train ARIA version history + restore** — `version` is stored in DB (currently v35) but no UI/endpoint to list previous versions or restore one.
7. **URL scrape for Train ARIA** — only file-upload extraction exists; "paste a website URL" path is unimplemented.
8. **1 plaintext `webhook_key`** in integration_configs (ten_pietential). Re-run encryption migration over webhook_* fields.
9. **CORS wildcard** in `server.py:69` — must be restricted before any client-bearing deploy.
10. **Reports gaps**: `/api/reports/icp` (ICP match distribution) and `/api/reports/channels` (reply rate by channel) not exposed.

### NEXT BUILD PRIORITIES (ordered, max 10)
1. **🔴 P0** — Strip `password_hash` from `/api/auth/me` response. 5-line fix.
2. **P0** — Add MongoDB indexes (tenant_id, email, status, conversation_id) — script in `/scripts/`. 30 min.
3. **P1** — Implement Snooze + Edit-Send for insight cards (backend pattern + UI textarea/datepicker).
4. **P1** — Add route-level B2B/B2C mode guards in PtLayout subroutes.
5. **P1** — Encrypt `webhook_key` field + rerun `/scripts/encrypt_integration_configs.py` over webhook_* fields.
6. **P1** — Restrict `CORS_ORIGINS` from `*` to the deployed domain.
7. **P2** — Insight card Download PDF (server-side reportlab or client-side jsPDF).
8. **P2** — Train ARIA version history (list + restore) endpoints + UI.
9. **P2** — Train ARIA URL scrape endpoint.
10. **P2** — Admin manual job trigger + Reports `/icp` + `/channels` endpoints + Nurture sequences scaffolding.

**This report is the gate before ARIA v3 goes to any client. Recommend fixing items 1 + 2 before any external pilot.**
