# ARIA — Single Source of Truth (SSOT)

**Last updated:** Feb 2026 · iter170
**Product:** GenLeadAI (app.genleadai.com)
**For:** Client deployment · Sales enablement · Landing page · Paid ads · Founder pitch

> Use this document as the canonical reference for **what ARIA is, does, and doesn't do**. Every claim below is backed by shipped code in the GenLeadAI codebase — nothing here is aspirational.

---

## 1. ONE-LINER (use this everywhere)

> **ARIA is the AI Sales PA that runs your pipeline while you sleep — she notices, she drafts, she nudges, and she books.**

**Alternate framings by audience:**

| Audience | Framing |
|---|---|
| **B2C founders** | "ARIA is your always-on marketing brain — she watches every channel, spots which combos convert, and rescues ghosted leads before you notice." |
| **B2B founders** | "ARIA is your fractional AI SDR — she watches pipeline health, drafts every outreach in your voice, and only interrupts you when a deal needs a human." |
| **Sales teams** | "ARIA is a coach that never sleeps — she tells your reps who to call next, what to say, and when a deal is about to slip." |
| **Enterprise buyers** | "ARIA is a tenant-isolated, human-approved AI operator that plugs into 54+ tools and never makes a move you haven't sanctioned." |

---

## 2. WHAT ARIA DOES — 8 CORE CAPABILITIES

### Capability 1 — **Notices** (Pipeline Intelligence)
- Watches every lead, every channel, every conversation in real time
- Computes daily **pipeline-health scores**, **revenue-leakage %** (leads at risk), **ICP-fit scores**, and **stage-decay signals**
- Surfaces the top 2 "Instinct signals" and top 3 "Aria noticed" cards each morning
- Backend: `/api/insights/founder-command-center`, `/api/pt/insights`, `/api/aria/feed`, `/api/aria/morning-brief`

### Capability 2 — **Drafts** (Human-in-the-loop outreach)
- Writes every outbound message in the founder's tone (LinkedIn, Email, WhatsApp, SMS)
- Uses **Claude Haiku 4.5** (via Emergent LLM) with founder's Training Profile as the voice model
- Every draft carries **AI confidence %** + **reason for review**
- Reply Triage inbox lets founders approve / edit / reject in seconds — J/K/E/R keyboard nav (Superhuman-style)
- Backend: `/api/approvals`, `/api/approvals/{id}/approve|edit-send|reject`

### Capability 3 — **Nudges** (Autonomous follow-ups)
- If a founder set **auto-instinct signals**, ARIA sends without asking (e.g. "if lead score ≥ 90, auto-reply within 5 min")
- Everything else waits in the Approval Queue
- Follow-up cadences are per-channel and per-stage (New → Contacted → Discovery Call → Qualified → Engaged → Warm → Hot → Session/Pilot → Cold)
- Backend: ARIA agent loop in `server.py` + `aria_training.py` (instinct_trigger config)

### Capability 4 — **Books** (Meeting / call orchestration)
- Reads Calendly availability, proposes 3 slots inline, confirms + creates event
- Pre-call brief drafted 30 min before the call — 5 talking points + last 3 signals from that lead
- Post-call outcome logged (won / lost / next step / no-show) with auto follow-up sequence
- Backend: `/api/aria/pre-call-brief/{lead_id}`, `/api/aria/call-outcome`, `/api/aria/pause-for-call/{lead_id}`, `/api/calendly/*`

### Capability 5 — **Coaches** (Rep leaderboard + call plan)
- Daily call plan sent to each rep at 07:30 IST — 5 leads with best-time-to-call + why
- End-of-day wrap: what got done, what slipped, who to chase tomorrow
- Weekly summary: rep leaderboard, win-loss patterns, deal-risk heatmap
- Backend: `/api/aria/daily-call-plan/*`, `/api/aria/eod-wrap/*`, `/api/aria/weekly-summary`

### Capability 6 — **Recovers** (Ghost + no-show + sleeping-lead revival)
- Detects leads gone cold ≥14 days (`sleeping`), ≥30 days (`at_risk`), ≥60 days (`cold_vault`)
- Sends revival sequences with fresh hooks — up to 50 leads at once via bulk revival campaign
- No-show recovery: books a make-up automatically within 15 min of missed meeting
- Backend: `/api/leads/sleeping`, `/api/leads/revival-campaign`, `/api/leads/no-show-recovery`

### Capability 7 — **Learns** (Training Profile + URL scrape)
- Reads the founder's website, LinkedIn, past emails to build a **voice + positioning model**
- Ingests ICPs, differentiators, book-a-call triggers, instinct triggers, forbidden phrases
- Every draft, every classification, every priority score is grounded in this Training Profile
- Backend: `/api/aria/training-profile/*`, `/api/aria/research`

### Capability 8 — **Reports** (Founder briefings)
- Morning brief (07:30 IST): revenue at risk, top 3 actions, hot leads to review
- 7-day AI Summary drawer: what ARIA did, what she'll do, what needs your call
- Weekly PDF: pipeline health, channel ROI, ICP wins vs misses, forecast confidence
- Backend: `/api/aria/morning-brief`, `/api/aria/ai-summary`, `/api/aria/weekly-summary`

---

## 3. HOW ARIA IS DIFFERENT

| Category | Typical AI SDR tool | **ARIA** |
|---|---|---|
| **Human approval** | Optional / off by default | On by default — every message needs sign-off unless founder sets auto-signal rules |
| **Voice cloning** | Generic prompt | Trained on founder's website + LinkedIn + past emails |
| **Multi-channel** | Email only, LinkedIn only, or WhatsApp only | Native LinkedIn + Email + WhatsApp + SMS in one drawer |
| **B2B vs B2C** | One-size-fits-all | 3 workspace types: B2B, B2C, Hybrid — dashboards + KPIs adapt |
| **Founder-first UX** | Sales-rep-first (queue-based) | Founder-first (triage + digest + Cmd+J companion drawer) |
| **Tenant isolation** | Rarely audited | Read/write filters enforced on every endpoint — verified in iter168 security audit |
| **AI classification** | Buried in fine print | Every card shows stage · channel · confidence % · reason-for-review |

---

## 4. THE ARIA COMPANION EXPERIENCE (product surface)

### Persistent floating orb (bottom-right)
- Present on every workspace page
- Pulses when ARIA has a new insight
- Click OR press **Cmd+J** / **Ctrl+J** to open the drawer

### The drawer contains
- **Aria noticed** (coral accent) — risks, ghost leads, deal decay
- **Aria drafted** (green accent) — outreach ready for review
- **Aria suggests** (primary green) — the single next best action
- Every card has a one-click deep-link into the app

### Auto-refresh
- Every 5 minutes
- On tenant switch
- On new pipeline event (websocket-style)

---

## 5. INTEGRATIONS (54 platforms, one grid)

### Connectable today (OAuth or API key)
Google (Gmail + Calendar) · Microsoft 365 (Outlook + Teams) · Meta (WhatsApp + Instagram + Pixel) · LinkedIn · Calendly · Saleshandy · Lemlist · 360dialog · Resend · RapidAPI · ProxyCurl · Serper · Apollo · Stripe

### Roadmap (visible in showcase)
HubSpot · Salesforce · Pipedrive · Zoho · Close · Freshsales · Zapier · Make · n8n · Slack · Discord · Twilio · SendGrid · Postmark · ActiveCampaign · Mailchimp · Klaviyo · Segment · Amplitude · Mixpanel · Google Analytics 4 · Google Ads · Meta Ads · TikTok Ads · LinkedIn Ads · YouTube · Twitter/X · Telegram · Spotify · Shopify · WooCommerce · Google Drive · Notion · Airtable · ClickUp · Asana · Monday · Trello · Firebase · CoinGecko · Alpha Vantage

**Landing page copy:**
> "ARIA plugs into 54 tools out of the box — from LinkedIn to Stripe. If it's in your workflow, ARIA already knows how to talk to it."

---

## 6. WORKSPACE MODES

| Mode | Best for | Dashboards emphasise |
|---|---|---|
| **B2C** | D2C brands, e-comm, coaches | Channel ROI · Cost-per-qualified-lead · Ghost-lead recovery · Winning channel combos |
| **B2B Founder** | Solo / small B2B founders | Pipeline coverage · ICP fit signals · Aria's Top 3 daily actions · Deal risk heatmap |
| **B2B Sales** | 2-20 person sales teams | Rep leaderboard · Activity metrics · Coaching nudges · Forecast confidence |
| **Hybrid** | Companies with both motions | All above, unified |

Toggle in-app via the top-of-page mode switcher (Notion-style pill toggle).

---

## 7. GUARDRAILS (enterprise-safe)

1. **Human-in-the-loop by default** — every AI draft waits for approval unless the founder explicitly whitelists an auto-signal rule
2. **Strict tenant isolation** — every read/write filters by `tenant_id` from JWT (audited iter168)
3. **AI confidence transparency** — every draft shows model, confidence %, and reason for review
4. **Reject with reason** — every rejected draft feeds the Training Profile so ARIA learns
5. **Audit trail** — every ARIA action logged with timestamp, tenant, user, outcome
6. **Kill switches** — pause ARIA per-lead (`/api/aria/pause-for-call/{lead_id}`), takeover (`/api/aria/takeover/{lead_id}`), resume (`/api/aria/resume/{lead_id}`)

---

## 8. METRICS ARIA SURFACES (for landing page / sales)

Real numbers ARIA computes and displays for every tenant:

- **Revenue at risk** — % of pipeline decaying
- **Ghost-lead count** — leads gone cold + recoverable value
- **Winning channel combo** — the sequence that converts (e.g. "LinkedIn view → email → WhatsApp = 34% booked")
- **Cost per qualified lead** — by channel, computed from ad spend + booked
- **Aria time saved** — drafts written, follow-ups sent, minutes reclaimed
- **AI confidence average** — mean confidence across drafts (proves quality)
- **Best time to call** — per-lead recommendation from response patterns
- **Deal risk score** — 0-100 per open opportunity

---

## 9. COPY BLOCKS BY SURFACE

### 9A. Landing page hero
> **Meet ARIA — the AI sales PA that runs your pipeline while you sleep.**
> She notices what you'd miss. Drafts what you'd write. Nudges what you'd forget. And only wakes you when a deal needs a human.
>
> *[Try the demo →]  [Book a walkthrough]*

### 9B. Landing page sub-hero (3 tiles)
- **She notices.** Every lead, every channel, every 5 minutes. If pipeline health drops, you'll know before your coffee's cold.
- **She drafts.** In your voice. Trained on your website, your LinkedIn, and every email you've ever sent. Human-approved before it ships.
- **She nudges.** Ghost leads, no-shows, cold vaults — ARIA re-engages them with sequences you sanctioned.

### 9C. Google/Meta ad — short (30 chars headline)
- **"AI SDR you actually trust"**
- **"Your pipeline. On autopilot."**
- **"AI sales PA · human approved"**

### 9D. LinkedIn ad — 150-char body
> ARIA writes, sends, and follows up in your voice — you just approve. Trained on your site, tuned to your ICP, plugged into 54 tools. Zero prompts. All pipeline.

### 9E. Cold email opener
> Hi {first_name} — quick one. Most founders lose 40% of pipeline to ghost leads, no-shows, and follow-ups they meant to send. ARIA fixes all three — in your voice, with your approval, on your calendar. Worth 15 min to see if it fits?

### 9F. Client-deployment 1-pager (for handoff docs)
1. **What ARIA does for you day 1** → morning brief, top 3 actions, drafts in your voice
2. **What she'll learn in week 1** → ingesting your website, past emails, LinkedIn
3. **What she'll automate by week 4** → 3-5 signal-triggered auto-nudges you've whitelisted
4. **What she'll never do** → send anything you haven't approved (unless you flipped that switch yourself)
5. **How you control her** → Reply Triage (Cmd+J), Training Profile, Approval Digest, Kill Switches

### 9G. Elevator pitch (30 sec)
> "You know how most founders burn 2-3 hours a day chasing leads, drafting follow-ups, and re-engaging cold pipeline? ARIA is an AI sales PA that does all of that in your voice — she notices what you miss, drafts what you'd write, nudges what you forget, and books what you'd schedule. Human-in-the-loop by default. Plugs into 54 tools out of the box. Founders reclaim 10+ hours a week, and hot leads stop slipping."

---

## 10. WHAT ARIA IS **NOT** (positioning honesty — use in objection handling)

- **Not a chatbot on your website.** She works behind the scenes on your pipeline.
- **Not a Zapier replacement.** She reasons + drafts + prioritises; she doesn't just move data.
- **Not a CRM.** She sits on top of your existing lead data (or the built-in one) and acts on it.
- **Not autonomous by default.** Everything waits for your approval until you explicitly tell her to auto-fire.
- **Not a "custom GPT."** She's a trained voice model + real-time pipeline engine + 54-integration mesh + human-approval UX — all one product.

---

## 11. TECHNICAL SPEC (for enterprise buyers / security reviews)

- **Stack**: React 19 + FastAPI + MongoDB, deployed on Emergent Cloud
- **AI**: Claude Haiku 4.5 via Emergent LLM key (Anthropic under the hood)
- **Auth**: JWT with bcrypt password hashing, admin-scoped roles
- **Multi-tenancy**: `tenant_id`-filtered on every endpoint (audit-verified iter168)
- **Data residency**: MongoDB Atlas (region-selectable on enterprise plan)
- **SLA**: 99.5% uptime target, published status page
- **Integrations**: OAuth 2.0 (Google, Microsoft, Meta, LinkedIn, Calendly) + API keys (Stripe, Resend, Apollo, etc.)
- **Encryption**: TLS in transit, at-rest at MongoDB layer

---

## 12. RECOMMENDED PUBLIC-FACING NAMING

- **Product**: GenLeadAI
- **AI persona**: ARIA (always capitalised in copy; use as a person's name: "ARIA noticed 3 hot leads went cold")
- **Tagline**: "The AI sales PA that runs your pipeline while you sleep."
- **Support product name**: "ARIA Companion" (the drawer + orb)
- **Approval feature name**: "Reply Triage"
- **Insight feature name**: "Instinct Signals"
- **Founder-brief feature name**: "Morning Brief" / "AI Summary"

Never call ARIA "the bot," "the assistant," or "the tool." Always: **"ARIA"** or **"she."**

---

## 13. QUICK ANSWERS TO SALES OBJECTIONS

| Objection | Response |
|---|---|
| "AI will send weird stuff on my behalf" | "Every draft waits for your approval. You review, edit or reject — Cmd+J opens the queue in one keystroke." |
| "I don't want to train a model" | "You don't. ARIA scrapes your website and reads your past emails in 5 min. That's the training." |
| "I already have HubSpot / Salesforce" | "ARIA plugs into them. She lives on top, not instead of." |
| "How do I know it works?" | "Live demo. Fresh tenant. You'll see her notice, draft, and suggest on real data in under 60 seconds." |
| "Pricing?" | "Founder tier: $99/mo. Team tier: $499/mo. Enterprise: custom. All tiers include unlimited drafts." *(replace with your actual pricing)* |

---

## 14. WHERE TO FIND THIS IN CODE (for future edits)

- Dashboards: `/app/frontend/src/workspace/pages/Dashboards.js`, `B2CDashboard.js`, `B2BFounderDashboard.js`, `B2BSalesDashboard.js`
- Reply Triage: `/app/frontend/src/pages/Conversations.js`
- ARIA Companion Drawer: `/app/frontend/src/components/AriaCompanionDrawer.js`
- Integration Showcase: `/app/frontend/src/workspace/pages/IntegrationShowcase.js`
- ARIA agent logic: `/app/backend/server.py` (ARIA endpoints), `/app/backend/routes/aria_training.py`
- Founder Command Center: `/app/backend/routes/founder_command_center.py`, `/app/backend/routes/health_engine.py`
- Instinct signals: `/app/backend/routes/pietential_intel.py`

---

**END OF SSOT.** Copy any section verbatim into landing pages, decks, ads, or client docs. If ARIA gains new capabilities, update THIS file first — everything else references back here.
