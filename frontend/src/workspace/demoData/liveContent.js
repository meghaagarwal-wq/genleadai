/**
 * ARIA Universal Demo — LIVE content (iter173)
 *
 * Approvals queue + Instinct Feed signals + drafted-message templates,
 * per mode. All content is templated so we can substitute the prospect's
 * company name after enrichment and still read as specific, not generic.
 *
 * Template variables (all optional; every template must survive without them):
 *   {{brand}}       — prospect company name
 *   {{icp}}         — inferred ICP one-liner
 *   {{industry}}    — inferred industry token
 */

// ─────────────────────────── APPROVALS ───────────────────────────
// Each approval carries ONE or MORE drafted outputs the founder inspects.
// The drafts must read as sharp, real, and personalised — this is the
// "sold-in-30-seconds" moment.

export const APPROVALS = {
  b2c: [
    {
      id:      'ap1',
      tag:     'Outreach drafts',
      title:   'Drafted 3 win-back messages for high-intent lapsed customers',
      why:     'Detected 3 VIP buyers who haven\'t reordered in 45–60 days. LTV each > $340.',
      value:   '$1,240 potential recovery',
      urgency: 'high',
      drafts:  [
        {
          to:      'Priya M.  ·  VIP · last order 52d ago  ·  LTV $412',
          channel: 'Email',
          subject: 'Priya, we saved your favourite',
          body:
            "Hey Priya,\n\nYour Glow Serum is due for a refill — you last topped up in early Feb. " +
            "We just got a fresh batch of the same lot number you loved, and I set one aside so " +
            "you wouldn\'t have to hunt for it.\n\nOne click and it ships tomorrow with a note from me. " +
            "No discount code needed — I know you don't buy on price.\n\n— {{brand}}",
        },
        {
          to:      'Alex R.  ·  VIP · last order 60d ago  ·  LTV $340',
          channel: 'SMS',
          body:
            "Alex — small heads-up: the Renewal Cream you kept reordering is about to go on backorder. " +
            "Want me to hold the last two before it disappears? Just reply Y.",
        },
        {
          to:      'Maya S.  ·  VIP · last order 47d ago  ·  LTV $488',
          channel: 'Email',
          subject: "Maya — hand-picked for you",
          body:
            "Hi Maya,\n\nI noticed the Cleansing Balm dropped out of your rotation this month. " +
            "Everyone I know who used it with the Glow Serum swore they couldn\'t go back — I put " +
            "together the pair with 10% off, no code, click through and it\'s applied.\n\n— {{brand}}",
        },
      ],
    },
    {
      id:      'ap2',
      tag:     'Cold-lead recovery',
      title:   'Flagged 2 abandoned carts > $200 — drafted a nudge',
      why:     '2 customers filled a $200+ cart and dropped off. Both are first-timers.',
      value:   '$412 recoverable',
      urgency: 'medium',
      drafts: [
        {
          to:      'Naya K.  ·  first-time · cart $218',
          channel: 'Email',
          subject: 'Left the Vitamin C Kit in your cart?',
          body:
            "Hi Naya — I saw you had the Vitamin C Kit and Renewal Cream in your cart. " +
            "If it was the shade you weren\'t sure about, we ship a free 3-day trial before you commit. " +
            "Reply YES and I\'ll drop it in the post today.\n\n— {{brand}}",
        },
      ],
    },
    {
      id:      'ap3',
      tag:     'Waitlist unlock',
      title:   'Restock waitlist ready — draft one email to send to 82 people',
      why:     'Glow Serum is back in stock. 82 people opted into the waitlist.',
      value:   'Est. $2,410 in 24h',
      urgency: 'high',
      drafts: [
        {
          to:      '82 waitlisted customers',
          channel: 'Email · bulk',
          subject: "It's back. And I held one for you.",
          body:
            "You waited. I appreciate that.\n\nThe Glow Serum landed this morning. Because you were " +
            "on the list, one is with your name until 9 pm tonight. After that it goes public.\n\n— {{brand}}",
        },
      ],
    },
    {
      id:      'ap4',
      tag:     'Retention',
      title:   'Prepared VIP birthday drop — 12 customers hit birthday week',
      why:     '12 VIP customers have birthdays in the next 7 days. Avg LTV $286.',
      value:   'Loyalty · long-tail',
      urgency: 'low',
      drafts: [
        {
          to:      '12 birthday-week VIPs',
          channel: 'Email · templated',
          subject: 'Something for your week',
          body:
            "Hi — a little something on the house for your birthday week. No occasion needed to open it.\n" +
            "Redeem inside · valid 14 days · yours only.\n\n— {{brand}}",
        },
      ],
    },
  ],

  b2b: [
    {
      id:      'ap1',
      tag:     'Multi-thread outreach',
      title:   "Drafted CFO-level intro on 3 named accounts",
      why:     "3 target accounts moved to Stage 2 — champion identified but exec sponsor missing.",
      value:   '$412K pipeline · unlock',
      urgency: 'high',
      drafts: [
        {
          to:      "Anita Bose  ·  CFO, Meridian Retail  ·  target account",
          channel: 'Email',
          subject: 'Meridian × {{brand}} — CFO-lens intro',
          body:
            "Anita — your team just started a trial of {{brand}} last Tuesday. Two things I wanted to put " +
            "on your radar before your Q2 planning:\n\n" +
            "  1) Where the ROI shows up first (cash cycle, not headcount) — 22-day payback on the peer cohort.\n" +
            "  2) The one line-item in your SOC 2 that we cover natively so you don\'t rebuild in-house.\n\n" +
            "Happy to send a 90-second Loom sized to a CFO agenda, no pitch. Reply LOOM.\n\n— {{brand}}",
        },
        {
          to:      "Rahul Menon  ·  VP RevOps, Aegis Health  ·  target account",
          channel: 'LinkedIn',
          body:
            "Rahul — congrats on the Series C. Saw you posted about pipeline hygiene last week. " +
            "There\'s one graph from a health-tech peer that closed 41% faster after adopting {{brand}} — " +
            "want me to send it over? Two clicks, no meeting.",
        },
        {
          to:      "Priyanka Rao  ·  CRO, Basel Systems  ·  target account",
          channel: 'Email',
          subject: 'Basel × the Q4 forecast conversation',
          body:
            "Priyanka — you flagged forecast accuracy on the earnings call. Two of your peers " +
            "cut variance by 60% after moving to signal-based scoring. If you want the exact playbook, " +
            "no meeting needed — just reply PDF.\n\n— {{brand}}",
        },
      ],
    },
    {
      id:      'ap2',
      tag:     'Deal-risk save',
      title:   '2 late-stage deals going cold — drafted exec nudge',
      why:     'No inbound from champion in 8 days. Contract sent 12 days ago.',
      value:   '$168K at risk',
      urgency: 'high',
      drafts: [
        {
          to:      'Meridian Retail — deal $84K · stage Proposal',
          channel: 'Email · to champion',
          subject: 'Anything I can unblock on your side?',
          body:
            "Hey — I don\'t want to be the eighth follow-up. Two possibilities I can act on today:\n" +
            "  a) Legal has questions and it\'s stuck on redlines — I can loop our General Counsel in.\n" +
            "  b) Priorities shifted — no ego, just tell me and I\'ll pull the redlines back.\n\n" +
            "Either way I\'d rather know than guess.\n\n— {{brand}}",
        },
      ],
    },
    {
      id:      'ap3',
      tag:     'Call prep',
      title:   'Prepared full brief for tomorrow\'s 11 AM demo',
      why:     'Discovery call with Basel Systems, CRO + VP Sales attending.',
      value:   '$96K opp · Round-2',
      urgency: 'medium',
      drafts: [
        {
          to:      'Call brief · Basel Systems demo',
          channel: 'Internal',
          body:
            "Attending: Priyanka Rao (CRO), Devansh Mehta (VP Sales)\n\n" +
            "Priorities from discovery: forecast accuracy, ramp-time for SDRs, integration with Snowflake.\n\n" +
            "Landmines: they piloted a competitor 6 months ago and pulled the plug at day 40 — ask why " +
            "before you demo. Do NOT lead with automation.\n\n" +
            "Best next line: \"What would have needed to be true for the {competitor} pilot to have worked?\"",
        },
      ],
    },
    {
      id:      'ap4',
      tag:     'Renewal',
      title:   '4 renewals inside 90 days — drafted the pre-conversation',
      why:     'Auto-renew 90 days out. Two contracts have usage growth > 40%.',
      value:   '$186K ARR retention',
      urgency: 'medium',
      drafts: [
        {
          to:      'Aegis Health · $52K renewal',
          channel: 'Email · CS-led',
          subject: 'Aegis Q3 renewal — no surprises call',
          body:
            "Hi team — 90 days out from renewal so we can plan, not react. " +
            "Two options for the pre-conversation:\n" +
            "  a) 20-min business-review call (metrics, roadmap, blockers).\n" +
            "  b) Async doc — I send a 1-pager, you comment inline.\n\n" +
            "Pick whichever costs you less time.\n\n— {{brand}}",
        },
      ],
    },
  ],

  hybrid: [
    {
      id:      'ap1',
      tag:     'Wholesale reactivation',
      title:   'Drafted reactivation email to 6 lapsed wholesale accounts',
      why:     '6 café accounts haven\'t reordered in > 40 days. All at previous 7-day cadence.',
      value:   '$8,400 monthly revenue at risk',
      urgency: 'high',
      drafts: [
        {
          to:      'Ravi at Crema · lapsed 44d · avg order $980',
          channel: 'Email',
          subject: 'Ravi — Crema\'s house-blend queue is thin',
          body:
            "Ravi — quick check-in. Your Crema queue looks like it\'s running low on the 5-lb house " +
            "blend (based on your usual 7-day cadence). Two things:\n\n" +
            "  1) Anything I need to fix on our side — a late delivery, a bag that came sealed wrong?\n" +
            "  2) If it\'s just the roast profile you want to switch, our new Ethiopian is closer to a " +
            "     stone-fruit note than the caramel your team was mixed on.\n\n" +
            "Want me to send a 1-lb sample to your bar today?\n\n— {{brand}}",
        },
      ],
    },
    {
      id:      'ap2',
      tag:     'DTC subscription',
      title:   'Drafted subscription-anchor email to 240 first-order DTC buyers',
      why:     '240 customers made a first order in the last 21 days. Repeat rate is 46%.',
      value:   'Est. $6,200 subs MRR',
      urgency: 'medium',
      drafts: [
        {
          to:      '240 recent first-time DTC buyers',
          channel: 'Email · bulk',
          subject: 'You liked it. Let\'s make sure you never run out.',
          body:
            "You bought a bag. You told a friend. Now the tricky part — running out on a Wednesday.\n\n" +
            "The subscription is one click, cancel any time, and you\'ll get 10% back for as long as " +
            "you stay (no first-month gimmick).\n\n— {{brand}}",
        },
      ],
    },
    {
      id:      'ap3',
      tag:     'Trade-show follow-up',
      title:   'Prepared drip for 84 trade-show contacts',
      why:     'Coffee Fest wrapped 6 days ago. 84 scanned badges. Zero touches so far.',
      value:   '20 likely conversions',
      urgency: 'high',
      drafts: [
        {
          to:      '84 Coffee Fest contacts',
          channel: 'Email · 5-touch drip',
          subject: '{{brand}} × your bar — 3 minutes',
          body:
            "It was noisy on the floor and I\'m guessing we both said \"send me a sample\" more than we " +
            "meant it. So this is me actually sending one. Two blends, wholesale price sheet, " +
            "no pressure.\n\n— {{brand}}",
        },
      ],
    },
  ],
};

// ─────────────────────────── INSTINCT FEED ───────────────────────────
// Signals that stream in during the demo. Templates carry a "kind" so the
// UI can pick an accent color + icon. Deliberately worded to sound *like*
// a real system, not marketing copy.

export const INSTINCT_TEMPLATES = {
  b2c: [
    { kind: 'intent',     title: '3 VIP buyers just re-visited the Glow Serum page',            body: 'Three customers with LTV > $300 landed on the same PDP in the last 40 minutes. Reorder cycle is due.', cta: 'Send win-back',        weight: 92 },
    { kind: 'competitor', title: 'Competitor just launched a bundle at $79',                    body: 'Their bundle undercuts your Vitamin C Kit by $4. Search share for "vitamin c serum" up 12% this week.', cta: 'Draft counter offer', weight: 78 },
    { kind: 'drift',      title: 'ICP drift · UGC is skewing 8y younger than your target',      body: 'Meta ad creatives from the last 14 days are testing higher on 18–24 than your defined ICP (25–35).', cta: 'Update creative brief', weight: 66 },
    { kind: 'cold',       title: '2 subscription customers hit "skip" 3 months in a row',       body: 'When skip-rate goes 3+ months, churn probability jumps 4×. Both LTVs still net-positive to save.',   cta: 'Draft retention nudge', weight: 84 },
    { kind: 'signal',     title: 'Restock waitlist just crossed 80',                            body: 'Glow Serum waitlist is at 82. Historical conversion on waitlist emails is 34%.',                          cta: 'Prepare drop email',   weight: 88 },
    { kind: 'success',    title: 'Winback flow just recovered $412 in the last hour',           body: 'Two customers who last bought > 60d ago just checked out. Both from yesterday\'s draft you approved.',  cta: 'View orders',          weight: 95 },
    { kind: 'intent',     title: 'A first-timer added $218 to cart, no checkout yet',           body: 'Cart contains Vitamin C Kit + Renewal Cream. High-value combo — worth a personal note.',                cta: 'Draft nudge',          weight: 74 },
    { kind: 'signal',     title: 'Google Trends: "clean skincare" +23% this week',              body: 'Your brand\'s co-occurrence with the term is up 41% in the same window.',                              cta: 'Amplify on Meta',      weight: 68 },
  ],

  b2b: [
    { kind: 'intent',     title: '{{brand}} target account just visited pricing 3× this week',   body: 'Basel Systems opened /pricing yesterday, again this morning, and forwarded the page internally (share signal).', cta: 'Open account brief', weight: 94 },
    { kind: 'hiring',     title: 'Meridian is hiring 3 SDRs — expansion signal',                 body: 'Two of the three roles list "outbound automation" in the JD. Good time for a founder-to-VP intro.', cta: 'Draft VP intro',      weight: 89 },
    { kind: 'funding',    title: 'Aegis Health raised $22M Series C — signal detected',          body: 'They previously stalled on your Q4 evaluation. New CFO usually resets vendor list within 60 days.',  cta: 'Draft CFO email',      weight: 91 },
    { kind: 'competitor', title: 'Competitor announced a Salesforce native app',                 body: 'Two of your evaluations name-checked the missing native app as a concern. This closes that gap.',    cta: 'Update positioning',   weight: 76 },
    { kind: 'drift',      title: 'Your win rate on <$40K deals dropped 6 pts',                   body: 'Small deals now take same cycle length as $80K deals. Discovery is not filtering correctly.',       cta: 'Review discovery gate',weight: 70 },
    { kind: 'cold',       title: 'Champion at Basel hasn\'t opened your last 3 emails',          body: 'Priyanka went silent 8 days ago. Deal is stage Proposal, $96K. Escalate or de-risk to close.',     cta: 'Draft exec nudge',     weight: 88 },
    { kind: 'success',    title: 'Sequence "MQL → SDR handoff" just added $412K to pipeline',    body: 'Last 30 days, ARIA-authored sequence performed 2.3× your prior 90-day median.',                     cta: 'See attribution',      weight: 95 },
    { kind: 'signal',     title: '4 accounts crossed 3+ intent signals in 48h',                  body: 'All four are on your top-100 target list. Intent stack: pricing view + team invite + comparison search.', cta: 'Open account brief',   weight: 92 },
  ],

  hybrid: [
    { kind: 'intent',     title: '6 café accounts overdue on their weekly reorder',              body: 'All have historical 7-day cadence; last order 8–11 days ago. Combined weekly value: $1,840.',        cta: 'Draft reactivation',  weight: 89 },
    { kind: 'trade',      title: 'Coffee Fest badge scans are cooling — 6 days silent',          body: 'You collected 84 badges. Historical: touching within 7 days converts at 24%, past 14d drops to 4%.', cta: 'Send follow-up drip', weight: 92 },
    { kind: 'competitor', title: 'Regional roaster launched a $12/lb wholesale plan',            body: 'Your closest wholesale tier is $14/lb. Two of your accounts flagged price in the last quarter.',      cta: 'Review tier structure',weight: 68 },
    { kind: 'signal',     title: 'DTC subscription anchor is converting at 38%',                 body: 'First-order DTC to subscription is up 8 pts month-over-month. This is your #1 unit-economics unlock.', cta: 'Scale audience',      weight: 90 },
    { kind: 'drift',      title: 'Instagram creative CTR down 14% w/w',                          body: 'Reels with the barista are still outperforming; the product-only posts are dragging the average.',    cta: 'Rebrief creator',      weight: 62 },
    { kind: 'cold',       title: 'Ravi at Crema hasn\'t replied in 12 days',                     body: 'One of your top-5 wholesale accounts. Last order was on time. Silence is the signal.',                  cta: 'Founder-to-owner note',weight: 87 },
    { kind: 'success',    title: 'Winter blend launch teaser has 240 pre-orders',                body: 'Zero paid amplification. Warm list only. Historical pre-order conversion: 74%.',                        cta: 'Prepare launch email', weight: 93 },
  ],
};

// ─────────────────────── SAMPLE COMPANIES ───────────────────────────
// Shown as clickable chips beneath the "paste your domain" input.

export const SAMPLE_COMPANIES = [
  { domain: 'lumen-skin.com',  companyName: 'Lumen Skin',       tagline: 'Direct-to-consumer skincare',        mode: 'b2c',    icon: '✨' },
  { domain: 'cortexlabs.ai',   companyName: 'Cortex Labs',      tagline: 'AI ops platform for RevOps teams',   mode: 'b2b',    icon: '⚡' },
  { domain: 'northwind.coffee',companyName: 'Northwind Coffee', tagline: 'Wholesale + DTC specialty roaster',  mode: 'hybrid', icon: '☕' },
];

// ─────────────────────── mode inference ───────────────────────────
// Given enrichment keywords, guess whether the site is more B2B, B2C
// or Hybrid. Simple keyword-bucket voting; never blocks the demo.

const _MODE_HINTS = {
  b2b:    ['saas', 'platform', 'enterprise', 'crm', 'api', 'devtools', 'infrastructure',
           'workflow', 'compliance', 'security', 'analytics', 'b2b', 'sales', 'pipeline',
           'automation', 'operations', 'ops', 'agency', 'consulting'],
  b2c:    ['shop', 'skincare', 'beauty', 'apparel', 'fashion', 'wellness', 'fitness',
           'supplement', 'jewelry', 'jewellery', 'candles', 'home', 'baby', 'kids', 'pet',
           'dtc', 'food', 'drink', 'snack', 'organic'],
  hybrid: ['wholesale', 'retail', 'distributor', 'brand', 'restaurant', 'cafe', 'coffee',
           'catering', 'boutique', 'hospitality', 'salon', 'studio'],
};

export function inferModeFromKeywords(keywords) {
  if (!keywords || !keywords.length) return null;
  const scores = { b2b: 0, b2c: 0, hybrid: 0 };
  const set = new Set(keywords.map((k) => (k || '').toLowerCase()));
  for (const [mode, hints] of Object.entries(_MODE_HINTS)) {
    for (const h of hints) {
      if (set.has(h)) scores[mode] += 2;
      else {
        for (const k of set) {
          if (k.includes(h) || h.includes(k)) { scores[mode] += 1; break; }
        }
      }
    }
  }
  const [winner, score] = Object.entries(scores).sort((a, b) => b[1] - a[1])[0];
  return score >= 2 ? winner : null;
}

// Simple ICP inference from keywords (used in Command Center header + drafts)
export function inferICPFromKeywords(keywords, mode) {
  if (!keywords || !keywords.length) return null;
  const top = keywords.slice(0, 5).map((k) => k.replace(/-/g, ' '));
  if (!top.length) return null;
  const [a, b] = top;
  if (mode === 'b2b')    return `${(a || 'RevOps')[0].toUpperCase()}${(a || 'RevOps').slice(1)} teams at Series A–C SaaS`;
  if (mode === 'hybrid') return `Independent ${a || 'specialty'} shops · wholesale + DTC`;
  return `${(a || 'wellness')[0].toUpperCase()}${(a || 'wellness').slice(1)}-curious buyers, 25–40`;
}

// Personalise a template string with {{brand}} etc. Empty replacements OK.
export function personaliseText(str, vars) {
  if (!str) return str;
  return str.replace(/\{\{(\w+)\}\}/g, (_, k) => (vars && vars[k]) || '');
}
