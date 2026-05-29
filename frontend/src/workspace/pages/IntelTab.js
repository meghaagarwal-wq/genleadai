/**
 * IntelTab — Batch 4 Multi-Platform Intelligence + Outreach Playbook
 * + Channel-Adaptive Composer (WhatsApp / Email / LinkedIn).
 *
 * Fetches and renders the intelligence profile for the current lead.
 * If no profile exists yet, surfaces a "Run intel" CTA.
 *
 * Backend contract
 * ────────────────
 *   GET   /api/intel/{lead_id}
 *   POST  /api/intel/{lead_id}/research { refresh }
 *   POST  /api/intel/{lead_id}/playbook { refresh }
 *   POST  /api/intel/{lead_id}/compose  { channel, user_steer? }
 *   GET   /api/intel/{lead_id}/budget
 */
import { useEffect, useState, useCallback } from 'react';
import { Brain, Sparkle, Warning, ChartLineUp, Target, Lightning, ArrowsClockwise, Copy, ChatCircleText, EnvelopeSimple, LinkedinLogo } from '@phosphor-icons/react';
import { toast } from 'sonner';
import { ptApi } from '../shared';

const SIGNAL_COLORS = {
  intent:           { bg: '#FEF3C7', text: '#92400E', border: '#F59E0B' },
  growth:           { bg: '#DCFCE7', text: '#166534', border: '#10B981' },
  pain:             { bg: '#FEE2E2', text: '#991B1B', border: '#DC2626' },
  trigger_event:    { bg: '#E0E7FF', text: '#3730A3', border: '#6366F1' },
  competitive:      { bg: '#FCE7F3', text: '#9D174D', border: '#EC4899' },
  buying_authority: { bg: '#EDE9FE', text: '#5B21B6', border: '#7C35DC' },
  engagement:       { bg: '#E0F2FE', text: '#075985', border: '#0EA5E9' },
  risk:             { bg: '#FEE2E2', text: '#7F1D1D', border: '#DC2626' },
};

const TIMING_LABELS = {
  now: 'Send now',
  today_business_hours: 'Today · business hours',
  tomorrow_morning: 'Tomorrow morning',
  mid_week: 'Mid-week',
  next_week: 'Next week',
};

const CHANNEL_ICONS = { whatsapp: ChatCircleText, email: EnvelopeSimple, linkedin: LinkedinLogo };

const IntelTab = ({ leadId, lead }) => {
  const [profile, setProfile] = useState(null);
  const [budget, setBudget] = useState(null);
  const [loading, setLoading] = useState(true);
  const [researching, setResearching] = useState(false);
  const [playbookBusy, setPlaybookBusy] = useState(false);
  const [composeBusy, setComposeBusy] = useState(false);
  const [sendBusy, setSendBusy] = useState(false);
  const [composeChannel, setComposeChannel] = useState('email');
  const [composeSteer, setComposeSteer] = useState('');
  const [composedMessage, setComposedMessage] = useState(null);
  const [dispatchResult, setDispatchResult] = useState(null);

  const fetchProfile = useCallback(async () => {
    setLoading(true);
    try {
      const [pr, br] = await Promise.all([
        ptApi.get(`/api/intel/${leadId}`),
        ptApi.get(`/api/intel/${leadId}/budget`),
      ]);
      setProfile(pr.data.profile);
      setBudget(br.data);
    } catch {
      toast.error('Could not load intelligence profile');
    } finally {
      setLoading(false);
    }
  }, [leadId]);

  useEffect(() => { fetchProfile(); }, [fetchProfile]);

  const runResearch = async (refresh = false) => {
    setResearching(true);
    try {
      const r = await ptApi.post(`/api/intel/${leadId}/research`, { refresh });
      setProfile(r.data.profile);
      toast.success(r.data.cached ? 'Loaded cached intel' : 'Intel synthesised');
      // refresh budget
      const br = await ptApi.get(`/api/intel/${leadId}/budget`);
      setBudget(br.data);
    } catch (err) {
      const status = err.response?.status;
      const detail = err.response?.data?.detail || 'Research failed';
      if (status === 503) {
        toast.error('Connect RapidAPI or Serper on /app/integrations first');
      } else if (status === 429) {
        toast.error('Crawl budget hit (8 calls / prospect)');
      } else {
        toast.error(detail);
      }
    } finally {
      setResearching(false);
    }
  };

  const runPlaybook = async (refresh = false) => {
    setPlaybookBusy(true);
    try {
      const r = await ptApi.post(`/api/intel/${leadId}/playbook`, { refresh });
      setProfile((p) => ({ ...(p || {}), playbook: r.data.playbook }));
      toast.success(r.data.cached ? 'Loaded cached playbook' : 'Playbook generated');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Playbook failed');
    } finally {
      setPlaybookBusy(false);
    }
  };

  const runCompose = async () => {
    setComposeBusy(true);
    setComposedMessage(null);
    setDispatchResult(null);
    try {
      const r = await ptApi.post(`/api/intel/${leadId}/compose`, {
        channel: composeChannel,
        user_steer: composeSteer.trim() || undefined,
      });
      setComposedMessage(r.data);
      toast.success(`${composeChannel} message generated`);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Compose failed');
    } finally {
      setComposeBusy(false);
    }
  };

  // iter117 — final-mile: compose AND dispatch via Resend / 360dialog / LinkedIn.
  const runComposeAndSend = async () => {
    setSendBusy(true);
    setDispatchResult(null);
    try {
      const r = await ptApi.post(`/api/intel/${leadId}/compose-and-send`, {
        channel: composeChannel,
        user_steer: composeSteer.trim() || undefined,
        auto_send: true,
      });
      setComposedMessage(r.data.composed);
      setDispatchResult(r.data.dispatch);
      const d = r.data.dispatch || {};
      if (d.sent) {
        toast.success(`Sent via ${d.provider || composeChannel}`);
      } else if (d.logged_only) {
        toast.info(d.note || 'Drafted — awaiting manual send');
      } else {
        toast.error(d.error || 'Send failed');
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Send failed');
    } finally {
      setSendBusy(false);
    }
  };

  const copyMessage = () => {
    if (!composedMessage) return;
    let txt = '';
    if (composedMessage.channel === 'email' && typeof composedMessage.message === 'object') {
      txt = `Subject: ${composedMessage.message.subject}\n\n${composedMessage.message.body}`;
    } else {
      txt = composedMessage.message || '';
    }
    navigator.clipboard.writeText(txt);
    toast.success('Copied to clipboard');
  };

  if (loading) {
    return <div className="text-sm text-[#64748B] p-6 text-center" data-testid="intel-loading">Loading intelligence…</div>;
  }

  // EMPTY STATE — no profile yet
  if (!profile) {
    return (
      <div className="bg-white border border-[#E2E8F0] rounded-lg p-8 text-center" data-testid="intel-empty-state">
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-full mb-3"
             style={{ background: 'linear-gradient(135deg, #FAF7FF 0%, #EDE9FE 100%)' }}>
          <Brain size={24} weight="duotone" className="text-[#7C35DC]" />
        </div>
        <h3 className="text-base font-bold text-[#0F172A]" style={{ fontFamily: 'Space Grotesk, Inter' }}>
          No intel yet for {lead?.first_name || 'this lead'}
        </h3>
        <p className="text-sm text-[#64748B] mt-1 max-w-md mx-auto">
          Run a multi-platform crawl (LinkedIn + Google) and let ARIA synthesise the signals into an actionable outreach plan.
        </p>
        <div className="mt-2 text-xs text-[#94A3B8]">
          Budget: {budget?.calls_remaining ?? 8} / {budget?.cap ?? 8} calls remaining for this prospect
        </div>
        <button
          onClick={() => runResearch(false)}
          disabled={researching}
          data-testid="intel-run-research"
          className="mt-4 inline-flex items-center gap-2 px-5 py-2.5 rounded-md text-sm font-semibold text-white disabled:opacity-50"
          style={{ background: 'linear-gradient(135deg, #4C1D95 0%, #7C35DC 100%)' }}
        >
          <Sparkle size={14} weight="fill" />
          {researching ? 'Crawling & synthesising…' : 'Run Intel'}
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="intel-tab">
      {/* Header — Fit + Budget + Refresh */}
      <div className="flex items-start justify-between gap-3 bg-white border border-[#E2E8F0] rounded-lg p-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <Brain size={16} weight="duotone" className="text-[#7C35DC]" />
            <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#7C35DC]">Intelligence Profile</span>
          </div>
          <p className="text-sm text-[#0F172A] mt-1.5 leading-snug" data-testid="intel-summary">{profile.summary || '—'}</p>
        </div>
        <div className="flex flex-col items-end gap-2 flex-shrink-0">
          <FitGauge score={profile.fit_score || 0} />
          <div className="text-[10px] text-[#94A3B8]">
            {budget?.calls_used ?? 0}/{budget?.cap ?? 8} crawl calls used
          </div>
          <button
            onClick={() => runResearch(true)}
            disabled={researching}
            data-testid="intel-refresh"
            className="inline-flex items-center gap-1 text-xs font-semibold text-[#7C35DC] hover:text-[#4C1D95] disabled:opacity-50"
          >
            <ArrowsClockwise size={12} weight="bold" /> {researching ? 'Refreshing…' : 'Re-crawl'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* LEFT — Signals + Risk */}
        <div className="lg:col-span-2 space-y-4">
          {/* Signals */}
          <SectionCard title="Signals" icon={ChartLineUp} testid="intel-signals">
            {(profile.signals || []).length === 0 ? (
              <div className="text-sm text-[#64748B]">No signals extracted from the crawl.</div>
            ) : (
              <div className="space-y-2">
                {(profile.signals || []).map((s, i) => (
                  <SignalRow key={i} signal={s} index={i} />
                ))}
              </div>
            )}
          </SectionCard>

          {/* Risk flags */}
          {(profile.risk_flags || []).length > 0 && (
            <SectionCard title="Risk flags" icon={Warning} testid="intel-risk-flags" accent="#DC2626">
              <div className="space-y-1.5">
                {profile.risk_flags.map((r, i) => (
                  <div key={i} className="flex items-start gap-2 text-sm" data-testid={`intel-risk-${i}`}>
                    <span className="mt-1 w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: r.severity === 'high' ? '#DC2626' : r.severity === 'med' ? '#F59E0B' : '#94A3B8' }} />
                    <div>
                      <div className="font-semibold text-[#0F172A]">{r.label}</div>
                      <div className="text-xs text-[#64748B]">{r.reason}</div>
                    </div>
                  </div>
                ))}
              </div>
            </SectionCard>
          )}

          {/* Composer */}
          <SectionCard title="Channel-Adaptive Composer" icon={Sparkle} testid="intel-composer">
            <div className="flex items-center gap-1.5 mb-3">
              {['whatsapp', 'email', 'linkedin'].map((ch) => {
                const Icon = CHANNEL_ICONS[ch];
                const active = composeChannel === ch;
                return (
                  <button
                    key={ch}
                    onClick={() => { setComposeChannel(ch); setComposedMessage(null); }}
                    data-testid={`intel-channel-${ch}`}
                    className={`flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-md text-xs font-semibold border transition-all ${active ? 'text-white border-transparent' : 'text-[#475569] border-[#E2E8F0] hover:bg-[#F8FAFC]'}`}
                    style={active ? { background: 'linear-gradient(135deg, #4C1D95 0%, #7C35DC 100%)' } : {}}
                  >
                    <Icon size={13} weight={active ? 'fill' : 'regular'} />
                    <span className="capitalize">{ch}</span>
                  </button>
                );
              })}
            </div>
            <textarea
              value={composeSteer}
              onChange={(e) => setComposeSteer(e.target.value)}
              placeholder="Optional founder steer (e.g., 'mention the funding round')"
              data-testid="intel-compose-steer"
              rows={2}
              className="w-full text-sm border border-[#E2E8F0] rounded-md px-2.5 py-1.5 outline-none resize-none mb-2"
            />
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-1.5">
                <button
                  onClick={runCompose}
                  disabled={composeBusy || sendBusy}
                  data-testid="intel-compose-go"
                  className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-md text-sm font-semibold text-[#7C35DC] border border-[#7C35DC]/40 hover:bg-[#FAF7FF] disabled:opacity-50"
                >
                  <Lightning size={13} weight="bold" />
                  {composeBusy ? 'Composing…' : 'Draft'}
                </button>
                <button
                  onClick={runComposeAndSend}
                  disabled={composeBusy || sendBusy}
                  data-testid="intel-send-via-aria"
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-bold text-white disabled:opacity-50"
                  style={{ background: 'linear-gradient(135deg, #4C1D95 0%, #7C35DC 100%)' }}
                >
                  <Sparkle size={13} weight="fill" />
                  {sendBusy ? 'Sending…' : 'Send via ARIA'}
                </button>
              </div>
              {composedMessage && (
                <button onClick={copyMessage} data-testid="intel-compose-copy"
                  className="inline-flex items-center gap-1 text-xs font-semibold text-[#7C35DC] hover:text-[#4C1D95]">
                  <Copy size={11} weight="bold" /> Copy
                </button>
              )}
            </div>
            {composedMessage && (
              <div className="mt-3 p-3 rounded-md border border-[#7C35DC]/30" style={{ background: '#FAF7FF' }} data-testid="intel-compose-result">
                {composedMessage.channel === 'email' && typeof composedMessage.message === 'object' ? (
                  <>
                    <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#7C35DC] mb-1">Subject</div>
                    <div className="text-sm font-semibold text-[#0F172A] mb-2">{composedMessage.message.subject}</div>
                    <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#7C35DC] mb-1">Body</div>
                    <div className="text-sm text-[#0F172A] whitespace-pre-wrap">{composedMessage.message.body}</div>
                  </>
                ) : (
                  <div className="text-sm text-[#0F172A] whitespace-pre-wrap">{composedMessage.message}</div>
                )}
                {!composedMessage.ai_powered && (
                  <div className="mt-2 text-[10px] text-[#DC2626]">Fallback message — Claude unavailable.</div>
                )}
                {dispatchResult && (
                  <div
                    data-testid="intel-dispatch-result"
                    className={`mt-3 px-2.5 py-1.5 rounded-md text-[11px] font-semibold border ${
                      dispatchResult.sent
                        ? 'text-emerald-700 border-emerald-200 bg-emerald-50'
                        : dispatchResult.logged_only
                        ? 'text-amber-700 border-amber-200 bg-amber-50'
                        : 'text-[#7F1D1D] border-red-200 bg-red-50'
                    }`}
                  >
                    {dispatchResult.sent
                      ? `✓ Sent via ${dispatchResult.provider || composeChannel}${dispatchResult.provider_id ? ` · ${dispatchResult.provider_id}` : ''}`
                      : dispatchResult.logged_only
                      ? `↗ Drafted — ${dispatchResult.note || 'queued for manual send'}`
                      : `× ${dispatchResult.error || 'Send failed'}`}
                  </div>
                )}
              </div>
            )}
          </SectionCard>
        </div>

        {/* RIGHT — Interests + Authority + Playbook */}
        <div className="space-y-4">
          {/* Interests */}
          {(profile.interests || []).length > 0 && (
            <SectionCard title="Interests" icon={Target} testid="intel-interests">
              <div className="flex flex-wrap gap-1.5">
                {profile.interests.map((it, i) => (
                  <span key={i} data-testid={`intel-interest-${i}`}
                    className="px-2 py-1 rounded-md text-xs font-semibold border border-[#7C35DC]/30 text-[#7C35DC]"
                    style={{ background: '#FAF7FF' }}>{it}</span>
                ))}
              </div>
            </SectionCard>
          )}

          {/* Buying authority */}
          {profile.buying_authority && (
            <SectionCard title="Buying authority" testid="intel-authority">
              <KV label="Seniority" value={profile.buying_authority.role_seniority || '—'} />
              <KV label="Decision-maker score" value={`${profile.buying_authority.decision_maker_likelihood ?? 0}/100`} />
            </SectionCard>
          )}

          {/* Playbook */}
          <SectionCard
            title="Outreach Playbook"
            icon={Lightning}
            testid="intel-playbook"
            right={
              <button onClick={() => runPlaybook(!!profile.playbook)} disabled={playbookBusy} data-testid="intel-playbook-go"
                className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-[0.14em] text-[#7C35DC] hover:text-[#4C1D95] disabled:opacity-50">
                <ArrowsClockwise size={10} weight="bold" /> {playbookBusy ? '…' : profile.playbook ? 'Refresh' : 'Generate'}
              </button>
            }
          >
            {!profile.playbook ? (
              <div className="text-xs text-[#64748B]">Click <span className="font-semibold text-[#7C35DC]">Generate</span> to draft an outreach playbook from the signals above.</div>
            ) : (
              <div className="space-y-2">
                <KV label="Channel"
                     value={<span className="capitalize font-semibold text-[#7C35DC]">{profile.playbook.recommended_channel}</span>} />
                <div className="text-[10px] text-[#94A3B8] -mt-1">{profile.playbook.channel_reason}</div>
                <KV label="Send timing" value={TIMING_LABELS[profile.playbook.send_timing] || profile.playbook.send_timing} />
                <div className="text-[10px] text-[#94A3B8] -mt-1">{profile.playbook.timing_reason}</div>
                <div className="pt-2 border-t border-[#F1F5F9]">
                  <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#64748B] mb-1">Opening message</div>
                  <div className="text-sm text-[#0F172A] p-2 rounded-md border border-[#E2E8F0]" style={{ background: '#FAFAFA' }} data-testid="intel-playbook-opening">
                    {profile.playbook.opening_message}
                  </div>
                </div>
                {profile.playbook.lead_magnet && (
                  <KV label="Lead magnet" value={profile.playbook.lead_magnet} />
                )}
                {(profile.playbook.follow_up_plan || []).length > 0 && (
                  <div className="pt-2 border-t border-[#F1F5F9]">
                    <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#64748B] mb-1.5">Follow-up plan</div>
                    <div className="space-y-1">
                      {profile.playbook.follow_up_plan.map((f, i) => (
                        <div key={i} className="text-xs text-[#475569] flex items-center gap-1.5" data-testid={`intel-followup-${i}`}>
                          <span className="font-mono font-bold text-[#7C35DC]">D+{f.day}</span>
                          <span className="capitalize px-1.5 py-0.5 rounded text-[10px] font-bold border border-[#E2E8F0]">{f.channel}</span>
                          <span className="truncate">{f.intent} · {f.message_hint}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </SectionCard>
        </div>
      </div>

      {/* Crawl sources */}
      {profile.crawl_meta && (
        <div className="text-[10px] text-[#94A3B8] text-center" data-testid="intel-crawl-meta">
          Sources: {profile.crawl_meta.sources_succeeded?.join(' · ') || '—'} · {profile.crawl_meta.calls_made || 0} API calls
          {profile.crawl_meta.errors?.length > 0 && (
            <span className="text-[#DC2626] ml-2">· {profile.crawl_meta.errors.length} error(s)</span>
          )}
        </div>
      )}
    </div>
  );
};

// ─── Subcomponents ─────────────────────────────────────────────────────
const SectionCard = ({ title, icon: Icon, right, accent, testid, children }) => (
  <div className="bg-white border border-[#E2E8F0] rounded-lg overflow-hidden" data-testid={testid}>
    <div className="px-4 py-2.5 border-b border-[#E2E8F0] flex items-center justify-between bg-[#F8FAFC]">
      <div className="flex items-center gap-1.5">
        {Icon && <Icon size={14} weight="duotone" style={{ color: accent || '#475569' }} />}
        <h3 className="text-xs font-bold uppercase tracking-[0.16em]" style={{ color: accent || '#475569' }}>{title}</h3>
      </div>
      {right}
    </div>
    <div className="p-4">{children}</div>
  </div>
);

const KV = ({ label, value }) => (
  <div className="flex items-center justify-between py-1 border-b border-[#F1F5F9] last:border-0">
    <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#64748B]">{label}</span>
    <span className="text-sm text-[#0F172A] font-medium">{value || '—'}</span>
  </div>
);

const SignalRow = ({ signal, index }) => {
  const color = SIGNAL_COLORS[signal.type] || SIGNAL_COLORS.engagement;
  return (
    <div className="flex items-start gap-2.5 pb-2 border-b border-[#F1F5F9] last:border-0" data-testid={`intel-signal-${index}`}>
      <span
        className="text-[10px] font-bold uppercase tracking-[0.14em] px-1.5 py-0.5 rounded flex-shrink-0 mt-0.5"
        style={{ background: color.bg, color: color.text, border: `1px solid ${color.border}40` }}
      >
        {signal.type.replace('_', ' ')}
      </span>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-semibold text-[#0F172A]">{signal.label}</div>
        <div className="text-xs text-[#64748B] mt-0.5 italic">"{signal.evidence}"</div>
        <div className="text-[10px] text-[#94A3B8] mt-0.5">
          {signal.source} · {signal.confidence} confidence
        </div>
      </div>
    </div>
  );
};

const FitGauge = ({ score }) => {
  const color = score >= 70 ? '#10B981' : score >= 40 ? '#F59E0B' : '#94A3B8';
  return (
    <div className="text-right" data-testid="intel-fit-gauge">
      <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#64748B]">ICP Fit</div>
      <div className="text-2xl font-extrabold leading-none" style={{ color, fontFamily: 'Space Grotesk, Inter' }}>{score}</div>
      <div className="text-[10px] text-[#94A3B8]">/100</div>
    </div>
  );
};

export default IntelTab;
