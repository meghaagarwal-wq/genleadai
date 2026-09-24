/**
 * ARIA Universal Demo Dashboard — mock persona data (iter171)
 *
 * Three fully-mocked personas: B2C, B2B, Hybrid.
 * All numbers are hand-tuned to feel realistic for a live sales demo.
 * No backend calls. No network. All data is generated deterministically
 * inside this module so the dashboard is instant.
 */

// ───────────────────────── shared building blocks ─────────────────────────

const CHANNEL_META = {
  meta:     { label: 'Meta Ads',        hue: '#4F86FF' },
  google:   { label: 'Google Ads',      hue: '#EA6E5A' },
  linkedin: { label: 'LinkedIn',        hue: '#2E6BE6' },
  seo:      { label: 'Organic / SEO',   hue: '#7BC58F' },
  referral: { label: 'Referrals',       hue: '#B892E8' },
  email:    { label: 'Cold Email',      hue: '#F2B84B' },
  events:   { label: 'Events',          hue: '#E38FB0' },
  outbound: { label: 'Outbound',        hue: '#5FB1B8' },
};

// Build 30 days of series values that trend upward with some noise
function buildTrend(base, drift = 0.02, spread = 0.15, seed = 1) {
  let r = seed * 9.71;
  const out = [];
  let v = base;
  for (let i = 0; i < 30; i++) {
    r = (r * 9301 + 49297) % 233280;
    const rand = r / 233280;
    v = v * (1 + drift + (rand - 0.5) * spread);
    out.push({
      day: i + 1,
      label: `Day ${i + 1}`,
      value: Math.max(0, Math.round(v)),
    });
  }
  return out;
}

// ───────────────────────── B2C PERSONA ─────────────────────────
// "Lumen Skin" — DTC beauty brand, high-volume, low ticket.
const B2C = {
  key: 'b2c',
  label: 'B2C',
  brand: {
    name: 'Lumen Skin',
    tagline: 'Direct-to-consumer skincare',
    founder: 'Maya',
    currency: 'USD',
    ticket: 84,
  },
  header: {
    kpis: [
      { key: 'revenue',    label: 'Revenue (30d)',        value: '$248,120',    delta: '+18.4%', tone: 'up', sub: 'vs prior 30d' },
      { key: 'aov',        label: 'Avg. order value',     value: '$84',         delta: '+3.1%',  tone: 'up', sub: '+$2.50' },
      { key: 'roas',       label: 'Blended ROAS',         value: '4.2x',        delta: '+0.4x',  tone: 'up', sub: 'across paid' },
      { key: 'cac',        label: 'CAC',                  value: '$22',         delta: '−12%',   tone: 'up', sub: 'paid + owned' },
      { key: 'orders',     label: 'Orders (30d)',         value: '2,954',       delta: '+21%',   tone: 'up', sub: '98/day avg' },
      { key: 'ltv',        label: '90-day LTV',           value: '$168',        delta: '+9.2%',  tone: 'up', sub: 'repeat + subs' },
    ],
    revenueSpark: buildTrend(6800, 0.008, 0.18, 17),
  },
  // Source → Channel → Stage → Revenue (for Sankey)
  sankey: {
    nodes: [
      { id: 'Paid Social' }, { id: 'Search' }, { id: 'Organic' }, { id: 'Referral' },
      { id: 'Meta Ads' }, { id: 'TikTok Ads' }, { id: 'Google Ads' },
      { id: 'Instagram' }, { id: 'SEO' }, { id: 'Word of Mouth' },
      { id: 'Landing' }, { id: 'Add-to-cart' }, { id: 'Checkout' }, { id: 'Purchase' },
      { id: 'Revenue' },
    ],
    links: [
      { source: 'Paid Social', target: 'Meta Ads',    value: 42000 },
      { source: 'Paid Social', target: 'TikTok Ads',  value: 28500 },
      { source: 'Search',      target: 'Google Ads',  value: 31200 },
      { source: 'Organic',     target: 'Instagram',   value: 18400 },
      { source: 'Organic',     target: 'SEO',         value: 22100 },
      { source: 'Referral',    target: 'Word of Mouth', value: 12800 },
      { source: 'Meta Ads',    target: 'Landing', value: 42000 },
      { source: 'TikTok Ads',  target: 'Landing', value: 28500 },
      { source: 'Google Ads',  target: 'Landing', value: 31200 },
      { source: 'Instagram',   target: 'Landing', value: 18400 },
      { source: 'SEO',         target: 'Landing', value: 22100 },
      { source: 'Word of Mouth', target: 'Landing', value: 12800 },
      { source: 'Landing',     target: 'Add-to-cart', value: 82000 },
      { source: 'Landing',     target: 'Purchase',    value: 12500 },
      { source: 'Add-to-cart', target: 'Checkout',    value: 62000 },
      { source: 'Checkout',    target: 'Purchase',    value: 51000 },
      { source: 'Purchase',    target: 'Revenue',     value: 248120 },
    ],
  },
  channels: [
    { name: 'Meta Ads',    spend: 18400, revenue: 78400, roas: 4.3, cac: 19, orders: 934, trend: buildTrend(2600, 0.01, 0.2, 3) },
    { name: 'Google Ads',  spend: 12800, revenue: 54200, roas: 4.2, cac: 21, orders: 645, trend: buildTrend(1800, 0.005, 0.14, 7) },
    { name: 'TikTok Ads',  spend:  9200, revenue: 41800, roas: 4.5, cac: 24, orders: 498, trend: buildTrend(1400, 0.012, 0.22, 12) },
    { name: 'Instagram',   spend:  2100, revenue: 18400, roas: 8.8, cac:  8, orders: 219, trend: buildTrend( 650, 0.007, 0.19, 19) },
    { name: 'SEO',         spend:     0, revenue: 22100, roas: '∞', cac:  0, orders: 263, trend: buildTrend( 720, 0.015, 0.12, 22) },
    { name: 'Referrals',   spend:     0, revenue: 12800, roas: '∞', cac:  0, orders: 152, trend: buildTrend( 420, 0.02, 0.15, 27) },
  ],
  journey: buildTouchpoints('b2c'),
  automations: [
    { id: 'a1', name: 'Abandoned checkout — 3-touch',   status: 'live',   sent: 4820, opened: '58%', clicked: '22%', revenue: '$12,400' },
    { id: 'a2', name: 'Welcome series — new customers', status: 'live',   sent: 2140, opened: '71%', clicked: '38%', revenue: '$8,200' },
    { id: 'a3', name: 'Winback — 60d silent',           status: 'live',   sent: 1820, opened: '42%', clicked: '15%', revenue: '$5,900' },
    { id: 'a4', name: 'Post-purchase reorder nudge',    status: 'live',   sent:  980, opened: '64%', clicked: '29%', revenue: '$7,100' },
    { id: 'a5', name: 'VIP birthday drop',              status: 'draft',  sent:    0, opened: '—',   clicked: '—',   revenue: '—' },
    { id: 'a6', name: 'Waitlist → Restock',             status: 'live',   sent:  620, opened: '81%', clicked: '52%', revenue: '$3,400' },
  ],
  revenue: {
    cohorts: [
      { cohort: 'Jan',  m0: 100, m1: 42, m2: 28, m3: 21, m4: 18, m5: 16 },
      { cohort: 'Feb',  m0: 100, m1: 48, m2: 31, m3: 24, m4: 20, m5: null },
      { cohort: 'Mar',  m0: 100, m1: 52, m2: 34, m3: 27, m4: null, m5: null },
      { cohort: 'Apr',  m0: 100, m1: 55, m2: 38, m3: null, m4: null, m5: null },
      { cohort: 'May',  m0: 100, m1: 58, m2: null, m3: null, m4: null, m5: null },
      { cohort: 'Jun',  m0: 100, m1: null, m2: null, m3: null, m4: null, m5: null },
    ],
    ltvCurve: [
      { day:  0, ltv:  84 }, { day: 15, ltv:  98 }, { day: 30, ltv: 118 },
      { day: 45, ltv: 132 }, { day: 60, ltv: 148 }, { day: 75, ltv: 160 },
      { day: 90, ltv: 168 }, { day: 120, ltv: 182 }, { day: 150, ltv: 198 },
      { day: 180, ltv: 214 },
    ],
    products: [
      { name: 'Glow Serum',      units: 1420, revenue: '$71,000', margin: '68%' },
      { name: 'Renewal Cream',   units:  980, revenue: '$49,000', margin: '62%' },
      { name: 'Cleansing Balm',  units:  720, revenue: '$28,800', margin: '58%' },
      { name: 'Vitamin C Kit',   units:  480, revenue: '$38,400', margin: '71%' },
    ],
  },
  dataHealth: {
    overall: 94,
    dials: [
      { label: 'Meta Ads',      health: 100, sync: '2m ago',  note: 'Fully connected' },
      { label: 'Shopify',       health: 100, sync: '1m ago',  note: 'Fully connected' },
      { label: 'Klaviyo',       health:  92, sync: '4m ago',  note: '3 fields missing' },
      { label: 'Google Ads',    health:  88, sync: '9m ago',  note: 'API rate-limited' },
      { label: 'GA4',           health:  96, sync: '3m ago',  note: 'Healthy' },
      { label: 'TikTok Ads',    health:  84, sync: '18m ago', note: 'Refresh recommended' },
    ],
  },
};

// ───────────────────────── B2B PERSONA ─────────────────────────
// "Cortex Labs" — SaaS platform, higher ticket, longer cycle.
const B2B = {
  key: 'b2b',
  label: 'B2B',
  brand: {
    name: 'Cortex Labs',
    tagline: 'AI operations platform for RevOps teams',
    founder: 'Aditya',
    currency: 'USD',
    ticket: 24000,
  },
  header: {
    kpis: [
      { key: 'arr',       label: 'New ARR (Q)',         value: '$1.24M',   delta: '+31%',    tone: 'up', sub: '52 accts' },
      { key: 'pipeline',  label: 'Qualified pipeline',  value: '$4.8M',    delta: '+22%',    tone: 'up', sub: '104 opps' },
      { key: 'sql',       label: 'SQL rate',            value: '38%',      delta: '+6pt',    tone: 'up', sub: 'from MQL' },
      { key: 'cycle',     label: 'Cycle length',        value: '41d',      delta: '−9d',     tone: 'up', sub: 'median' },
      { key: 'winrate',   label: 'Win rate',            value: '28%',      delta: '+4pt',    tone: 'up', sub: 'closed / touched' },
      { key: 'acv',       label: 'Avg. contract value', value: '$24K',     delta: '+$3K',    tone: 'up', sub: 'ACV' },
    ],
    revenueSpark: buildTrend(38000, 0.014, 0.24, 41),
  },
  sankey: {
    nodes: [
      { id: 'Outbound' }, { id: 'Content' }, { id: 'Referral' }, { id: 'Events' },
      { id: 'LinkedIn' }, { id: 'Cold Email' }, { id: 'SEO' }, { id: 'Webinars' }, { id: 'Partners' },
      { id: 'MQL' }, { id: 'SQL' }, { id: 'Demo Booked' }, { id: 'Proposal' }, { id: 'Closed Won' },
      { id: 'ARR' },
    ],
    links: [
      { source: 'Outbound', target: 'LinkedIn',    value: 180 },
      { source: 'Outbound', target: 'Cold Email',  value: 240 },
      { source: 'Content',  target: 'SEO',         value:  95 },
      { source: 'Content',  target: 'Webinars',    value:  62 },
      { source: 'Referral', target: 'Partners',    value:  48 },
      { source: 'Events',   target: 'Partners',    value:  36 },
      { source: 'LinkedIn',   target: 'MQL', value: 180 },
      { source: 'Cold Email', target: 'MQL', value: 240 },
      { source: 'SEO',        target: 'MQL', value:  95 },
      { source: 'Webinars',   target: 'MQL', value:  62 },
      { source: 'Partners',   target: 'MQL', value:  84 },
      { source: 'MQL',         target: 'SQL',         value: 245 },
      { source: 'SQL',         target: 'Demo Booked', value: 168 },
      { source: 'Demo Booked', target: 'Proposal',    value:  92 },
      { source: 'Proposal',    target: 'Closed Won',  value:  52 },
      { source: 'Closed Won',  target: 'ARR',         value: 1240000 },
    ],
  },
  channels: [
    { name: 'LinkedIn Ads',  spend: 42000, revenue: 380000, roas: 9.0, cac: 810, orders:  52, trend: buildTrend(12500, 0.01, 0.24, 4) },
    { name: 'Cold Email',    spend:  8400, revenue: 220000, roas: 26.2, cac: 240, orders: 34, trend: buildTrend( 7200, 0.02, 0.19, 8) },
    { name: 'Outbound SDR',  spend: 68000, revenue: 410000, roas: 6.0, cac: 1450, orders: 47, trend: buildTrend(14000, 0.011, 0.18, 11) },
    { name: 'Content / SEO', spend: 22000, revenue: 190000, roas: 8.6, cac: 720, orders:  26, trend: buildTrend( 6300, 0.014, 0.16, 15) },
    { name: 'Webinars',      spend: 12000, revenue:  86000, roas: 7.2, cac: 950, orders:  13, trend: buildTrend( 2800, 0.008, 0.22, 20) },
    { name: 'Partners',      spend:  6400, revenue: 148000, roas: 23.1, cac: 380, orders:  21, trend: buildTrend( 4900, 0.016, 0.15, 25) },
  ],
  journey: buildTouchpoints('b2b'),
  automations: [
    { id: 'a1', name: 'MQL → SDR handoff',              status: 'live',  sent: 1240, opened: '68%', clicked: '31%', revenue: '$412K' },
    { id: 'a2', name: 'Multi-thread champion',          status: 'live',  sent:  820, opened: '74%', clicked: '42%', revenue: '$285K' },
    { id: 'a3', name: 'Stalled deal — exec nudge',      status: 'live',  sent:  480, opened: '81%', clicked: '38%', revenue: '$168K' },
    { id: 'a4', name: 'Renewal 90-day pre-work',        status: 'live',  sent:  320, opened: '84%', clicked: '46%', revenue: '$210K' },
    { id: 'a5', name: 'Trial → activation — day 3',     status: 'live',  sent:  680, opened: '62%', clicked: '28%', revenue: '$92K' },
    { id: 'a6', name: 'Waking dormant opps',            status: 'draft', sent:    0, opened: '—',   clicked: '—',   revenue: '—' },
  ],
  revenue: {
    cohorts: [
      { cohort: 'Q1 ‘24', m0: 100, m1: 96, m2: 93, m3: 91, m4: 89, m5: 87 },
      { cohort: 'Q2 ‘24', m0: 100, m1: 97, m2: 94, m3: 92, m4: 90, m5: null },
      { cohort: 'Q3 ‘24', m0: 100, m1: 98, m2: 95, m3: 93, m4: null, m5: null },
      { cohort: 'Q4 ‘24', m0: 100, m1: 98, m2: 96, m3: null, m4: null, m5: null },
      { cohort: 'Q1 ‘25', m0: 100, m1: 99, m2: null, m3: null, m4: null, m5: null },
      { cohort: 'Q2 ‘25', m0: 100, m1: null, m2: null, m3: null, m4: null, m5: null },
    ],
    ltvCurve: [
      { day:   0, ltv: 24000 }, { day:  90, ltv: 24000 }, { day: 180, ltv: 32000 },
      { day: 270, ltv: 41000 }, { day: 365, ltv: 52000 }, { day: 540, ltv: 68000 },
      { day: 730, ltv: 84000 }, { day: 900, ltv: 98000 }, { day: 1080, ltv: 112000 },
    ],
    products: [
      { name: 'Cortex Growth',    units: 24, revenue: '$576K', margin: '78%' },
      { name: 'Cortex Enterprise', units: 12, revenue: '$540K', margin: '82%' },
      { name: 'Cortex Starter',   units: 34, revenue: '$204K', margin: '71%' },
      { name: 'Integrations Add-on', units: 42, revenue: '$126K', margin: '86%' },
    ],
  },
  dataHealth: {
    overall: 91,
    dials: [
      { label: 'HubSpot',       health: 100, sync: '2m ago',  note: 'Healthy' },
      { label: 'Salesforce',    health:  96, sync: '4m ago',  note: 'Healthy' },
      { label: 'Gong',          health:  88, sync: '6m ago',  note: 'Some calls missing' },
      { label: 'Slack',         health: 100, sync: '1m ago',  note: 'Healthy' },
      { label: 'LinkedIn Ads',  health:  84, sync: '11m ago', note: 'Refresh recommended' },
      { label: 'Clearbit',      health:  78, sync: '22m ago', note: '12% unenriched' },
    ],
  },
};

// ───────────────────────── HYBRID PERSONA ─────────────────────────
// "Northwind Coffee" — Wholesale + DTC, mid-ticket, mixed cycle.
const HYBRID = {
  key: 'hybrid',
  label: 'Hybrid',
  brand: {
    name: 'Northwind Coffee',
    tagline: 'Wholesale + DTC specialty roaster',
    founder: 'Priya',
    currency: 'USD',
    ticket: 340,
  },
  header: {
    kpis: [
      { key: 'revenue',   label: 'Revenue (30d)',      value: '$412,800', delta: '+14%',   tone: 'up', sub: 'DTC + wholesale' },
      { key: 'accts',     label: 'Wholesale accts',    value: '184',      delta: '+11',    tone: 'up', sub: 'net new' },
      { key: 'dtc',       label: 'DTC orders',         value: '2,318',    delta: '+17%',   tone: 'up', sub: 'in 30d' },
      { key: 'aov',       label: 'Blended AOV',        value: '$178',     delta: '+$12',   tone: 'up', sub: 'weighted' },
      { key: 'repeat',    label: 'Repeat rate',        value: '46%',      delta: '+4pt',   tone: 'up', sub: '90d window' },
      { key: 'nps',       label: 'NPS (rolling)',      value: '62',       delta: '+8',     tone: 'up', sub: 'past quarter' },
    ],
    revenueSpark: buildTrend(11500, 0.011, 0.18, 33),
  },
  sankey: {
    nodes: [
      { id: 'Wholesale' }, { id: 'DTC' }, { id: 'Retail' },
      { id: 'Cold Email' }, { id: 'Trade Shows' }, { id: 'Meta Ads' }, { id: 'SEO' }, { id: 'Referral' }, { id: 'Instagram' },
      { id: 'Onboarding' }, { id: 'First Order' }, { id: 'Reorder' }, { id: 'Subscription' },
      { id: 'Revenue' },
    ],
    links: [
      { source: 'Wholesale', target: 'Cold Email',    value: 84 },
      { source: 'Wholesale', target: 'Trade Shows',   value: 42 },
      { source: 'DTC',       target: 'Meta Ads',      value: 620 },
      { source: 'DTC',       target: 'Instagram',     value: 340 },
      { source: 'DTC',       target: 'SEO',           value: 280 },
      { source: 'Retail',    target: 'Referral',      value: 68 },
      { source: 'Cold Email',  target: 'Onboarding', value: 84 },
      { source: 'Trade Shows', target: 'Onboarding', value: 42 },
      { source: 'Meta Ads',    target: 'First Order', value: 620 },
      { source: 'Instagram',   target: 'First Order', value: 340 },
      { source: 'SEO',         target: 'First Order', value: 280 },
      { source: 'Referral',    target: 'First Order', value:  68 },
      { source: 'Onboarding',  target: 'First Order', value: 126 },
      { source: 'First Order', target: 'Reorder',     value: 780 },
      { source: 'First Order', target: 'Subscription', value: 420 },
      { source: 'Reorder',      target: 'Revenue', value: 168000 },
      { source: 'Subscription', target: 'Revenue', value: 244800 },
    ],
  },
  channels: [
    { name: 'Meta Ads',      spend: 14200, revenue: 84400, roas: 5.9, cac: 22, orders: 512, trend: buildTrend(3200, 0.012, 0.18, 6) },
    { name: 'Wholesale SDR', spend: 12000, revenue: 148000, roas: 12.3, cac: 260, orders: 46, trend: buildTrend(4200, 0.014, 0.16, 10) },
    { name: 'Instagram',     spend:  3200, revenue: 42000, roas: 13.1, cac:  9, orders: 268, trend: buildTrend(1200, 0.008, 0.2, 14) },
    { name: 'SEO',           spend:     0, revenue: 68000, roas: '∞', cac:  0, orders: 380, trend: buildTrend(2100, 0.016, 0.14, 18) },
    { name: 'Trade Shows',   spend: 18000, revenue: 62000, roas: 3.4, cac: 780, orders: 22, trend: buildTrend( 800, 0.008, 0.28, 24) },
    { name: 'Referrals',     spend:     0, revenue: 8400,  roas: '∞', cac:  0, orders:  48, trend: buildTrend( 260, 0.02, 0.15, 29) },
  ],
  journey: buildTouchpoints('hybrid'),
  automations: [
    { id: 'a1', name: 'Wholesale nurture — 5 emails',   status: 'live',  sent: 1420, opened: '61%', clicked: '28%', revenue: '$62K' },
    { id: 'a2', name: 'DTC subscription anchor',        status: 'live',  sent: 2140, opened: '68%', clicked: '34%', revenue: '$84K' },
    { id: 'a3', name: 'Reorder reminder — 21 days',     status: 'live',  sent: 3120, opened: '58%', clicked: '22%', revenue: '$48K' },
    { id: 'a4', name: 'Café-owner activation',          status: 'live',  sent:  420, opened: '77%', clicked: '46%', revenue: '$32K' },
    { id: 'a5', name: 'Winter blend launch',            status: 'draft', sent:    0, opened: '—',   clicked: '—',   revenue: '—' },
    { id: 'a6', name: 'Broken-machine winback',         status: 'live',  sent:  240, opened: '72%', clicked: '38%', revenue: '$14K' },
  ],
  revenue: {
    cohorts: [
      { cohort: 'Jan', m0: 100, m1: 62, m2: 48, m3: 41, m4: 37, m5: 34 },
      { cohort: 'Feb', m0: 100, m1: 66, m2: 52, m3: 44, m4: 39, m5: null },
      { cohort: 'Mar', m0: 100, m1: 69, m2: 55, m3: 47, m4: null, m5: null },
      { cohort: 'Apr', m0: 100, m1: 71, m2: 58, m3: null, m4: null, m5: null },
      { cohort: 'May', m0: 100, m1: 74, m2: null, m3: null, m4: null, m5: null },
      { cohort: 'Jun', m0: 100, m1: null, m2: null, m3: null, m4: null, m5: null },
    ],
    ltvCurve: [
      { day:   0, ltv: 178 }, { day:  30, ltv: 268 }, { day:  60, ltv: 340 },
      { day:  90, ltv: 412 }, { day: 120, ltv: 482 }, { day: 180, ltv: 610 },
      { day: 270, ltv: 780 }, { day: 365, ltv: 920 }, { day: 540, ltv: 1180 },
    ],
    products: [
      { name: 'House Blend (Wholesale 5lb)', units: 486, revenue: '$97,200', margin: '48%' },
      { name: 'Single Origin — Ethiopia',    units: 620, revenue: '$68,200', margin: '62%' },
      { name: 'Cold Brew Kit',               units: 340, revenue: '$47,600', margin: '58%' },
      { name: 'Subscription — Monthly',      units: 812, revenue: '$142,100', margin: '71%' },
    ],
  },
  dataHealth: {
    overall: 89,
    dials: [
      { label: 'Shopify',       health: 100, sync: '1m ago',  note: 'Healthy' },
      { label: 'Klaviyo',       health:  94, sync: '3m ago',  note: 'Healthy' },
      { label: 'HubSpot (WS)',  health:  88, sync: '6m ago',  note: '2 sequences paused' },
      { label: 'QuickBooks',    health:  82, sync: '12m ago', note: 'Refresh recommended' },
      { label: 'Meta Ads',      health:  96, sync: '2m ago',  note: 'Healthy' },
      { label: 'Google Ads',    health:  76, sync: '18m ago', note: 'Token expiring' },
    ],
  },
};

// ───────────────────────── shared: 32-touchpoint journey ─────────────────────────
function buildTouchpoints(mode) {
  const catalog = {
    b2c: [
      ['Ad impression',       'Meta Ads',   'view',      'Awareness'],
      ['Ad click',            'Meta Ads',   'click',     'Awareness'],
      ['Landing page',        'Web',        'visit',     'Consideration'],
      ['Quiz taken',          'Web',        'engage',    'Consideration'],
      ['Email captured',      'Klaviyo',    'sub',       'Consideration'],
      ['Welcome email 1',     'Email',      'send',      'Consideration'],
      ['Product view',        'Web',        'visit',     'Consideration'],
      ['Add-to-cart',         'Web',        'action',    'Consideration'],
      ['Abandoned checkout',  'System',     'signal',    'Consideration'],
      ['SMS reminder',        'SMS',        'send',      'Consideration'],
      ['Discount code',       'Email',      'send',      'Consideration'],
      ['Purchase',            'Shopify',    'convert',   'Purchase'],
      ['Thank-you email',     'Email',      'send',      'Onboarding'],
      ['Order shipped',       'Shopify',    'status',    'Onboarding'],
      ['Delivered',           'Shopify',    'status',    'Onboarding'],
      ['Review request',      'Email',      'send',      'Onboarding'],
      ['Review submitted',    'Yotpo',      'engage',    'Advocacy'],
      ['Refer-a-friend',      'Email',      'send',      'Advocacy'],
      ['Reorder nudge',       'Email',      'send',      'Repeat'],
      ['UGC on Instagram',    'Instagram',  'engage',    'Advocacy'],
      ['VIP tier reached',    'Klaviyo',    'status',    'Loyalty'],
      ['Restock waitlist',    'Web',        'sub',       'Repeat'],
      ['Restock email',       'Email',      'send',      'Repeat'],
      ['Second purchase',     'Shopify',    'convert',   'Repeat'],
      ['Subscribe',           'Shopify',    'sub',       'Loyalty'],
      ['Sub delivery 1',      'Shopify',    'status',    'Loyalty'],
      ['Skip request',        'Shopify',    'action',    'Loyalty'],
      ['Retention win',       'ARIA',       'signal',    'Loyalty'],
      ['Birthday drop',       'Email',      'send',      'Loyalty'],
      ['NPS survey',          'Email',      'send',      'Loyalty'],
      ['Refer converted',     'ARIA',       'convert',   'Advocacy'],
      ['LTV milestone $500',  'ARIA',       'signal',    'Loyalty'],
    ],
    b2b: [
      ['LinkedIn view',       'LinkedIn',   'view',      'Awareness'],
      ['Ad click',            'LinkedIn Ads','click',    'Awareness'],
      ['SEO landing',         'Web',        'visit',     'Awareness'],
      ['Content download',    'Web',        'sub',       'Consideration'],
      ['Nurture email 1',     'Email',      'send',      'Consideration'],
      ['Cold email opened',   'Email',      'engage',    'Consideration'],
      ['Cold email reply',    'Email',      'engage',    'Consideration'],
      ['Website revisit',     'Web',        'visit',     'Consideration'],
      ['Demo booked',         'ARIA',       'convert',   'Evaluation'],
      ['Discovery call',      'Zoom',       'call',      'Evaluation'],
      ['Follow-up email',     'Email',      'send',      'Evaluation'],
      ['Champion identified', 'ARIA',       'signal',    'Evaluation'],
      ['Multi-thread email',  'ARIA',       'send',      'Evaluation'],
      ['Deep-dive demo',      'Zoom',       'call',      'Evaluation'],
      ['Proposal sent',       'Docs',       'send',      'Proposal'],
      ['Pricing question',    'Email',      'engage',    'Proposal'],
      ['Security review',     'Docs',       'engage',    'Proposal'],
      ['MSA reviewed',        'Docs',       'engage',    'Proposal'],
      ['Legal redlines',      'Docs',       'engage',    'Proposal'],
      ['Exec alignment',      'ARIA',       'signal',    'Proposal'],
      ['Verbal yes',          'ARIA',       'signal',    'Close'],
      ['Contract sent',       'Docs',       'send',      'Close'],
      ['Contract signed',     'Docs',       'convert',   'Close'],
      ['Kickoff scheduled',   'Calendar',   'action',    'Onboarding'],
      ['Kickoff call',        'Zoom',       'call',      'Onboarding'],
      ['Data ingest',         'System',     'status',    'Onboarding'],
      ['First value',         'ARIA',       'signal',    'Adoption'],
      ['Executive review',    'Zoom',       'call',      'Adoption'],
      ['Expansion signal',    'ARIA',       'signal',    'Expansion'],
      ['Upsell demo',         'Zoom',       'call',      'Expansion'],
      ['Contract expansion',  'Docs',       'convert',   'Expansion'],
      ['Advocacy — case study','ARIA',       'signal',    'Advocacy'],
    ],
    hybrid: [
      ['Instagram reel view', 'Instagram',   'view',     'Awareness'],
      ['Ad click',            'Meta Ads',    'click',    'Awareness'],
      ['Landing page',        'Web',         'visit',    'Consideration'],
      ['Free sample request', 'Web',         'sub',      'Consideration'],
      ['Sample shipped',      'Shopify',     'status',   'Consideration'],
      ['Sample delivered',    'Shopify',     'status',   'Consideration'],
      ['Feedback email',      'Email',       'send',     'Consideration'],
      ['Cold email — café',   'ARIA',        'send',     'Consideration'],
      ['Reply received',      'Email',       'engage',   'Consideration'],
      ['Discovery call',      'Zoom',        'call',     'Evaluation'],
      ['Quote sent',          'Docs',        'send',     'Evaluation'],
      ['Trial order',         'Shopify',     'convert',  'Evaluation'],
      ['Onboarding call',     'Zoom',        'call',     'Onboarding'],
      ['Equipment delivered', 'Shopify',     'status',   'Onboarding'],
      ['Training completed',  'ARIA',        'signal',   'Onboarding'],
      ['First serving',       'POS',         'signal',   'Adoption'],
      ['Weekly restock',      'Shopify',     'convert',  'Repeat'],
      ['Reorder nudge',       'Email',       'send',     'Repeat'],
      ['DTC subscription',    'Shopify',     'sub',      'Loyalty'],
      ['Sub delivery',        'Shopify',     'status',   'Loyalty'],
      ['Review request',      'Email',       'send',     'Advocacy'],
      ['UGC posted',          'Instagram',   'engage',   'Advocacy'],
      ['Referral offered',    'Email',       'send',     'Advocacy'],
      ['Referral converted',  'ARIA',        'convert',  'Advocacy'],
      ['NPS survey',          'Email',       'send',     'Loyalty'],
      ['Winter blend release','Email',       'send',     'Repeat'],
      ['Trade-show pickup',   'Events',      'engage',   'Awareness'],
      ['Wholesale intro',     'ARIA',        'signal',   'Consideration'],
      ['B2B onboarding',      'System',      'status',   'Onboarding'],
      ['Volume tier upgrade', 'ARIA',        'signal',   'Expansion'],
      ['Café location #2',    'Shopify',     'convert',  'Expansion'],
      ['Testimonial recorded','ARIA',        'signal',   'Advocacy'],
    ],
  }[mode];

  return catalog.map((row, i) => ({
    idx: i + 1,
    name: row[0],
    channel: row[1],
    kind: row[2],
    stage: row[3],
    // day offset — spread across ~90 days for a plausible journey
    dayOffset: Math.round((i / 31) * 90),
  }));
}

// ───────────────────────── automation flow (nodes + edges) ─────────────────────────
const AUTOMATION_FLOWS = {
  b2c: {
    title: 'Abandoned Checkout → Winback',
    nodes: [
      { id: 'n1', label: 'Trigger', sub: 'Cart abandoned > 1h',   type: 'trigger', x: 40,  y: 60  },
      { id: 'n2', label: 'Wait',    sub: '1 hour',                type: 'wait',    x: 200, y: 60  },
      { id: 'n3', label: 'Email',   sub: '"Left something?"',     type: 'action',  x: 360, y: 60  },
      { id: 'n4', label: 'If',      sub: 'Opened within 6h',      type: 'branch',  x: 520, y: 60  },
      { id: 'n5', label: 'SMS',     sub: 'Nudge + 10% code',      type: 'action',  x: 680, y: 20  },
      { id: 'n6', label: 'Wait',    sub: '24 hours',              type: 'wait',    x: 680, y: 130 },
      { id: 'n7', label: 'Email',   sub: '"Still thinking?"',     type: 'action',  x: 840, y: 130 },
      { id: 'n8', label: 'End',     sub: 'Purchased or exhaust',  type: 'end',     x: 1000, y: 90 },
    ],
    edges: [
      { from: 'n1', to: 'n2' }, { from: 'n2', to: 'n3' },
      { from: 'n3', to: 'n4' }, { from: 'n4', to: 'n5', label: 'yes' },
      { from: 'n4', to: 'n6', label: 'no' }, { from: 'n6', to: 'n7' },
      { from: 'n5', to: 'n8' }, { from: 'n7', to: 'n8' },
    ],
  },
  b2b: {
    title: 'MQL → SQL → Handoff',
    nodes: [
      { id: 'n1', label: 'Trigger', sub: 'Marketing form fill',   type: 'trigger', x: 40,  y: 60  },
      { id: 'n2', label: 'Enrich',  sub: 'Clearbit + LinkedIn',   type: 'action',  x: 200, y: 60  },
      { id: 'n3', label: 'Score',   sub: 'ICP fit',               type: 'action',  x: 360, y: 60  },
      { id: 'n4', label: 'If',      sub: 'Fit ≥ 70',              type: 'branch',  x: 520, y: 60  },
      { id: 'n5', label: 'SDR ping', sub: 'Slack + task',         type: 'action',  x: 680, y: 20  },
      { id: 'n6', label: 'Nurture', sub: '5-touch email',         type: 'action',  x: 680, y: 130 },
      { id: 'n7', label: 'Wait',    sub: '3 business days',       type: 'wait',    x: 840, y: 20  },
      { id: 'n8', label: 'Handoff', sub: 'Meeting booked',        type: 'end',     x: 1000, y: 60 },
    ],
    edges: [
      { from: 'n1', to: 'n2' }, { from: 'n2', to: 'n3' },
      { from: 'n3', to: 'n4' }, { from: 'n4', to: 'n5', label: 'yes' },
      { from: 'n4', to: 'n6', label: 'no' }, { from: 'n5', to: 'n7' },
      { from: 'n7', to: 'n8' }, { from: 'n6', to: 'n8' },
    ],
  },
  hybrid: {
    title: 'Sample → Wholesale Order',
    nodes: [
      { id: 'n1', label: 'Trigger', sub: 'Sample requested',      type: 'trigger', x: 40,  y: 60  },
      { id: 'n2', label: 'Ship',    sub: 'Sample + brochure',     type: 'action',  x: 200, y: 60  },
      { id: 'n3', label: 'Wait',    sub: '5 days',                type: 'wait',    x: 360, y: 60  },
      { id: 'n4', label: 'Email',   sub: '"How was it?"',         type: 'action',  x: 520, y: 60  },
      { id: 'n5', label: 'If',      sub: 'Replied yes',           type: 'branch',  x: 680, y: 60  },
      { id: 'n6', label: 'Call',    sub: 'Rep books demo',        type: 'action',  x: 840, y: 20  },
      { id: 'n7', label: 'Nurture', sub: '3-touch drip',          type: 'action',  x: 840, y: 130 },
      { id: 'n8', label: 'Close',   sub: 'First order shipped',   type: 'end',     x: 1000, y: 60 },
    ],
    edges: [
      { from: 'n1', to: 'n2' }, { from: 'n2', to: 'n3' },
      { from: 'n3', to: 'n4' }, { from: 'n4', to: 'n5' },
      { from: 'n5', to: 'n6', label: 'yes' }, { from: 'n5', to: 'n7', label: 'no' },
      { from: 'n6', to: 'n8' }, { from: 'n7', to: 'n8' },
    ],
  },
};

export const PERSONAS = { b2c: B2C, b2b: B2B, hybrid: HYBRID };
export const PERSONA_ORDER = ['b2c', 'b2b', 'hybrid'];
export { CHANNEL_META, AUTOMATION_FLOWS };
