import React, { useEffect, useState } from 'react';
import {
  ChartLineUp, Lightning, Globe, Plug, CheckCircle, Warning, ArrowRight,
  PaperPlaneTilt, Heartbeat, ArrowsClockwise, CaretRight, Receipt,
} from '@phosphor-icons/react';
import { toast } from 'sonner';
import api from '../../config/api';

/**
 * The four stat cards at the top of the Integration Hub.
 * Connected Tools · Lead Sources · CRM Sync · Automation Health
 */
export function HubStatCards({ integrations, health }) {
  const connected = integrations.filter((i) => i.status === 'connected');
  const leadSources = connected.filter((i) => i.category === 'lead_source');
  const crmConnected = connected.filter((i) => i.category === 'crm');

  const cards = [
    {
      key: 'tools', label: 'Connected tools',
      value: connected.length || 0, suffix: 'active',
      icon: Plug, tint: '#7C35DC',
    },
    {
      key: 'leads', label: 'Lead sources',
      value: leadSources.length || 0, suffix: leadSources.length === 1 ? 'source' : 'sources',
      icon: Globe, tint: '#16A34A',
    },
    {
      key: 'crm', label: 'CRM sync',
      value: crmConnected[0]?.label || 'Not connected',
      suffix: crmConnected[0] ? 'connected' : null,
      icon: Receipt, tint: '#0055FF',
    },
    {
      key: 'health', label: 'Automation health',
      value: `${health?.healthy_percent ?? 100}%`, suffix: 'healthy',
      icon: Heartbeat, tint: '#E11D48',
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3" data-testid="hub-stat-cards">
      {cards.map((c) => (
        <div key={c.key} data-testid={`stat-${c.key}`} className="bg-white border border-[#E8E0F5] rounded-2xl p-4 flex items-start justify-between" style={{ boxShadow: 'var(--shadow-card)' }}>
          <div>
            <div className="text-[10px] uppercase tracking-[0.18em] font-bold text-slate-500 mb-1">{c.label}</div>
            <div className="text-xl font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{c.value}</div>
            {c.suffix && <div className="text-[10px] uppercase tracking-wider font-bold text-slate-400 mt-0.5">{c.suffix}</div>}
          </div>
          <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: c.tint + '15', color: c.tint }}>
            <c.icon size={18} weight="duotone" />
          </div>
        </div>
      ))}
    </div>
  );
}


/** Setup progress bar with horizontal stepper. */
export function SetupProgress() {
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get('/api/integrations/setup-progress').then((r) => setData(r.data)).catch(() => {});
  }, []);

  if (!data) return null;

  return (
    <section data-testid="setup-progress" className="bg-white border border-[#E8E0F5] rounded-2xl p-5" style={{ boxShadow: 'var(--shadow-card)' }}>
      <div className="flex items-start justify-between mb-3 flex-wrap gap-2">
        <div>
          <h3 className="text-base font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Your Aria sales system: {data.percent}% complete</h3>
          <p className="text-xs text-[#5A4A7A] mt-0.5">Connect each step to unlock the full lead → sale loop. {data.completed}/{data.total} steps live.</p>
        </div>
        <div className="text-[10px] font-extrabold uppercase tracking-wider px-2.5 py-1 rounded-full border bg-violet-50 text-violet-700 border-violet-200">
          {data.percent}%
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-2 rounded-full bg-slate-100 overflow-hidden mb-4">
        <div
          data-testid="setup-progress-bar"
          className="h-full bg-gradient-to-r from-violet-500 to-fuchsia-500 transition-all duration-500"
          style={{ width: `${data.percent}%` }}
        />
      </div>

      {/* Stepper */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2" data-testid="setup-stepper">
        {data.steps.map((s, i) => {
          const done = s.complete;
          return (
            <div
              key={s.key}
              data-testid={`setup-step-${s.key}`}
              className={`relative p-2.5 rounded-xl border transition-all ${
                done ? 'bg-emerald-50 border-emerald-200' : 'bg-slate-50 border-slate-200'
              }`}
            >
              <div className="flex items-center gap-1.5 mb-1">
                <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-extrabold ${
                  done ? 'bg-emerald-500 text-white' : 'bg-slate-300 text-white'
                }`}>{done ? '✓' : i + 1}</div>
                <span className={`text-[10px] uppercase font-bold tracking-wider ${done ? 'text-emerald-700' : 'text-slate-500'}`}>Step {i + 1}</span>
              </div>
              <div className="text-xs font-bold text-slate-900">{s.label}</div>
            </div>
          );
        })}
      </div>
    </section>
  );
}


/** Visual data flow preview — capture → signal → score → followup → CRM → booking → alert. */
export function DataFlowPreview() {
  const [data, setData] = useState(null);
  useEffect(() => {
    api.get('/api/integrations/data-flow').then((r) => setData(r.data)).catch(() => {});
  }, []);

  if (!data) return null;
  return (
    <section data-testid="data-flow-preview" className="bg-white border border-[#E8E0F5] rounded-2xl p-5" style={{ boxShadow: 'var(--shadow-card)' }}>
      <div className="mb-4">
        <h3 className="text-base font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>How your lead data flows</h3>
        <p className="text-xs text-[#5A4A7A] mt-0.5">Every lead travels through Aria's intelligence layer before it hits your CRM.</p>
      </div>
      <div className="flex items-center gap-2 overflow-x-auto pb-2" data-testid="data-flow-nodes">
        {data.nodes.map((n, i) => (
          <React.Fragment key={n.key}>
            <div data-testid={`flow-node-${n.key}`} className="shrink-0 min-w-[160px] p-3 rounded-xl border border-[#E8E0F5] bg-gradient-to-br from-white to-violet-50/30">
              <div className="text-[9px] uppercase tracking-wider font-bold text-violet-600 mb-1">Step {i + 1}</div>
              <div className="text-xs font-extrabold text-slate-900 mb-0.5">{n.title}</div>
              <div className="text-[11px] text-slate-600 leading-snug">{n.subtitle}</div>
            </div>
            {i < data.nodes.length - 1 && (
              <CaretRight size={18} weight="bold" className="text-violet-400 shrink-0" />
            )}
          </React.Fragment>
        ))}
      </div>
    </section>
  );
}


/** Integration health table. */
export function IntegrationHealthTable() {
  const [data, setData] = useState(null);
  useEffect(() => {
    api.get('/api/integrations/health').then((r) => setData(r.data)).catch(() => {});
  }, []);
  if (!data) return null;

  return (
    <section data-testid="integration-health" className="bg-white border border-[#E8E0F5] rounded-2xl overflow-hidden" style={{ boxShadow: 'var(--shadow-card)' }}>
      <div className="p-5 border-b border-[#F0ECF9] flex items-start justify-between flex-wrap gap-2">
        <div>
          <h3 className="text-base font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Integration health</h3>
          <p className="text-xs text-[#5A4A7A] mt-0.5">Live status across all connected tools. {data.healthy}/{data.total} healthy.</p>
        </div>
        <div className={`text-[10px] font-extrabold uppercase tracking-wider px-2.5 py-1 rounded-full border ${
          data.healthy_percent === 100 ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
          data.healthy_percent >= 70 ? 'bg-amber-50 text-amber-800 border-amber-200' :
          'bg-rose-50 text-rose-700 border-rose-200'
        }`}>{data.healthy_percent}% healthy</div>
      </div>
      {data.rows.length === 0 ? (
        <div className="p-6 text-center text-slate-400 text-xs" data-testid="health-empty">
          Connect at least one integration to see health here.
        </div>
      ) : (
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-[10px] uppercase tracking-wider text-slate-500 font-semibold">
            <tr>
              <th className="px-4 py-2.5 text-left">Tool</th>
              <th className="px-4 py-2.5 text-left">Status</th>
              <th className="px-4 py-2.5 text-left">Last sync</th>
              <th className="px-4 py-2.5 text-left">Issue</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((r) => (
              <tr key={r.type} data-testid={`health-row-${r.type}`} className="border-t border-slate-100">
                <td className="px-4 py-2.5 font-bold text-slate-900">{r.label}</td>
                <td className="px-4 py-2.5">
                  {r.status === 'connected' && !r.error_message ? (
                    <span className="inline-flex items-center gap-1 text-emerald-700 bg-emerald-50 border border-emerald-200 text-[10px] font-extrabold uppercase tracking-wider px-2 py-0.5 rounded-full">
                      <CheckCircle size={10} weight="fill" /> Connected
                    </span>
                  ) : r.error_message ? (
                    <span className="inline-flex items-center gap-1 text-rose-700 bg-rose-50 border border-rose-200 text-[10px] font-extrabold uppercase tracking-wider px-2 py-0.5 rounded-full">
                      <Warning size={10} weight="fill" /> Error
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-slate-700 bg-slate-100 border border-slate-200 text-[10px] font-extrabold uppercase tracking-wider px-2 py-0.5 rounded-full">
                      {r.status}
                    </span>
                  )}
                </td>
                <td className="px-4 py-2.5 text-xs text-slate-600">{r.last_sync_at ? relative(r.last_sync_at) : '—'}</td>
                <td className="px-4 py-2.5 text-xs text-rose-600 font-mono">{r.error_message || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}


/** "Send Test Lead" CTA — fires a labeled test lead through every connected outbound integration. */
export function SendTestLeadButton() {
  const [busy, setBusy] = useState(false);
  const [last, setLast] = useState(null);

  const send = async () => {
    setBusy(true);
    try {
      const r = await api.post('/api/integrations/test-lead', {});
      setLast(r.data);
      if (r.data.fired === 0) {
        toast.info('No outbound integrations connected yet — connect one to test the flow.');
      } else {
        toast.success(`Test lead fired through ${r.data.fired} integration(s). Check your Slack/CRM/analytics for the “ARIA TEST LEAD” marker.`);
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Test failed');
    } finally { setBusy(false); }
  };

  return (
    <div data-testid="send-test-lead-block" className="bg-gradient-to-br from-violet-50 to-fuchsia-50 border border-violet-200 rounded-2xl p-5">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-violet-100 text-violet-600 flex items-center justify-center">
            <PaperPlaneTilt size={18} weight="duotone" />
          </div>
          <div>
            <h3 className="text-base font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Test your lead flow</h3>
            <p className="text-xs text-[#5A4A7A] mt-0.5 max-w-md">
              Fire a clearly-labeled test lead through every connected outbound integration. It will <b>not</b> appear in your Lead Inbox — just downstream in Zapier/GA4/CRM.
            </p>
          </div>
        </div>
        <button
          data-testid="send-test-lead-btn"
          onClick={send}
          disabled={busy}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-violet-600 text-white text-xs font-bold uppercase tracking-wider hover:bg-violet-700 disabled:opacity-50"
        >
          {busy ? 'Firing…' : <>Send test lead <ArrowRight size={11} weight="bold" /></>}
        </button>
      </div>
      {last && (
        <div data-testid="test-lead-results" className="mt-4 p-3 rounded-xl bg-white border border-violet-100">
          <div className="text-[10px] uppercase tracking-wider font-bold text-violet-600 mb-2">Last test — {last.test_lead_id}</div>
          {last.fired === 0 ? (
            <div className="text-xs text-slate-500">No outbound integrations connected yet.</div>
          ) : (
            <ul className="space-y-1 text-xs">
              {last.results.map((r) => (
                <li key={r.type} data-testid={`test-result-${r.type}`} className="flex items-center justify-between gap-2">
                  <span className="font-bold text-slate-900">{r.label}</span>
                  <span className={`text-[10px] font-extrabold uppercase px-1.5 py-0.5 rounded-full border ${
                    r.ok ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-rose-50 text-rose-700 border-rose-200'
                  }`}>{r.ok ? 'OK' : 'Failed'}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}


function relative(iso) {
  try {
    const d = new Date(iso);
    const sec = Math.round((Date.now() - d.getTime()) / 1000);
    if (sec < 60) return `${sec}s ago`;
    if (sec < 3600) return `${Math.round(sec / 60)} min ago`;
    if (sec < 86400) return `${Math.round(sec / 3600)} hr ago`;
    return `${Math.round(sec / 86400)} d ago`;
  } catch { return iso; }
}
