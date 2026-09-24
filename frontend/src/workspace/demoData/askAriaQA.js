/**
 * askAriaQA — iter174
 *
 * A small library of canned smart questions the demo prospect can ask.
 * Each question maps to a rich, mode-scoped response (headline + 2–4
 * data-backed bullets) AND an "action card" that gets injected into the
 * Approvals queue when the prospect taps "Draft this".
 *
 * The point isn't to be an LLM. The point is that on stage the founder
 * clicks 1 of 6 questions and ARIA gives a specific, plausible reply
 * pinned to the seeded persona data.
 */

// Every entry: { id, question, replyFor: { b2c, b2b, hybrid } → { headline, bullets[], action }
// action = { tag, title, why, value, urgency, drafts[] }  — same shape as APPROVALS entries.

const A = {
  b2c: {
    channel_waste: {
      headline: 'Meta Ads at the $79 bundle is your leak',
      bullets: [
        'Meta ROAS on the Vitamin C Kit bundle dropped from 5.9× to 3.1× over 14 days.',
        'The same ad set is targeting an ICP-drifted 18–24 cohort, not your 25–35 buyer.',
        'Cutting the 18–24 exclusion returns ~$4,200/mo in retained margin.',
      ],
      action: {
        tag: 'Ad optimisation', urgency: 'medium', value: '$4,200/mo saved',
        title: 'Tighten Meta targeting and pause the $79 bundle set',
        why: 'ROAS on the Vitamin C Kit bundle fell 47% in 14 days on drifted audience.',
        drafts: [{
          to: 'Marketing manager', channel: 'Internal',
          body: "Meta bundle set (id 4b7a-c) is drifting to 18–24 and burning $4.2K/mo. Pause it and re-run the working audience (25–35, high-intent skincare). I've queued the audience diff and creative rebrief. Approve to ship.",
        }],
      },
    },
    call_today: {
      headline: '3 VIPs are due for outreach today',
      bullets: [
        '3 buyers with LTV > $340 have not reordered in 47–60 days.',
        'All 3 revisited the Glow Serum page in the last 48 hours.',
        'Recovery probability with a personal note is 62% based on historical cohort.',
      ],
      action: {
        tag: 'VIP outreach', urgency: 'high', value: '$1,240 potential recovery',
        title: 'Send 3 personal win-back notes to lapsed VIPs',
        why: '3 VIPs (Priya M., Alex R., Maya S.) — LTV avg $413, reorder overdue.',
        drafts: [
          { to: 'Priya M. · VIP · 52d lapsed', channel: 'Email', subject: 'Priya, we saved your favourite',
            body: "Hey Priya — your Glow Serum is due for a refill. Same lot number, one bag set aside with a note from me. No discount, no gimmick. Ships tomorrow.\n\n— {{brand}}" },
        ],
      },
    },
    ltv_lever: {
      headline: 'Post-purchase subscription anchor is your unlock',
      bullets: [
        'Repeat-rate is 38% at day 60; the subscription anchor is currently only shown post-checkout to 22% of buyers.',
        'Shown to 100%, projected LTV lift on first-order cohort is +$46 in 90 days.',
        'One flow change. Zero acquisition cost.',
      ],
      action: {
        tag: 'Retention', urgency: 'medium', value: '+$46 LTV per new customer',
        title: 'Show subscription anchor on every order confirmation',
        why: 'Currently limited to 22% coverage. Full coverage lifts 90d LTV +38%.',
        drafts: [{ to: 'Growth engineer', channel: 'Internal',
          body: "Turn on subscription anchor for 100% of order confirmations (currently 22%). Projected +$46 LTV on first-time buyers over 90 days. Change is a single flag in the checkout confirmation template.",
        }],
      },
    },
  },

  b2b: {
    channel_waste: {
      headline: 'Outbound SDR at $1,450 CAC is your leak',
      bullets: [
        'SDR outbound converts at $1,450 CAC vs $240 on cold email — 6× more expensive per closed opp.',
        '43% of SDR-sourced deals lose to "no decision" (i.e., dead pipeline, not real losses).',
        'Reallocating 30% of SDR capacity to a champion-multi-thread play returns $180K ARR in Q.',
      ],
      action: {
        tag: 'GTM reallocation', urgency: 'high', value: '$180K ARR in Q',
        title: 'Reallocate 30% of SDR capacity to multi-thread motion',
        why: 'SDR CAC $1,450 vs cold email $240 · SDR "no-decision" rate 43%.',
        drafts: [{ to: 'VP Sales', channel: 'Email', subject: 'GTM reallocation — 30 min next Tue',
          body: "Two data points I want to talk about before Q3 planning:\n\n  1) SDR CAC is 6× your cold email CAC ($1,450 vs $240).\n  2) 43% of SDR-sourced opps close as \"no decision\" — dead pipeline.\n\nProposal: move 30% of SDR capacity to multi-thread within existing accounts. Projected $180K ARR in-quarter, no headcount change.\n\n30 min next Tuesday to align?" }],
      },
    },
    call_today: {
      headline: 'Call Priyanka at Basel today — deal is going cold',
      bullets: [
        '$96K opp, stage Proposal, no inbound from champion for 8 days.',
        'Champion opened the pricing page 3× last week but hasn\'t opened your last 3 emails.',
        'This is a champion-alignment risk, not a pricing risk — go direct.',
      ],
      action: {
        tag: 'Deal-risk save', urgency: 'high', value: '$96K opp',
        title: 'Direct outreach to Priyanka Rao (CRO, Basel)',
        why: 'Champion silent 8 days · pricing page opened 3× · no reply on last 3 emails.',
        drafts: [{ to: 'Priyanka Rao · CRO, Basel Systems', channel: 'Email',
          subject: 'Priyanka — anything I can unblock?',
          body: "Priyanka — I don't want to be the eighth follow-up. Two possibilities I can act on today:\n\n  a) Legal has questions and it's stuck on redlines — I can loop our GC in.\n  b) Priorities shifted — no ego, just tell me and I'll pull the redlines back.\n\nEither way I'd rather know than guess.\n\n— {{brand}}" }],
      },
    },
    ltv_lever: {
      headline: 'Renewal 90-day pre-work is your net-retention lever',
      bullets: [
        '4 renewals inside 90 days; 2 have usage growth > 40% — clean expansion setup.',
        'Historical: teams that ran the 90-day pre-conversation renewed at 96% vs 78% for reactive renewals.',
        'Zero net-new sales work. Pure retention.',
      ],
      action: {
        tag: 'Renewal', urgency: 'medium', value: '+$186K ARR retention',
        title: 'Run the 90-day pre-renewal conversation on 4 accounts',
        why: '4 renewals in 90d · 2 with usage growth > 40% (expansion setup).',
        drafts: [{ to: '4 renewal-window accounts', channel: 'Email · CS-led',
          subject: '90-day pre-renewal — no surprises',
          body: "Hi team — 90 days out from renewal so we can plan, not react. 20-min business review or async 1-pager — pick whichever costs you less time.\n\n— {{brand}}" }],
      },
    },
  },

  hybrid: {
    channel_waste: {
      headline: 'Trade shows at $780 CAC are your leak — Coffee Fest paid off, Roasters Expo didn\'t',
      bullets: [
        'Trade-show CAC is $780 — 35× your DTC Meta CAC.',
        'Coffee Fest converted 24 accounts in 7 days; Roasters Expo (higher cost) is at 6 in 42 days.',
        'Move Roasters Expo budget to sample-request Meta ads: projected +$14K/mo revenue.',
      ],
      action: {
        tag: 'Budget shift', urgency: 'medium', value: '+$14K/mo projected',
        title: 'Reallocate Roasters Expo budget to sample-request Meta ads',
        why: 'Roasters Expo: 6 accts in 42d. Coffee Fest: 24 accts in 7d. Meta sample-req CAC is $22.',
        drafts: [{ to: 'Marketing manager', channel: 'Internal',
          body: "Kill Roasters Expo attendance next year — 6 accts in 42 days at $780 CAC. Move the $18K to a sample-request Meta campaign (CAC $22). Projected +$14K/mo new revenue at same spend.",
        }],
      },
    },
    call_today: {
      headline: 'Call Ravi at Crema today — silent 12 days',
      bullets: [
        'Top-5 wholesale account, previous 7-day cadence.',
        'Last order on time; no reason in the ticket log.',
        'Historical: 12-day silences from top-5 accounts churn in 3 weeks 61% of the time.',
      ],
      action: {
        tag: 'Wholesale save', urgency: 'high', value: '$980/wk at risk',
        title: 'Founder-to-owner note to Ravi at Crema',
        why: 'Top-5 account · 12 days silent · silence-then-churn probability 61%.',
        drafts: [{ to: 'Ravi at Crema', channel: 'Email', subject: 'Ravi — Crema\'s house-blend queue is thin',
          body: "Ravi — quick check-in. Your Crema queue looks like it's running low on the 5-lb house blend. Two things:\n\n  1) Anything I need to fix on our side — a late delivery, a bag that came sealed wrong?\n  2) If it's just the roast profile you want to switch, our new Ethiopian is closer to a stone-fruit note.\n\nWant me to send a 1-lb sample today?\n\n— {{brand}}" }],
      },
    },
    ltv_lever: {
      headline: 'DTC subscription anchor is your #1 unit-economics unlock',
      bullets: [
        'First-order → subscription conversion is 38%, up 8 pts MoM.',
        'Subscribed customers have 3.4× the 12-month value of one-time buyers.',
        'Every DTC first-order that misses the anchor is $180 in future revenue you leave on the table.',
      ],
      action: {
        tag: 'DTC LTV', urgency: 'medium', value: '+$180 per first-order buyer',
        title: 'Route all first-time DTC buyers through the subscription anchor',
        why: 'Subscriber 12-mo value is 3.4× one-time. Anchor lift +8pt MoM.',
        drafts: [{ to: 'Growth engineer', channel: 'Internal',
          body: "Route every first-time DTC buyer through subscription anchor post-checkout (not just the 62% currently in the flow). Projected +$180 LTV per buyer at zero acquisition cost.",
        }],
      },
    },
  },
};

export const ASK_ARIA_QUESTIONS = [
  { id: 'channel_waste', label: 'Which channel is wasting money?' },
  { id: 'call_today',    label: 'Who should I call today?' },
  { id: 'ltv_lever',     label: 'What\'s my biggest LTV lever?' },
];

export function askAria(questionId, mode) {
  const set = A[mode] || A.b2c;
  return set[questionId] || null;
}
