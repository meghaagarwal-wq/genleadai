# B2C Demo Dashboard — Standalone Export

Self-contained React component extracted from **ARIA / GenLeadAI**.
Drop into any React 18 / React 19 project and wire to your own backend.

---

## 1. Files in this bundle

| File | What it is |
|---|---|
| `B2CDashboard.jsx` | The full dashboard component (~430 LOC). Default export + named export. |
| `b2c_dashboard.schema.json` | JSON schema of the exact payload your backend must return at `GET /api/dashboard/b2c`. |
| `sample_response.json` | A real, populated example response (10 leads, all stages, all widgets filled). |
| `README.md` | This file. |

---

## 2. Install

```bash
yarn add react react-dom @phosphor-icons/react
# Tailwind recommended but optional — the markup uses utility classes.
yarn add -D tailwindcss postcss autoprefixer
```

## 3. Wire it up

```jsx
import B2CDashboard from './B2CDashboard.jsx';

function App() {
  return (
    <B2CDashboard
      onLeadClick={(leadId) => router.push(`/leads/${leadId}`)}
      onViewAllConversations={() => router.push('/conversations')}
    />
  );
}
```

### Configure the backend URL

The component reads from `process.env.REACT_APP_API_BASE` (CRA / Vite envs).
If your backend is on the same origin, leave it blank.

```env
REACT_APP_API_BASE=https://api.yourdomain.com
```

### Auth

`getAuthToken()` reads `localStorage.auth_token` by default. Open
`B2CDashboard.jsx`, replace it with your own integration:

```js
const getAuthToken = () => yourAuthContext.getAccessToken();
```

---

## 4. Backend contract — `GET /api/dashboard/b2c`

Your backend MUST return the JSON shape below. Optional fields are marked.

```ts
type B2CDashboardResponse = {
  header: {
    greeting: string;          // "Good morning"
    owner_name: string;
    workspace_name: string;
    currency: 'INR' | 'USD' | 'GBP' | 'AED' | 'EUR';
  };

  kpis: {
    leads_today:     { value: number, trend?: { direction: 'up'|'down'|'flat', pct: number } };
    active_convos:   { value: number, label?: string };
    bookings_week:   { value: number, trend?: { direction, pct } };
    conversion_rate: { value: number, trend?: { direction, pct } };   // percentage
    revenue_pipeline:{ value: number, currency: string };
  };

  aria_time_saved: {
    hours: number;
    money_equivalent: number;
    breakdown: { conversations: number, drafts: number, insights: number, researched: number };
  };

  momentum: {
    direction: 'up' | 'down' | 'flat';
    score: number;                  // 0..100
    label: string;                  // "Accelerating"
    driver_text: string;            // "Hot leads up 30%"
  };

  revenue_forecast:
    | { coming_soon: true }
    | { coming_soon: false, projected_end_of_month: number, last_month_actual: number, pct_of_last_month: number };

  conversations: Array<{
    lead_id: string;
    name: string;
    initials: string;               // "JD"
    status: 'live' | 'waiting' | 'booked' | 'qualified';
    snippet: string;                // last message preview, <=120 chars
    minutes_ago: number;
  }>;

  lead_sources: Array<{
    channel: string;                // "linkedin" | "whatsapp" | "email" | ...
    count: number;
    colour?: string;                // hex; falls back to built-in palette
  }>;

  asset_performance:
    | { coming_soon: true, rows: [] }
    | { coming_soon: false, rows: Array<{ name: string, clicks: number }> };

  funnel: Array<{
    stage: string;                  // "Discovered", "Engaged", "Qualified", "Replied", "Booked"
    count: number;
    pct_of_prev?: number;
    drop_flag?: boolean;
  }>;

  biggest_drop?: { from: string, to: string, loss_pct: number };

  sequences: Array<{
    name: string;
    active: number;
    booked: number;
    rate: number;                   // percentage 0..100
  }>;

  channel_overlap:
    | { coming_soon: true, rows: [] }
    | { coming_soon: false, rows: Array<{ channels: string, leads: number, conv_rate: number }> };

  ghost_leads: Array<{
    id: string;
    name: string;
    company: string;
    days_silent: number;
  }>;

  cost_per_qualified_lead:
    | { coming_soon: true, rows: [] }
    | { coming_soon: false, rows: Array<{ channel: string, spend: number, qualified: number, cpql: number|null, currency: string }> };
};
```

See `sample_response.json` for a fully-populated example.

---

## 5. Theming

The component uses CSS variables with **safe defaults**, so it works out
of the box on a white background. Override these to match your brand:

```css
:root {
  --theme-text:         #111827;
  --theme-text-muted:   #6B7280;
  --theme-surface:      #FFFFFF;   /* card backgrounds */
  --theme-surface2:     #F3F4F6;   /* secondary surfaces, hover states */
  --theme-border:       #E5E7EB;
  --theme-purple-light: #A78BFA;   /* accents */
}

/* Dark mode example */
.dark {
  --theme-text:         #F1F5F9;
  --theme-text-muted:   #94A3B8;
  --theme-surface:      #1E293B;
  --theme-surface2:     #334155;
  --theme-border:       #475569;
  --theme-purple-light: #A78BFA;
}
```

---

## 6. Minimum data needed to "look alive"

If you're spinning up a new backend, the dashboard renders nicely when
your DB has at least:

- ≥3 leads created today (powers KPI `leads_today` + `lead_sources`)
- ≥5 leads with `score >= 40` (powers `pipeline_value` + `ghost_leads`)
- ≥2 active conversations in the last 2h (powers Live Conversations)
- ≥3 booking events this month (powers Bookings KPI + Revenue Forecast)
- ≥1 ad-spend row (powers `cost_per_qualified_lead`)
- ≥2 leads with multi-channel `source_channels` arrays (powers `channel_overlap`)

Without these, those widgets show a friendly `Coming soon — …` empty state.

---

## 7. License & support

Exported from ARIA / GenLeadAI for client-facing demo use. No warranty.
For questions, ping the GenLeadAI team.
