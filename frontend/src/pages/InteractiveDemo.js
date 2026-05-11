/**
 * Interactive Demo — /demo
 *
 * Fully self-contained, no auth, no backend, all mock data.
 * 5 main scenes + 2 bonus scenes, dark Aria brand colours per spec.
 */
import React, { useEffect, useMemo, useRef, useState } from 'react';

// Dark theme palette (per spec)
const C = {
  bg: '#0d0d1a',
  surface: '#1a1a2e',
  primary: '#4f8ef7',
  gold: '#e2b96f',
  text: '#ffffff',
  textDim: '#a0a8c0',
  border: '#2a2a45',
  success: '#34d399',
  danger: '#f87171',
};

const SHARE_URL = 'https://app.genleadai.com/demo';
const SIGNUP_URL = 'https://app.genleadai.com/';

// ──────────────────────────────────────────────────────────────────────────
// Conversation scripts
// ──────────────────────────────────────────────────────────────────────────
const SCENE1_SCRIPT = [
  { role: 'lead', text: "Hi, I saw your Instagram ad about the growth marketing service. Can you tell me more?" },
  { role: 'aria', delay: 1500, text: "Hi Priya! 👋 I'm Aria, the sales assistant at GenLeadAI.\n\nThanks for reaching out — great to connect! Before I share details, mind if I ask a couple of quick questions so I can send you exactly what's relevant?" },
  { role: 'lead', text: "Sure, go ahead!" },
  { role: 'aria', delay: 1200, text: "Perfect! Are you looking for a solution for your own business, or on behalf of a client?" },
  { role: 'lead', text: "For my own business — I run a D2C skincare brand." },
  { role: 'aria', delay: 1500, text: "Love that! And roughly how many leads or orders are you currently handling per month? Even a ballpark works 😊" },
  { role: 'lead', text: "Around 200–300 inquiries a month, but our follow-up is all over the place." },
  { role: 'aria', delay: 1200, text: "That's exactly where we can help. One last thing — do you have a rough budget in mind, or still exploring options?" },
  { role: 'lead', text: "We have a budget, yes. Looking at solutions in the ₹10,000–20,000/month range." },
  { role: 'aria', delay: 2000, text: "This fits really well, Priya. You're in the right range for our Growth plan, which is designed for exactly your kind of volume.\n\nI'd love to get you on a quick 20-min call with our team this week. Would Wednesday or Thursday work better for you? 🗓️" },
];

const SCENE2_SCRIPT = [
  { sys: 'Yesterday' },
  { role: 'aria', text: "Hi Priya! Just following up from yesterday 😊 Did you get a chance to check if Wednesday or Thursday works for a quick call?" },
  { sys: 'Today · 9:14am' },
  { role: 'lead', text: "Sorry, been swamped! Thursday works actually. What time?" },
  { role: 'aria', delay: 1500, text: "No worries at all! How does 11am or 3pm Thursday work for you?" },
  { role: 'lead', text: "3pm works!" },
  { role: 'aria', delay: 1000, text: "Perfect — I've noted that down! 🎉 You'll receive a calendar invite from our team shortly.\n\nIn the meantime, here's a quick case study from a D2C brand similar to yours who 3x'd their follow-up rate using our system: aria.gen/case-d2c\n\nLooking forward to Thursday, Priya!" },
];

const SCENE4_SCRIPT = [
  { role: 'aria', text: "Hi Vikram! Just checking in — did you get a chance to review the proposal we sent last week? 😊" },
  { role: 'lead', text: "Honestly not impressed. The pricing doesn't make sense for what you're offering. I've seen better." },
  { alert: true },
  { role: 'aria', paused: true, text: "I hear you, Vikram. Let me get the right person from our team to address this directly — they'll be in touch very shortly." },
];

// Scene 1 — intelligence panel timeline
const SCENE1_PANEL_STEPS = [
  { afterMsgIdx: 0, classification: { layer: 3, decision: 'LEAD', confidence: 94, reason: 'Prospect referencing ad, asking about service' }, score: 20, scoreReasons: ['+20 Inbound inquiry (self-initiated)'] },
  { afterMsgIdx: 4, scoreDelta: 15, score: 35, scoreReasons: ['+20 Inbound inquiry', '+15 Decision-maker (own business)'] },
  { afterMsgIdx: 6, scoreDelta: 12, score: 47, scoreReasons: ['+20 Inbound inquiry', '+15 Decision-maker', '+12 Clear pain point stated'] },
  { afterMsgIdx: 8, scoreDelta: 25, score: 72, scoreReasons: ['+20 Inbound inquiry', '+15 Decision-maker', '+12 Pain point stated', '+15 Budget confirmed', '+10 D2C industry match'], qualified: ['need', 'decision', 'budget'] },
];

// ──────────────────────────────────────────────────────────────────────────
// Common UI primitives
// ──────────────────────────────────────────────────────────────────────────
const Bubble = ({ role, text, paused }) => {
  const isAria = role === 'aria';
  return (
    <div className={`flex ${isAria ? 'justify-start' : 'justify-end'} mb-2`}>
      <div
        className="max-w-[78%] px-3 py-2 text-[13px] leading-relaxed whitespace-pre-line"
        style={{
          background: isAria ? C.primary : '#2a3447',
          color: '#fff',
          borderRadius: isAria ? '14px 14px 14px 4px' : '14px 14px 4px 14px',
          opacity: paused ? 0.45 : 1,
          boxShadow: '0 2px 8px rgba(0,0,0,0.25)',
        }}
      >
        {text}
        {paused && <div className="mt-1 text-[10px] font-bold uppercase tracking-wider opacity-75">⏸ Paused</div>}
      </div>
    </div>
  );
};

const TypingIndicator = () => (
  <div className="flex justify-start mb-2">
    <div className="px-3 py-2.5 rounded-2xl rounded-bl-sm" style={{ background: C.primary }}>
      <div className="flex gap-1 items-center">
        {[0, 1, 2].map((i) => (
          <span key={i} className="w-1.5 h-1.5 bg-white rounded-full" style={{ animation: `aria-bounce 1.4s ease-in-out ${i * 0.2}s infinite` }}></span>
        ))}
      </div>
    </div>
  </div>
);

const PhoneFrame = ({ businessName = 'GenLeadAI', children }) => (
  <div className="mx-auto rounded-[40px] p-2 shadow-2xl" style={{ background: '#000', maxWidth: 380, border: `4px solid ${C.border}` }}>
    <div className="rounded-[32px] overflow-hidden" style={{ background: '#0b1422' }}>
      <div className="px-4 py-3 flex items-center gap-3" style={{ background: '#1f2c3d' }}>
        <div className="w-9 h-9 rounded-full flex items-center justify-center font-bold text-sm" style={{ background: C.primary }}>A</div>
        <div className="flex-1 min-w-0">
          <div className="text-white text-sm font-bold truncate" style={{ fontFamily: 'Inter' }}>{businessName}</div>
          <div className="text-[10px]" style={{ color: '#94a3b8' }}>+91 98XXX XXXXX · online</div>
        </div>
      </div>
      <div
        className="p-3 overflow-y-auto"
        style={{
          height: 480,
          background: 'linear-gradient(180deg, #0c1623 0%, #111c2a 100%)',
          backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='40' height='40' viewBox='0 0 40 40'%3E%3Cpath fill='%23ffffff05' d='M0 0h2v2H0zM20 20h2v2h-2z'/%3E%3C/svg%3E\")",
        }}
      >
        {children}
      </div>
    </div>
  </div>
);

const PanelCard = ({ title, icon, children, accent = C.primary }) => (
  <div
    className="rounded-xl p-4 mb-3"
    style={{ background: 'rgba(255,255,255,0.03)', border: `1px solid ${C.border}`, backdropFilter: 'blur(8px)' }}
  >
    <div className="flex items-center gap-2 mb-3 text-xs font-bold uppercase tracking-[0.18em]" style={{ color: accent, fontFamily: 'Inter' }}>
      {icon} {title}
    </div>
    {children}
  </div>
);

// ──────────────────────────────────────────────────────────────────────────
// Hook: progressive conversation player
// ──────────────────────────────────────────────────────────────────────────
function useConversationPlayer(script, autoStart = true) {
  const [visible, setVisible] = useState(0);
  const [typing, setTyping] = useState(false);
  const timer = useRef(null);

  useEffect(() => {
    if (!autoStart) return;
    setVisible(0);
    let i = 0;
    const tick = () => {
      if (i >= script.length) return;
      const msg = script[i];
      if (msg.sys || msg.alert) {
        setVisible((v) => i + 1); i++;
        timer.current = setTimeout(tick, 600);
        return;
      }
      if (msg.role === 'aria' && !msg.paused) {
        setTyping(true);
        timer.current = setTimeout(() => {
          setTyping(false);
          setVisible(i + 1);
          i++;
          timer.current = setTimeout(tick, 900);
        }, msg.delay || 1500);
      } else {
        setVisible(i + 1); i++;
        timer.current = setTimeout(tick, msg.role === 'lead' ? 1200 : 700);
      }
    };
    timer.current = setTimeout(tick, 400);
    return () => clearTimeout(timer.current);
  }, [autoStart, script]);

  return { visible, typing };
}

// ──────────────────────────────────────────────────────────────────────────
// Scenes
// ──────────────────────────────────────────────────────────────────────────
const SceneTitle = ({ children }) => (
  <div className="mb-5 p-4 rounded-xl" style={{ background: 'rgba(79,142,247,0.08)', border: `1px solid ${C.primary}33` }}>
    <p className="text-base md:text-lg leading-relaxed" style={{ color: C.text, fontFamily: 'Inter' }}>{children}</p>
  </div>
);

const Scene1 = () => {
  const { visible, typing } = useConversationPlayer(SCENE1_SCRIPT);
  const messages = SCENE1_SCRIPT.slice(0, visible);

  const panelState = useMemo(() => {
    let s = null;
    for (const step of SCENE1_PANEL_STEPS) {
      if (visible - 1 >= step.afterMsgIdx) s = step;
    }
    return s;
  }, [visible]);

  return (
    <div data-testid="demo-scene-1">
      <SceneTitle>🔔 A new lead just messaged your WhatsApp Business number. Watch how Aria identifies, classifies, and responds — in real time.</SceneTitle>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <PhoneFrame>
          {messages.map((m, i) => m.sys || m.alert ? null : <Bubble key={i} role={m.role} text={m.text} />)}
          {typing && <TypingIndicator />}
        </PhoneFrame>
        <div data-testid="scene1-intel">
          <PanelCard title="Lead Classification" icon={<span>🧠</span>}>
            <div className="space-y-1.5 text-xs" style={{ color: C.textDim }}>
              <div>Layer 1: <span style={{ color: C.text }}>No trigger phrase match</span></div>
              <div>Layer 2: <span style={{ color: C.text }}>Unknown number — not in contacts</span></div>
              <div>Layer 3: <span style={{ color: C.success }}>AI Classification → LEAD ✅</span></div>
              {panelState && (
                <>
                  <div className="pt-1.5 mt-1.5 border-t" style={{ borderColor: C.border }}>
                    Confidence: <span style={{ color: C.success, fontWeight: 700 }}>{panelState.classification?.confidence || 94}%</span>
                  </div>
                  <div className="italic" style={{ color: C.textDim, fontSize: 11 }}>"{panelState.classification?.reason || 'Prospect referencing ad'}"</div>
                </>
              )}
            </div>
          </PanelCard>

          <PanelCard title="Live Lead Score" icon={<span>📊</span>}>
            <div className="flex items-baseline gap-2 mb-2">
              <span className="text-3xl font-extrabold" style={{ color: C.gold, fontFamily: 'Inter' }}>{panelState?.score || 0}</span>
              <span className="text-xs" style={{ color: C.textDim }}>/ 100</span>
            </div>
            <div className="h-2 rounded-full overflow-hidden mb-2" style={{ background: C.border }}>
              <div className="h-full rounded-full transition-all duration-700" style={{ width: `${panelState?.score || 0}%`, background: `linear-gradient(90deg, ${C.primary}, ${C.gold})` }}></div>
            </div>
            {(panelState?.scoreReasons || []).map((r, i) => (
              <div key={i} className="text-[11px] py-0.5" style={{ color: C.textDim }}>{r}</div>
            ))}
          </PanelCard>

          <PanelCard title="Qualification Criteria" icon={<span>✓</span>}>
            <div className="space-y-1.5 text-xs">
              {[
                { key: 'need', label: 'Need identified' },
                { key: 'decision', label: 'Decision-maker confirmed' },
                { key: 'budget', label: 'Budget in range' },
                { key: 'timeline', label: 'Timeline not yet confirmed' },
              ].map((q) => {
                const met = (panelState?.qualified || []).includes(q.key);
                return (
                  <div key={q.key} style={{ color: met ? C.success : C.textDim }}>{met ? '✅' : '⏳'} {q.label}</div>
                );
              })}
            </div>
          </PanelCard>

          <PanelCard title="Touchpoint Status" icon={<span>🔄</span>}>
            <div className="text-xs" style={{ color: C.textDim }}>
              Journey: <span style={{ color: C.text, fontWeight: 600 }}>Warm Nurture Template</span><br />
              Touchpoint 1 of 6 · In progress<br />
              Next: Follow-up in 24hrs if no reply
            </div>
          </PanelCard>

          <p className="text-xs italic mt-3" style={{ color: C.textDim }}>Aria determined this is a genuine lead in 0.8 seconds — before sending a single word.</p>
        </div>
      </div>
    </div>
  );
};

const Scene2 = () => {
  const { visible, typing } = useConversationPlayer(SCENE2_SCRIPT);
  const messages = SCENE2_SCRIPT.slice(0, visible);
  return (
    <div data-testid="demo-scene-2">
      <SceneTitle>Priya responded. She's interested but needs a nudge. Aria picks up the conversation exactly where it left off — 18 hours later.</SceneTitle>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <PhoneFrame>
          {/* Greyed previous convo summary */}
          <div className="mb-3 p-2 rounded-lg text-center text-[10px]" style={{ background: '#0a1320', color: '#637184', border: `1px dashed ${C.border}` }}>
            ← scrolled-up: yesterday's qualification chat (5 messages)
          </div>
          {messages.map((m, i) => {
            if (m.sys) return <div key={i} className="text-center my-2 text-[10px] font-bold tracking-wider" style={{ color: '#7b8aa3' }}>{m.sys}</div>;
            return <Bubble key={i} role={m.role} text={m.text} />;
          })}
          {typing && <TypingIndicator />}
        </PhoneFrame>

        <div data-testid="scene2-panel">
          <PanelCard title="Touchpoint Log" icon={<span>📍</span>}>
            <div className="space-y-1.5 text-[11px] font-mono">
              {[
                ['TP-01', 'Day 0 · Instant', 'sent', 'Hi Priya! I\'m Aria...'],
                ['TP-02', 'Day 1 · 9am', 'sent', 'Just following up...'],
                ['TP-03', 'Day 3 · Value Drop', 'scheduled', ''],
                ['TP-04', 'Day 7 · Re-engage', 'scheduled', ''],
                ['TP-05', 'Day 10 · CTA', 'scheduled', ''],
                ['TP-06', 'Day 14 · Final', 'scheduled', ''],
              ].map(([id, when, status, prev]) => (
                <div key={id} className="flex items-center gap-2">
                  <span style={{ color: C.textDim, width: 56 }}>{id}</span>
                  <span style={{ color: C.textDim, width: 100 }}>{when}</span>
                  <span style={{ color: status === 'sent' ? C.success : C.gold }}>{status === 'sent' ? '✅ Sent' : '⏳ Scheduled'}</span>
                  {prev && <span style={{ color: C.textDim, fontSize: 10 }} className="truncate">"{prev}"</span>}
                </div>
              ))}
            </div>
          </PanelCard>

          <PanelCard title="Lead Stage Updated" icon={<span>🚀</span>}>
            <div className="flex items-center gap-2 text-[11px] flex-wrap">
              {['New Lead', 'Contacted', 'Qualified', 'Meeting Booked'].map((s, i) => (
                <React.Fragment key={s}>
                  <span className={i === 3 ? 'animate-pulse' : ''} style={{
                    color: i <= 3 ? C.text : C.textDim,
                    background: i === 3 ? C.gold + '22' : 'transparent',
                    border: `1px solid ${i === 3 ? C.gold : C.border}`,
                    padding: '4px 10px', borderRadius: 6, fontWeight: i === 3 ? 800 : 500,
                  }}>{s}{i === 3 ? ' ✅' : ''}</span>
                  {i < 3 && <span style={{ color: C.textDim }}>→</span>}
                </React.Fragment>
              ))}
            </div>
            <p className="text-[10px] mt-2" style={{ color: C.gold }}>↑ just now</p>
          </PanelCard>

          <PanelCard title="Meeting Booked" icon={<span>🗓️</span>} accent={C.gold}>
            <div className="text-xs space-y-1" style={{ color: C.textDim }}>
              <div>Contact: <span style={{ color: C.text, fontWeight: 700 }}>Priya Sharma</span></div>
              <div>Date: <span style={{ color: C.text }}>Thursday · 3:00 PM</span></div>
              <div>Assigned to: <span style={{ color: C.text }}>Megha (Owner)</span></div>
              <div>Source: Instagram Ad · Warm Nurture TP-02</div>
              <div className="pt-1.5 mt-1.5 border-t" style={{ borderColor: C.border, color: C.gold }}>⏱ First message → booked: <strong>26 hours</strong></div>
            </div>
          </PanelCard>

          <PanelCard title="CRM Sync" icon={<span>🔗</span>} accent={C.success}>
            <div className="text-xs" style={{ color: C.success }}>🟢 Synced to HubSpot · just now</div>
            <div className="text-[11px] mt-1" style={{ color: C.textDim }}>Contact created · Deal created · Meeting logged</div>
          </PanelCard>
        </div>
      </div>
    </div>
  );
};

// ──────────────────────────────────────────────────────────────────────────
// Scene 3 — Dashboard mock with 4 tabs
// ──────────────────────────────────────────────────────────────────────────
const KPI = ({ label, value, delta, deltaSign = 'up' }) => (
  <div className="rounded-xl p-4" style={{ background: C.surface, border: `1px solid ${C.border}` }}>
    <div className="text-[10px] uppercase tracking-[0.15em] font-bold mb-2" style={{ color: C.textDim }}>{label}</div>
    <div className="flex items-baseline gap-2">
      <span className="text-3xl font-extrabold" style={{ color: C.text, fontFamily: 'Inter' }}>{value}</span>
      <span className="text-xs font-bold" style={{ color: deltaSign === 'up' ? C.success : C.danger }}>{deltaSign === 'up' ? '▲' : '▼'} {delta}</span>
    </div>
  </div>
);

const ActivityFeed = () => {
  const items = [
    { dot: C.success, name: 'Priya Sharma', text: 'Meeting booked · 3pm Thursday', when: '2 min ago' },
    { dot: C.gold, name: 'Rahul Mehta', text: 'Awaiting budget confirmation', when: '1 hr ago' },
    { dot: '#94a3b8', name: 'Sneha Kapoor', text: 'Intro sent', when: '3 hrs ago' },
    { dot: C.danger, name: 'Vikram Joshi', text: 'Negative sentiment flagged', when: '4 hrs ago' },
    { dot: C.success, name: 'Anita Roy', text: 'Qualified · Score 84', when: '6 hrs ago' },
    { dot: '#94a3b8', name: 'Dev Sharma', text: 'Re-engagement sent', when: 'Yesterday' },
  ];
  return (
    <div className="rounded-xl p-4" style={{ background: C.surface, border: `1px solid ${C.border}` }} data-testid="activity-feed">
      <div className="text-xs uppercase tracking-[0.15em] font-bold mb-3" style={{ color: C.gold }}>Activity Feed</div>
      <div className="space-y-2">
        {items.map((it, i) => (
          <div key={i} className="flex items-center gap-2 text-xs py-1.5 border-b last:border-0" style={{ borderColor: C.border, color: C.textDim }}>
            <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: it.dot }}></span>
            <span className="font-bold" style={{ color: C.text }}>{it.name}</span>
            <span className="flex-1 truncate">{it.text}</span>
            <span className="flex-shrink-0">{it.when}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

const PipelineHealthGauge = () => (
  <div className="rounded-xl p-4" style={{ background: C.surface, border: `1px solid ${C.border}` }}>
    <div className="text-xs uppercase tracking-[0.15em] font-bold mb-3" style={{ color: C.success }}>Pipeline Health</div>
    <div className="flex items-center gap-4">
      <div className="relative">
        <svg width="84" height="84" viewBox="0 0 84 84">
          <circle cx="42" cy="42" r="34" fill="none" stroke={C.border} strokeWidth="8" />
          <circle cx="42" cy="42" r="34" fill="none" stroke={C.success} strokeWidth="8" strokeLinecap="round"
            strokeDasharray={`${(81 / 100) * 2 * Math.PI * 34} ${2 * Math.PI * 34}`} transform="rotate(-90 42 42)" />
          <text x="42" y="46" textAnchor="middle" fontSize="22" fontWeight="800" fill={C.text} fontFamily="Inter">81</text>
        </svg>
      </div>
      <div className="flex-1">
        <div className="text-sm font-extrabold" style={{ color: C.success }}>🟢 Healthy</div>
        <div className="text-[11px] mt-1" style={{ color: C.textDim }}>Above industry benchmark for D2C SaaS at this stage.</div>
      </div>
    </div>
  </div>
);

const KanbanColumn = ({ title, count, cards, accent }) => (
  <div className="flex-1 min-w-[180px] rounded-xl p-3" style={{ background: C.bg, border: `1px solid ${C.border}` }}>
    <div className="flex items-center justify-between mb-3">
      <span className="text-[10px] uppercase tracking-[0.15em] font-bold" style={{ color: accent }}>{title}</span>
      <span className="text-[10px] font-mono" style={{ color: C.textDim }}>{count}</span>
    </div>
    <div className="space-y-2">
      {cards.map((c, i) => (
        <button key={i} type="button" className="w-full text-left rounded-lg p-2.5 hover:scale-[1.02] transition-transform" style={{ background: C.surface, border: `1px solid ${C.border}` }}>
          <div className="text-xs font-bold" style={{ color: C.text }}>{c.name}</div>
          <div className="text-[10px] mt-0.5" style={{ color: C.textDim }}>{c.tag}</div>
          <div className="text-[10px] mt-1.5 font-mono" style={{ color: c.scoreColor || C.gold }}>{c.meta}</div>
        </button>
      ))}
    </div>
  </div>
);

const Scene3Dashboard = () => (
  <div className="space-y-4" data-testid="scene3-home">
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      <KPI label="Active Leads" value="47" delta="12%" />
      <KPI label="Conversations Today" value="23" delta="8%" />
      <KPI label="Qualified This Week" value="11" delta="34%" />
      <KPI label="Meetings Booked" value="6" delta="20%" />
    </div>
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
      <PipelineHealthGauge />
      <div className="rounded-xl p-4" style={{ background: 'linear-gradient(135deg, #1c1f3a 0%, #1a1a2e 100%)', border: `1px solid ${C.gold}44` }}>
        <div className="text-xs uppercase tracking-[0.15em] font-bold mb-2" style={{ color: C.gold }}>Aria's Impact This Month</div>
        <div className="text-xs leading-relaxed" style={{ color: C.text }}>
          Aria handled <strong>143 conversations</strong> · Qualified <strong>31 leads</strong> · Saved your team an estimated <strong style={{ color: C.gold }}>19 hours</strong>.
        </div>
      </div>
      <div className="rounded-xl p-4" style={{ background: C.surface, border: `1px solid ${C.border}` }}>
        <div className="text-xs uppercase tracking-[0.15em] font-bold mb-2" style={{ color: C.success }}>Aria Status</div>
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full animate-pulse" style={{ background: C.success }}></span>
          <span className="text-sm font-bold" style={{ color: C.text }}>Active</span>
          <div className="ml-auto w-10 h-5 rounded-full relative" style={{ background: C.success }}>
            <span className="absolute top-0.5 right-0.5 w-4 h-4 rounded-full bg-white"></span>
          </div>
        </div>
        <p className="text-[11px] mt-2" style={{ color: C.textDim }}>Pause anytime — your sequences hold their state.</p>
      </div>
    </div>
    <ActivityFeed />
  </div>
);

const Scene3Pipeline = () => (
  <div className="overflow-x-auto" data-testid="scene3-pipeline">
    <div className="flex gap-3 pb-2" style={{ minWidth: 1000 }}>
      <KanbanColumn title="NEW LEAD" count="8" accent={C.primary} cards={[
        { name: 'Priya S.', tag: 'D2C Skincare', meta: 'Score: 72 🟢' },
        { name: 'Dev S.', tag: 'Consulting', meta: 'Score: 41 ⚪' },
      ]} />
      <KanbanColumn title="CONTACTED" count="12" accent={C.primary} cards={[
        { name: 'Rahul M.', tag: 'SaaS Startup', meta: 'Score: 58 🟡' },
        { name: 'Pooja K.', tag: 'E-commerce', meta: 'Score: 63 🟡' },
      ]} />
      <KanbanColumn title="QUALIFIED" count="11" accent={C.gold} cards={[
        { name: 'Anita R.', tag: 'Healthcare', meta: 'Score: 84 🟢' },
        { name: 'Ravi N.', tag: 'Finance', meta: 'Score: 79 🟢' },
      ]} />
      <KanbanColumn title="MEETING BOOKED" count="6" accent={C.gold} cards={[
        { name: 'Karan P.', tag: 'Real Estate', meta: '₹15K/mo' },
        { name: 'Sunita M.', tag: 'Consulting', meta: '₹25K/mo' },
      ]} />
      <KanbanColumn title="CLOSED WON" count="4" accent={C.success} cards={[
        { name: 'Meera T.', tag: 'E-commerce', meta: '₹12K/mo ✅' },
        { name: 'Aditya R.', tag: 'SaaS', meta: '₹8K/mo ✅' },
      ]} />
    </div>
  </div>
);

const Scene3Conversations = () => {
  const threads = [
    { name: 'Priya Sharma', co: 'D2C Skincare', msg: "Looking forward to Thursday, Priya!", when: '2m', dot: C.success },
    { name: 'Rahul Mehta', co: 'SaaS Startup', msg: "Sure, let me check with my co-founder…", when: '1h', dot: C.gold },
    { name: 'Anita Roy', co: 'Healthcare', msg: "Yes, please share the proposal", when: '3h', dot: C.success },
    { name: 'Vikram Joshi', co: 'Manufacturing', msg: "Pricing doesn't make sense for what you're offering.", when: '4h', dot: C.danger },
    { name: 'Sneha Kapoor', co: 'D2C Fashion', msg: "Got it, will revert tomorrow", when: '6h', dot: '#94a3b8' },
    { name: 'Karan Patel', co: 'Real Estate', msg: "Calendar invite received — see you then", when: '8h', dot: C.success },
    { name: 'Dev Sharma', co: 'Consulting', msg: "Hi, what does your tool actually do?", when: '1d', dot: '#94a3b8' },
    { name: 'Aditya Roy', co: 'SaaS', msg: "Wire transferred. Onboarding pls.", when: '2d', dot: C.success },
  ];
  return (
    <div className="rounded-xl overflow-hidden" style={{ background: C.surface, border: `1px solid ${C.border}` }} data-testid="scene3-conversations">
      {threads.map((t, i) => (
        <div key={i} className={`px-4 py-3 flex items-center gap-3 ${i < threads.length - 1 ? 'border-b' : ''}`} style={{ borderColor: C.border }}>
          <div className="w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold" style={{ background: C.primary, color: '#fff' }}>{t.name[0]}</div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold" style={{ color: C.text }}>{t.name}</span>
              <span className="text-[10px]" style={{ color: C.textDim }}>· {t.co}</span>
            </div>
            <div className="text-xs truncate mt-0.5" style={{ color: C.textDim }}>{t.msg}</div>
          </div>
          <span className="w-2 h-2 rounded-full" style={{ background: t.dot }}></span>
          <span className="text-[10px] font-mono w-8 text-right" style={{ color: C.textDim }}>{t.when}</span>
        </div>
      ))}
    </div>
  );
};

const Scene3Leads = () => {
  const [q, setQ] = useState('');
  const all = [
    ['Priya Sharma', 'Instagram Ads', 'Meeting Booked', '🟢', 72],
    ['Rahul Mehta', 'Referral', 'Contacted', '🟡', 58],
    ['Anita Roy', 'Website Form', 'Qualified', '🟢', 84],
    ['Vikram Joshi', 'Saleshandy', 'Contacted', '🔴', 43],
    ['Sneha Kapoor', 'Lemlist', 'Contacted', '⚪', 51],
    ['Karan Patel', 'Instagram Ads', 'Meeting Booked', '🟢', 78],
    ['Sunita Menon', 'Referral', 'Meeting Booked', '🟢', 81],
    ['Dev Sharma', 'Website Form', 'New Lead', '⚪', 41],
    ['Ravi Nair', 'Instagram Ads', 'Qualified', '🟢', 79],
    ['Pooja Kashyap', 'Saleshandy', 'Contacted', '🟡', 63],
    ['Aditya Roy', 'Referral', 'Closed Won', '🟢', 88],
    ['Meera T.', 'Website Form', 'Closed Won', '🟢', 86],
  ];
  const rows = all.filter((r) => !q || r[0].toLowerCase().includes(q.toLowerCase()));
  return (
    <div data-testid="scene3-leads">
      <div className="flex items-center gap-2 mb-3">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search leads…"
          className="flex-1 px-3 py-2 text-sm rounded-lg" style={{ background: C.surface, border: `1px solid ${C.border}`, color: C.text }} />
        <button className="px-3 py-2 text-xs font-bold rounded-lg" style={{ background: C.surface, border: `1px solid ${C.border}`, color: C.textDim }}>Filter ▾</button>
      </div>
      <div className="rounded-xl overflow-hidden" style={{ background: C.surface, border: `1px solid ${C.border}` }}>
        <table className="w-full text-xs">
          <thead style={{ background: '#0f0f24' }}>
            <tr>{['Name', 'Source', 'Stage', 'Sentiment', 'Score', 'Opt-in', 'CRM'].map((h) => (
              <th key={h} className="px-3 py-2 text-left text-[10px] uppercase tracking-wider font-bold" style={{ color: C.textDim }}>{h}</th>
            ))}</tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-t" style={{ borderColor: C.border }}>
                <td className="px-3 py-2 font-bold" style={{ color: C.text }}>{r[0]}</td>
                <td className="px-3 py-2" style={{ color: C.textDim }}>{r[1]}</td>
                <td className="px-3 py-2" style={{ color: C.text }}>{r[2]}</td>
                <td className="px-3 py-2">{r[3]}</td>
                <td className="px-3 py-2 font-mono font-bold" style={{ color: C.gold }}>{r[4]}</td>
                <td className="px-3 py-2">🟢</td>
                <td className="px-3 py-2">🟢</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

const Scene3 = () => {
  const [tab, setTab] = useState('home');
  const tabs = [
    { id: 'home', label: 'Dashboard' },
    { id: 'pipeline', label: 'Pipeline' },
    { id: 'conversations', label: 'Conversations' },
    { id: 'leads', label: 'Leads' },
  ];
  return (
    <div data-testid="demo-scene-3">
      <SceneTitle>This is your command centre. Every lead Aria is managing — visible in one place.</SceneTitle>
      <div className="flex items-center gap-1 mb-4 overflow-x-auto" data-testid="scene3-tabs">
        {tabs.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)} data-testid={`tab-${t.id}`}
            className="px-3 py-2 text-xs font-bold rounded-lg whitespace-nowrap transition-all"
            style={{
              background: tab === t.id ? C.primary : 'transparent',
              color: tab === t.id ? '#fff' : C.textDim,
              border: `1px solid ${tab === t.id ? C.primary : C.border}`,
              fontFamily: 'Inter',
            }}>
            {t.label}
          </button>
        ))}
      </div>
      {tab === 'home' && <Scene3Dashboard />}
      {tab === 'pipeline' && <Scene3Pipeline />}
      {tab === 'conversations' && <Scene3Conversations />}
      {tab === 'leads' && <Scene3Leads />}

      <div className="mt-4 p-3 rounded-lg text-center text-xs" style={{ background: C.gold + '15', border: `1px solid ${C.gold}55`, color: C.gold }}>
        ✦ This is realistic mock data. Click any tab to explore.
      </div>
    </div>
  );
};

// ──────────────────────────────────────────────────────────────────────────
// Scene 4 — Human Takeover
// ──────────────────────────────────────────────────────────────────────────
const Scene4 = () => {
  const { visible } = useConversationPlayer(SCENE4_SCRIPT);
  const messages = SCENE4_SCRIPT.slice(0, visible);
  const [taken, setTaken] = useState(false);
  const [reply, setReply] = useState('');
  const [sent, setSent] = useState(null);
  const [resumed, setResumed] = useState(false);

  const sendReply = () => {
    if (!reply.trim()) return;
    setSent(reply.trim());
    setReply('');
  };

  return (
    <div data-testid="demo-scene-4">
      <SceneTitle>Vikram Joshi is frustrated. Aria detected it — and flagged him immediately. Your rep steps in with one click.</SceneTitle>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <PhoneFrame businessName="Vikram Joshi · Manufacturing">
          {messages.map((m, i) => {
            if (m.alert) return (
              <div key={i} className="my-2 mx-1 p-2 rounded-md text-[11px] text-center font-bold" style={{ background: C.danger + '20', border: `1px solid ${C.danger}55`, color: C.danger }}>
                ⚠️ Negative sentiment detected · Aria pausing for human review
              </div>
            );
            return <Bubble key={i} role={m.role} text={m.text} paused={m.paused} />;
          })}
          {visible >= SCENE4_SCRIPT.length && (
            <div className="my-2 text-center text-[11px] font-bold" style={{ color: C.danger }}>🔴 Aria paused · Waiting for human</div>
          )}
          {sent && (
            <>
              <Bubble role="rep" text={sent} />
              <div className="text-[10px] text-right pr-1" style={{ color: C.textDim }}>Sent by you · just now</div>
            </>
          )}
          {resumed && (
            <div className="my-2 p-2 text-center text-[11px] font-bold rounded-md" style={{ background: C.primary + '20', border: `1px solid ${C.primary}55`, color: C.primary }}>
              ✦ Aria is back. Next touchpoint resumes tomorrow.
            </div>
          )}
        </PhoneFrame>

        <div data-testid="scene4-takeover">
          {!taken ? (
            <PanelCard title="Attention Required" icon={<span>🔴</span>} accent={C.danger}>
              <div className="space-y-1.5 text-xs" style={{ color: C.textDim }}>
                <div>Contact: <span style={{ color: C.text, fontWeight: 700 }}>Vikram Joshi</span></div>
                <div>Sentiment: <span style={{ color: C.danger, fontWeight: 700 }}>Negative</span></div>
                <div>Last message: <span style={{ color: C.text }} className="italic">"pricing doesn't make sense..."</span></div>
                <div>Aria confidence: <span style={{ color: C.danger, fontWeight: 700 }}>43%</span> (below threshold)</div>
                <div>Recommended action: <span style={{ color: C.gold, fontWeight: 700 }}>Human takeover</span></div>
              </div>
              <button onClick={() => setTaken(true)} data-testid="take-over-btn"
                className="mt-4 w-full py-2.5 rounded-lg text-sm font-bold transition-all hover:opacity-90"
                style={{ background: C.primary, color: '#fff', fontFamily: 'Inter' }}>
                Take Over Conversation
              </button>
            </PanelCard>
          ) : (
            <PanelCard title="You've Taken Over" icon={<span>✅</span>} accent={C.success}>
              <div className="p-2.5 rounded-md mb-3 text-xs" style={{ background: C.success + '20', color: C.success, border: `1px solid ${C.success}55` }}>
                Aria has stepped aside. This conversation is now yours.
              </div>
              <div className="text-xs" style={{ color: C.textDim }}>
                <div className="mb-2 p-2 rounded" style={{ background: C.surface, border: `1px solid ${C.border}` }}>
                  🟢 <strong style={{ color: C.text }}>HubSpot updated</strong> · Deal owner: <strong style={{ color: C.text }}>You</strong> · Note logged
                </div>
              </div>
              {!sent ? (
                <div className="mt-3">
                  <label className="text-[10px] uppercase tracking-wider font-bold" style={{ color: C.textDim }}>Your reply</label>
                  <textarea
                    rows={3}
                    value={reply}
                    onChange={(e) => setReply(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) sendReply(); }}
                    placeholder="Type your reply as Vikram's rep…"
                    data-testid="rep-reply-input"
                    className="w-full mt-1 px-3 py-2 text-sm rounded-md"
                    style={{ background: C.bg, border: `1px solid ${C.border}`, color: C.text }}
                  />
                  <button onClick={sendReply} disabled={!reply.trim()} data-testid="rep-send-btn"
                    className="mt-2 w-full py-2 rounded-lg text-sm font-bold disabled:opacity-40"
                    style={{ background: C.gold, color: '#000', fontFamily: 'Inter' }}>
                    Send reply
                  </button>
                </div>
              ) : !resumed && (
                <button onClick={() => setResumed(true)} data-testid="hand-back-btn"
                  className="mt-3 w-full py-2 rounded-lg text-sm font-bold"
                  style={{ background: 'transparent', color: C.primary, border: `1px solid ${C.primary}55` }}>
                  Hand back to Aria →
                </button>
              )}
            </PanelCard>
          )}

          <div className="mt-3 p-4 rounded-xl" style={{ background: C.surface, border: `1px solid ${C.gold}33` }}>
            <p className="text-sm leading-relaxed" style={{ color: C.text }}>
              <strong style={{ color: C.gold }}>💡 Aria doesn't just pause — she briefs your rep first.</strong>
            </p>
            <p className="text-xs mt-2 leading-relaxed" style={{ color: C.textDim }}>
              Every takeover includes the full conversation history, lead score, qualification status, and last 3 messages — already in HubSpot before your rep opens their laptop.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

// ──────────────────────────────────────────────────────────────────────────
// Scene 5 — Reports & ROI
// ──────────────────────────────────────────────────────────────────────────
function useCountUp(target, duration = 1500) {
  const [val, setVal] = useState(0);
  useEffect(() => {
    const start = Date.now();
    const id = setInterval(() => {
      const t = Math.min(1, (Date.now() - start) / duration);
      setVal(Math.round(target * (1 - Math.pow(1 - t, 3))));
      if (t >= 1) clearInterval(id);
    }, 50);
    return () => clearInterval(id);
  }, [target, duration]);
  return val;
}

const AnimatedKPI = ({ label, target, suffix = '', sub = '' }) => {
  const v = useCountUp(target);
  return (
    <div className="rounded-xl p-4" style={{ background: C.surface, border: `1px solid ${C.border}` }}>
      <div className="text-[10px] uppercase tracking-[0.15em] font-bold mb-2" style={{ color: C.textDim }}>{label}</div>
      <div className="text-3xl font-extrabold" style={{ color: C.gold, fontFamily: 'Inter' }}>{v}{suffix}</div>
      {sub && <div className="text-xs mt-1" style={{ color: C.textDim }}>{sub}</div>}
    </div>
  );
};

const Funnel = () => {
  const stages = [
    ['Leads entered', 143, null],
    ['Aria contacted', 118, 17.5],
    ['Replied', 89, 24.6],
    ['Qualified', 31, 65.2],
    ['Meeting booked', 18, 41.9],
    ['Closed Won', 7, 61.1],
  ];
  const max = stages[0][1];
  return (
    <div className="rounded-xl p-4" style={{ background: C.surface, border: `1px solid ${C.border}` }} data-testid="scene5-funnel">
      <div className="text-xs uppercase tracking-[0.15em] font-bold mb-3" style={{ color: C.primary }}>Pipeline Funnel</div>
      <div className="space-y-1.5">
        {stages.map(([label, val, drop], i) => {
          const w = (val / max) * 100;
          return (
            <div key={label} className="flex items-center gap-3 text-xs">
              <span className="w-32 flex-shrink-0" style={{ color: C.textDim }}>{label}</span>
              <div className="flex-1 h-8 rounded-md relative overflow-hidden" style={{ background: C.bg }}>
                <div className="h-full rounded-md flex items-center px-2 transition-all" style={{ width: `${Math.max(8, w)}%`, background: `linear-gradient(90deg, ${C.primary} ${100 - i * 10}%, ${C.gold})` }}>
                  <span className="text-white font-extrabold text-xs">{val}</span>
                </div>
              </div>
              {drop !== null && <span className="w-14 flex-shrink-0 text-right text-[10px] font-bold" style={{ color: C.danger }}>-{drop}%</span>}
            </div>
          );
        })}
      </div>
    </div>
  );
};

const TouchpointPie = () => {
  const total = 312 + 28 + 3;
  const sent = (312 / total) * 360;
  const skipped = (28 / total) * 360;
  return (
    <div className="rounded-xl p-4 flex items-center gap-4" style={{ background: C.surface, border: `1px solid ${C.border}` }} data-testid="scene5-touchpoints">
      <div className="relative w-32 h-32 flex-shrink-0">
        <div className="absolute inset-0 rounded-full" style={{ background: `conic-gradient(${C.success} 0deg ${sent}deg, ${C.gold} ${sent}deg ${sent + skipped}deg, ${C.danger} ${sent + skipped}deg 360deg)` }}></div>
        <div className="absolute inset-3 rounded-full flex items-center justify-center" style={{ background: C.surface }}>
          <span className="text-xl font-extrabold" style={{ color: C.text, fontFamily: 'Inter' }}>{total}</span>
        </div>
      </div>
      <div className="space-y-1.5 text-xs">
        <div className="text-[10px] uppercase tracking-wider font-bold mb-1" style={{ color: C.primary }}>Touchpoints</div>
        <div className="flex items-center gap-2"><span className="w-2 h-2 rounded-full" style={{ background: C.success }}></span><span style={{ color: C.text }}>Sent</span><span className="ml-auto font-mono" style={{ color: C.textDim }}>312</span></div>
        <div className="flex items-center gap-2"><span className="w-2 h-2 rounded-full" style={{ background: C.gold }}></span><span style={{ color: C.text }}>Skipped</span><span className="ml-auto font-mono" style={{ color: C.textDim }}>28</span></div>
        <div className="flex items-center gap-2"><span className="w-2 h-2 rounded-full" style={{ background: C.danger }}></span><span style={{ color: C.text }}>Failed</span><span className="ml-auto font-mono" style={{ color: C.textDim }}>3</span></div>
      </div>
    </div>
  );
};

const ConversationsByDay = () => {
  const heights = [35, 50, 80, 45, 60, 30, 25, 70, 90, 55, 65, 75, 40, 30, 50, 85, 70, 60, 80, 45, 55, 65, 50, 75, 100, 60, 70, 45, 80, 90];
  return (
    <div className="rounded-xl p-4" style={{ background: C.surface, border: `1px solid ${C.border}` }} data-testid="scene5-daily">
      <div className="text-xs uppercase tracking-[0.15em] font-bold mb-3" style={{ color: C.primary }}>Conversations · Last 30 days</div>
      <div className="flex items-end gap-1 h-32">
        {heights.map((h, i) => (
          <div key={i} className="flex-1 rounded-sm transition-all hover:opacity-80" style={{ background: `linear-gradient(180deg, ${C.primary}, ${C.primary}88)`, height: `${h}%` }} title={`Day ${i + 1}: ${Math.round(h * 0.4)} conversations`}></div>
        ))}
      </div>
    </div>
  );
};

const SourceTable = () => {
  const rows = [
    ['Instagram Ads', 52, 14, '26.9%', '3.1d'],
    ['Referral', 18, 9, '50%', '1.4d'],
    ['Website Form', 31, 7, '22.6%', '2.8d'],
    ['Saleshandy', 24, 6, '25%', '4.2d'],
    ['Lemlist', 18, 5, '27.8%', '5.1d'],
  ];
  return (
    <div className="rounded-xl overflow-hidden" style={{ background: C.surface, border: `1px solid ${C.border}` }} data-testid="scene5-sources">
      <div className="px-4 py-3 border-b" style={{ borderColor: C.border }}>
        <div className="text-xs uppercase tracking-[0.15em] font-bold" style={{ color: C.primary }}>Lead Source Performance</div>
      </div>
      <table className="w-full text-xs">
        <thead style={{ background: '#0f0f24' }}>
          <tr>{['Source', 'Leads', 'Qualified', 'Conv %', 'Avg Days'].map((h) => (
            <th key={h} className="px-4 py-2 text-left text-[10px] uppercase tracking-wider font-bold" style={{ color: C.textDim }}>{h}</th>
          ))}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-t" style={{ borderColor: C.border }}>
              <td className="px-4 py-2.5 font-bold" style={{ color: C.text }}>{r[0]}</td>
              <td className="px-4 py-2.5" style={{ color: C.text }}>{r[1]}</td>
              <td className="px-4 py-2.5" style={{ color: C.text }}>{r[2]}</td>
              <td className="px-4 py-2.5 font-mono font-bold" style={{ color: C.gold }}>{r[3]}</td>
              <td className="px-4 py-2.5" style={{ color: C.textDim }}>{r[4]}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

const Scene5 = () => (
  <div data-testid="demo-scene-5">
    <SceneTitle>One month in. Here's what Aria did for this workspace.</SceneTitle>
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
      <AnimatedKPI label="Leads handled" target={143} />
      <AnimatedKPI label="Qualified" target={31} sub="21.7% qualification rate" />
      <AnimatedKPI label="Meetings booked" target={18} />
      <AnimatedKPI label="Closed (Aria-touched)" target={7} sub="₹3.4L total value" />
    </div>

    <div className="mb-4"><Funnel /></div>

    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
      <ConversationsByDay />
      <TouchpointPie />
    </div>

    <div className="mb-6"><SourceTable /></div>

    <div className="rounded-xl p-6 mb-6 text-center" style={{ background: `linear-gradient(135deg, ${C.surface} 0%, #1f1a30 100%)`, border: `2px solid ${C.gold}` }}>
      <div className="text-xs uppercase tracking-[0.18em] font-bold mb-2" style={{ color: C.gold }}>💰 Aria's ROI This Month</div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4 text-left">
        <div>
          <div className="text-[10px] uppercase tracking-wider font-bold" style={{ color: C.textDim }}>Revenue from Aria-touched deals</div>
          <div className="text-2xl font-extrabold" style={{ color: C.text, fontFamily: 'Inter' }}>₹3,40,000</div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-wider font-bold" style={{ color: C.textDim }}>Cost of Aria this month</div>
          <div className="text-2xl font-extrabold" style={{ color: C.text, fontFamily: 'Inter' }}>₹12,999</div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-wider font-bold" style={{ color: C.textDim }}>Hours saved</div>
          <div className="text-2xl font-extrabold" style={{ color: C.text, fontFamily: 'Inter' }}>~19 hours</div>
        </div>
      </div>
      <div className="mt-4 pt-4 border-t" style={{ borderColor: C.gold + '55' }}>
        <span className="text-sm font-bold" style={{ color: C.textDim }}>Return on investment:</span>
        <span className="text-3xl font-extrabold ml-3" style={{ color: C.gold, fontFamily: 'Inter' }}>2,515%</span>
      </div>
    </div>

    <div className="rounded-2xl p-6 md:p-8 text-center" style={{ background: `linear-gradient(135deg, ${C.primary} 0%, #6a5acd 100%)` }} data-testid="scene5-cta">
      <h2 className="text-2xl md:text-3xl font-extrabold mb-2" style={{ color: '#fff', fontFamily: 'Inter' }}>Ready to see this for your business?</h2>
      <p className="text-sm md:text-base mb-5" style={{ color: '#dde6ff' }}>Start your 14-day free trial. Set up in under 4 hours.</p>
      <div className="flex flex-col sm:flex-row gap-3 justify-center">
        <a href={SIGNUP_URL} data-testid="cta-start-trial" className="inline-block px-6 py-3 rounded-lg text-sm font-extrabold transition-all hover:scale-105" style={{ background: '#fff', color: '#1a1a2e', fontFamily: 'Inter' }}>Start Free Trial</a>
        <a href="mailto:meghaagarwal@genleadai.com?subject=Book%20a%20demo%20call" data-testid="cta-book-call" className="inline-block px-6 py-3 rounded-lg text-sm font-extrabold transition-all hover:bg-white/10" style={{ background: 'transparent', color: '#fff', border: '1.5px solid #fff' }}>Book a Demo Call</a>
      </div>
      <div className="mt-5 flex flex-wrap items-center justify-center gap-4 text-xs" style={{ color: '#dde6ff' }}>
        <span>🔒 Secure</span><span>⚡ Live in 4 hrs</span><span>💬 WhatsApp-Native</span><span>🧠 Claude AI</span>
      </div>
    </div>
  </div>
);

// ──────────────────────────────────────────────────────────────────────────
// Bonus scenes
// ──────────────────────────────────────────────────────────────────────────
const BonusA = () => {
  const script = [
    { role: 'lead', text: "Hi, I'm Rohit from RankGenius SEO Agency. We help SaaS companies boost their organic traffic by 300%. Interested in a quick chat about your SEO strategy?" },
  ];
  const { visible } = useConversationPlayer(script);
  return (
    <div data-testid="demo-bonus-a">
      <SceneTitle>Not every WhatsApp message is a lead. Watch Aria identify a vendor pitch and respond appropriately — without polluting your pipeline.</SceneTitle>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <PhoneFrame businessName="Unknown · +91 99XXX 11122">
          {script.slice(0, visible).map((m, i) => <Bubble key={i} role={m.role} text={m.text} />)}
          {visible >= script.length && (
            <Bubble role="aria" text="Hi Rohit! Thanks for reaching out. We're not actively evaluating new vendors right now, but feel free to email us at vendor@yourcompany.com and we'll keep your details on file. 🙏" />
          )}
        </PhoneFrame>
        <div>
          <PanelCard title="3-Layer Classification" icon={<span>🧠</span>}>
            <div className="space-y-1.5 text-xs" style={{ color: C.textDim }}>
              <div>Layer 1: <span style={{ color: C.text }}>No trigger phrase match</span></div>
              <div>Layer 2: <span style={{ color: C.text }}>Unknown number, not in contacts</span></div>
              <div>Layer 3 (AI): <span style={{ color: C.gold, fontWeight: 700 }}>VENDOR ✅</span></div>
              <div className="pt-1.5 mt-1.5 border-t italic" style={{ borderColor: C.border }}>"Self-introducing as agency, pitching services to us"</div>
              <div>Confidence: <span style={{ color: C.success, fontWeight: 700 }}>91%</span></div>
            </div>
          </PanelCard>
          <PanelCard title="Routing Decision" icon={<span>🎯</span>} accent={C.gold}>
            <div className="text-xs" style={{ color: C.text }}>
              ✦ Routed to: <strong>Vendor canned response</strong><br />
              ✦ Action: <strong>Logged to classification_log</strong><br />
              ✦ Lead pipeline: <strong style={{ color: C.danger }}>NOT created</strong>
            </div>
          </PanelCard>
          <p className="text-xs italic mt-3" style={{ color: C.textDim }}>Your sales team never sees this. Your pipeline stays clean.</p>
        </div>
      </div>
    </div>
  );
};

const BonusB = () => {
  const touchpoints = [
    { day: 0, hour: 9, ch: 'WhatsApp', type: 'Intro', msg: "Hi {{first_name}}, I'm Aria from {{company}} — saw you're interested in…" },
    { day: 1, hour: 9, ch: 'WhatsApp', type: 'Qualifier', msg: "Quick question — what's the main outcome you're hoping for?" },
    { day: 2, hour: 11, ch: 'Email', type: 'Value Drop', msg: "Sharing a case study that matches your stage…" },
    { day: 4, hour: 9, ch: 'WhatsApp', type: 'Social Proof', msg: "Just closed a similar deal with {{example_company}} — open to a 15-min walkthrough?" },
    { day: 7, hour: 14, ch: 'WhatsApp', type: 'Follow-up', msg: "Hi {{first_name}} — any thoughts on what I shared earlier?" },
    { day: 10, hour: 9, ch: 'WhatsApp', type: 'Soft CTA', msg: "We have one slot opening up this week. Want me to hold it?" },
    { day: 14, hour: 9, ch: 'WhatsApp', type: 'Budget Probe', msg: "If budget is the blocker, I'd love to suggest a phased approach." },
    { day: 21, hour: 9, ch: 'WhatsApp', type: 'Final', msg: "Last note — happy to revisit when timing is better. Have a great quarter, {{first_name}}." },
  ];
  const [hovered, setHovered] = useState(null);
  return (
    <div data-testid="demo-bonus-b">
      <SceneTitle>Aria's brain is your touchpoint map. 8 steps tailored to your sales cycle — fully editable, drag-to-reorder, or import from your own DOCX.</SceneTitle>
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs" style={{ color: C.textDim }}><strong style={{ color: C.gold }}>8 / 32</strong> touchpoints · Considered Sale template</div>
        <button onClick={() => alert('In your workspace, you can upload your existing sales sequence (.docx / .xlsx / .pdf) and Aria will extract every touchpoint automatically using Claude AI.')} data-testid="bonus-doc-btn"
          className="px-3 py-1.5 text-xs font-bold rounded-md" style={{ background: C.gold, color: '#000' }}>📄 Import from document</button>
      </div>
      <div className="space-y-2">
        {touchpoints.map((tp, i) => (
          <div key={i} onMouseEnter={() => setHovered(i)} onMouseLeave={() => setHovered(null)} data-testid={`bonus-tp-${i}`}
            className="rounded-lg p-3 flex items-center gap-3 transition-all cursor-pointer"
            style={{ background: hovered === i ? '#1f1a30' : C.surface, border: `1px solid ${hovered === i ? C.gold + '88' : C.border}` }}>
            <div className="flex-shrink-0 flex flex-col items-center w-12 py-1 rounded-md" style={{ background: C.primary + '20', border: `1px solid ${C.primary}55` }}>
              <span className="text-[9px] font-bold" style={{ color: C.primary }}>DAY</span>
              <span className="text-base font-extrabold" style={{ color: '#fff', fontFamily: 'Inter' }}>{tp.day}</span>
              <span className="text-[9px] font-mono" style={{ color: C.textDim }}>{String(tp.hour).padStart(2, '0')}:00</span>
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-bold" style={{ color: C.text }}>{tp.type}</span>
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded" style={{ background: tp.ch === 'WhatsApp' ? C.success + '20' : C.primary + '20', color: tp.ch === 'WhatsApp' ? C.success : C.primary }}>{tp.ch}</span>
              </div>
              <div className="text-xs truncate" style={{ color: C.textDim }}>{tp.msg}</div>
            </div>
            <div className="text-[10px] font-mono" style={{ color: C.textDim }}>TP-{String(i + 1).padStart(2, '0')}</div>
          </div>
        ))}
      </div>
    </div>
  );
};

// ──────────────────────────────────────────────────────────────────────────
// Top-level shell
// ──────────────────────────────────────────────────────────────────────────
const SCENES = [
  { id: 1, title: 'New Lead Arrives', component: Scene1 },
  { id: 2, title: 'Aria Qualifies the Lead', component: Scene2 },
  { id: 3, title: 'Pipeline & Dashboard', component: Scene3 },
  { id: 4, title: 'Human Takeover', component: Scene4 },
  { id: 5, title: 'Reports & ROI', component: Scene5 },
  { id: 'A', title: 'Bonus · Aria classifies a vendor', component: BonusA, bonus: true },
  { id: 'B', title: 'Bonus · Touchpoint map', component: BonusB, bonus: true },
];

const InteractiveDemo = () => {
  const [active, setActive] = useState(1);
  const [completed, setCompleted] = useState(new Set());
  const [mode, setMode] = useState('explore');  // 'explore' | 'guided'
  const [copied, setCopied] = useState(false);

  const idx = SCENES.findIndex((s) => s.id === active);
  const SceneComp = SCENES[idx]?.component || Scene1;
  const totalMain = SCENES.filter((s) => !s.bonus).length;

  const goto = (id) => {
    if (mode === 'guided' && typeof id === 'number' && id > Math.max(...Array.from(completed).filter((x) => typeof x === 'number'), 0) + 1) return;
    setActive(id);
  };

  const next = () => {
    setCompleted((c) => new Set([...c, active]));
    if (idx < SCENES.length - 1) setActive(SCENES[idx + 1].id);
  };
  const prev = () => { if (idx > 0) setActive(SCENES[idx - 1].id); };

  const share = async () => {
    try { await navigator.clipboard.writeText(SHARE_URL); setCopied(true); setTimeout(() => setCopied(false), 2000); }
    catch { /* ignore */ }
  };

  // Keyboard arrows
  useEffect(() => {
    const h = (e) => { if (e.key === 'ArrowRight') next(); if (e.key === 'ArrowLeft') prev(); };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
    // eslint-disable-next-line
  }, [active]);

  // Set page title and meta description
  useEffect(() => {
    const prev = document.title;
    document.title = 'Aria Demo — AI Sales PA by GenLeadAI';
    let meta = document.querySelector('meta[name="description"]');
    const created = !meta;
    if (!meta) {
      meta = document.createElement('meta');
      meta.name = 'description';
      document.head.appendChild(meta);
    }
    const prevDesc = meta.content;
    meta.content = 'See Aria in action. Watch how she qualifies leads, books meetings, and manages your WhatsApp pipeline — live interactive demo.';
    // Preload Inter font
    const fontLink = document.createElement('link');
    fontLink.href = 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap';
    fontLink.rel = 'stylesheet';
    document.head.appendChild(fontLink);
    return () => {
      document.title = prev;
      if (created) document.head.removeChild(meta); else meta.content = prevDesc;
      try { document.head.removeChild(fontLink); } catch { /* ignore */ }
    };
  }, []);

  return (
    <div style={{ background: C.bg, color: C.text, minHeight: '100vh', fontFamily: 'Inter, system-ui, sans-serif' }} data-testid="interactive-demo-page">

      <style>{`
        @keyframes aria-bounce {
          0%,80%,100% { transform: scale(0.7); opacity: 0.5; }
          40% { transform: scale(1); opacity: 1; }
        }
        @keyframes aria-fade-in { from { opacity:0; transform: translateX(20px); } to { opacity:1; transform: translateX(0); } }
        .demo-stage { animation: aria-fade-in 300ms ease-out; }
      `}</style>

      {/* Header */}
      <header className="sticky top-0 z-50 px-4 md:px-6 py-3 flex items-center justify-between gap-4 backdrop-blur-md" style={{ background: 'rgba(13,13,26,0.85)', borderBottom: `1px solid ${C.border}` }}>
        <div className="flex items-center gap-3">
          <a href="/" className="flex items-center gap-2">
            <span className="text-base md:text-lg font-extrabold tracking-tight" style={{
              background: `linear-gradient(90deg, ${C.primary}, ${C.gold})`,
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
            }}>Aria by GenLeadAI</span>
          </a>
          <span className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold" style={{ background: C.gold + '22', color: C.gold, border: `1px solid ${C.gold}55` }}>✦ Interactive Demo</span>
        </div>

        <div className="hidden md:flex items-center gap-2 text-xs" style={{ color: C.textDim }}>
          {!SCENES[idx]?.bonus && <>Scene {active} of {totalMain} · <span style={{ color: C.text }}>{SCENES[idx]?.title}</span></>}
        </div>

        <div className="flex items-center gap-2">
          <button onClick={share} data-testid="share-demo-btn" className="hidden md:inline-flex text-[11px] font-bold px-2 py-1.5 rounded" style={{ color: C.textDim, border: `1px solid ${C.border}` }}>
            {copied ? '✓ Copied' : '🔗 Share'}
          </button>
          <button onClick={prev} disabled={idx === 0} data-testid="prev-scene" className="hidden sm:inline-flex text-xs px-3 py-1.5 rounded font-bold disabled:opacity-30" style={{ color: C.textDim, border: `1px solid ${C.border}` }}>← Previous</button>
          <button onClick={next} disabled={idx === SCENES.length - 1} data-testid="next-scene" className="hidden sm:inline-flex text-xs px-3 py-1.5 rounded font-bold disabled:opacity-30" style={{ background: C.primary, color: '#fff' }}>Next →</button>
          <a href={SIGNUP_URL} data-testid="header-trial" className="text-xs font-extrabold px-3 py-1.5 rounded-full whitespace-nowrap" style={{ background: C.gold, color: '#000' }}>Start Free Trial</a>
        </div>
      </header>

      <div className="flex">
        {/* Navigator (desktop) */}
        <aside className="hidden md:block w-64 flex-shrink-0 p-4 sticky top-[68px] self-start" style={{ borderRight: `1px solid ${C.border}`, height: 'calc(100vh - 68px)', overflowY: 'auto' }} data-testid="demo-navigator">
          <div className="mb-4 flex items-center gap-1 p-1 rounded-lg" style={{ background: C.surface, border: `1px solid ${C.border}` }}>
            <button onClick={() => setMode('explore')} data-testid="mode-explore" className="flex-1 text-[10px] font-bold py-1.5 rounded" style={{ background: mode === 'explore' ? C.primary : 'transparent', color: mode === 'explore' ? '#fff' : C.textDim }}>🔓 Free</button>
            <button onClick={() => setMode('guided')} data-testid="mode-guided" className="flex-1 text-[10px] font-bold py-1.5 rounded" style={{ background: mode === 'guided' ? C.primary : 'transparent', color: mode === 'guided' ? '#fff' : C.textDim }}>📖 Guided</button>
          </div>
          <div className="space-y-1">
            {SCENES.map((s) => {
              const isActive = active === s.id;
              const isDone = completed.has(s.id);
              const isLocked = mode === 'guided' && !s.bonus && typeof s.id === 'number' && s.id > Math.max(0, ...Array.from(completed).filter((x) => typeof x === 'number')) + 1;
              return (
                <button key={s.id} onClick={() => goto(s.id)} disabled={isLocked} data-testid={`nav-scene-${s.id}`}
                  className="w-full text-left p-2.5 rounded-md text-xs font-medium transition-all flex items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
                  style={{
                    background: isActive ? C.primary + '22' : 'transparent',
                    borderLeft: isActive ? `3px solid ${C.primary}` : `3px solid transparent`,
                    color: isActive ? C.text : C.textDim,
                  }}>
                  <span className="font-mono text-[10px] font-bold">{s.bonus ? '★' : `①②③④⑤`[s.id - 1]}</span>
                  <span className="flex-1 truncate">{s.title}</span>
                  {isDone && <span style={{ color: C.success }}>✅</span>}
                  {isLocked && <span style={{ color: C.textDim }}>🔒</span>}
                </button>
              );
            })}
          </div>
        </aside>

        {/* Mobile horizontal tab strip */}
        <div className="md:hidden w-full overflow-x-auto sticky top-[60px] z-40 px-3 py-2" style={{ background: C.bg, borderBottom: `1px solid ${C.border}` }}>
          <div className="flex gap-2">
            {SCENES.map((s) => (
              <button key={s.id} onClick={() => goto(s.id)} data-testid={`nav-mobile-${s.id}`}
                className="flex-shrink-0 text-[10px] font-bold px-3 py-1.5 rounded-full whitespace-nowrap"
                style={{
                  background: active === s.id ? C.primary : C.surface,
                  color: active === s.id ? '#fff' : C.textDim,
                  border: `1px solid ${active === s.id ? C.primary : C.border}`,
                }}>
                {s.bonus ? '★' : s.id} · {s.title.length > 20 ? s.title.slice(0, 20) + '…' : s.title}
              </button>
            ))}
          </div>
        </div>

        {/* Stage */}
        <main className="flex-1 min-w-0 p-4 md:p-6">
          <div key={active} className="demo-stage">
            <SceneComp />
          </div>
          <div className="mt-8 flex items-center justify-between sm:hidden">
            <button onClick={prev} disabled={idx === 0} className="text-xs px-4 py-2 rounded font-bold disabled:opacity-30" style={{ color: C.textDim, border: `1px solid ${C.border}` }}>← Previous</button>
            <button onClick={next} disabled={idx === SCENES.length - 1} className="text-xs px-4 py-2 rounded font-bold disabled:opacity-30" style={{ background: C.primary, color: '#fff' }}>Next →</button>
          </div>
        </main>
      </div>

      {/* Footer */}
      <footer className="px-4 md:px-6 py-6 text-center text-xs" style={{ color: C.textDim, borderTop: `1px solid ${C.border}` }}>
        Aria by GenLeadAI · <a href="/privacy" className="underline">Privacy</a> · <a href="/terms" className="underline">Terms</a> · <a href="mailto:meghaagarwal@genleadai.com" className="underline">Contact</a>
      </footer>
    </div>
  );
};

export default InteractiveDemo;
