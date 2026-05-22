// Iter79 — S8: Master Admin Deployments tab.
// Shows every workspace as a deployment card (SETUP / LIVE / PAUSED) with
// rollup counts, last-activity, channel flags, and pause/resume + manage actions.
// "+ New deployment" launches the 4-step OnboardingWizard modal.
import React, { useEffect, useState } from 'react';
import { Rocket, Pause, Play, Plus, ChatTeardropText, EnvelopeSimple, Database, ArrowRight, Sparkle } from '@phosphor-icons/react';
import { toast } from 'sonner';
import api from '../../config/api';
import OnboardingWizard from './OnboardingWizard';

const STATUS_CHIP = {
  LIVE:   'bg-emerald-100 text-emerald-700 border-emerald-200',
  SETUP:  'bg-amber-100 text-amber-700 border-amber-200',
  PAUSED: 'bg-rose-100 text-rose-700 border-rose-200',
};

const ROLLUP_TILE = [
  { key: 'total',  label: 'Total',  ring: 'border-slate-200',   accent: 'text-slate-700' },
  { key: 'live',   label: 'Live',   ring: 'border-emerald-200', accent: 'text-emerald-700' },
  { key: 'setup',  label: 'In Setup', ring: 'border-amber-200', accent: 'text-amber-700' },
  { key: 'paused', label: 'Paused', ring: 'border-rose-200',    accent: 'text-rose-700' },
];

export default function DeploymentsTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [busyId, setBusyId] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get('/api/admin/deployments');
      setData(r.data);
    } catch (e) {
      toast.error("Couldn't load deployments");
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const togglePause = async (d) => {
    setBusyId(d.tenant_id);
    try {
      await api.post(`/api/admin/deployments/${d.tenant_id}/toggle`, { pause: d.status !== 'PAUSED' });
      toast.success(d.status === 'PAUSED' ? `${d.workspace_name} resumed` : `${d.workspace_name} paused`);
      await load();
    } catch (e) {
      toast.error('Toggle failed');
    } finally { setBusyId(null); }
  };

  if (loading) return <div data-testid="deployments-loading" className="p-8 text-sm text-slate-500">Loading deployments…</div>;
  if (!data) return <div className="p-8 text-sm text-rose-700">Couldn't load deployments.</div>;

  return (
    <div data-testid="deployments-tab" className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-xl font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Deployments</h2>
          <p className="text-xs text-[#5A4A7A]">Every client workspace running on Aria. Pause, monitor, or onboard a new one.</p>
        </div>
        <button
          type="button"
          onClick={() => setWizardOpen(true)}
          data-testid="deployment-new-btn"
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-gradient-to-r from-[#7C35DC] to-[#C044E0] text-white text-xs font-bold hover:opacity-95 shadow"
        >
          <Plus size={14} weight="bold" /> New deployment
        </button>
      </div>

      {/* Rollup tiles */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="deployments-rollup">
        {ROLLUP_TILE.map((t) => (
          <div key={t.key} className={`bg-white border ${t.ring} rounded-2xl p-4`}>
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{t.label}</div>
            <div className={`text-3xl font-extrabold ${t.accent} mt-1`} data-testid={`rollup-${t.key}`}>{data.rollup?.[t.key] || 0}</div>
          </div>
        ))}
      </div>

      {/* Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3" data-testid="deployments-grid">
        {data.deployments.map((d) => (
          <div
            key={d.tenant_id}
            data-testid={`deployment-card-${d.tenant_id}`}
            className="bg-white border border-slate-200 rounded-2xl p-4 hover:shadow-md transition-shadow"
          >
            <div className="flex items-center justify-between gap-2 mb-2 flex-wrap">
              <div className="min-w-0 flex-1">
                <h3 className="font-extrabold text-sm text-[#1A0A2E] truncate" style={{ fontFamily: 'Plus Jakarta Sans' }}>{d.workspace_name}</h3>
                <p className="text-[11px] text-slate-500 truncate">{d.founder_name || '—'} {d.industry && <> · <span className="italic">{d.industry}</span></>}</p>
              </div>
              <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border ${STATUS_CHIP[d.status]}`} data-testid={`deployment-status-${d.tenant_id}`}>{d.status}</span>
            </div>

            <div className="flex items-center gap-1.5 mb-3 mt-2">
              <Chip on={d.channels.whatsapp} icon={ChatTeardropText} label="WhatsApp" />
              <Chip on={d.channels.email}    icon={EnvelopeSimple}   label="Email" />
              <Chip on={d.channels.crm}      icon={Database}         label="CRM" />
            </div>

            <dl className="grid grid-cols-2 gap-1 text-[11px] mb-3">
              <div><dt className="text-slate-500">Leads</dt><dd className="font-extrabold text-slate-900">{d.leads_total}</dd></div>
              <div><dt className="text-slate-500">Touchpoints / wk</dt><dd className="font-extrabold text-slate-900">{d.touchpoints_this_week}</dd></div>
              <div className="col-span-2"><dt className="text-slate-500">Last activity</dt><dd className="text-slate-700">{d.last_activity_at ? new Date(d.last_activity_at).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' }) : '—'}</dd></div>
            </dl>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => togglePause(d)}
                disabled={busyId === d.tenant_id}
                data-testid={`deployment-toggle-${d.tenant_id}`}
                className={`flex-1 inline-flex items-center justify-center gap-1 px-3 py-2 rounded-lg text-[11px] font-bold ${d.status === 'PAUSED' ? 'bg-emerald-600 text-white hover:bg-emerald-700' : 'bg-amber-50 text-amber-700 border border-amber-200 hover:bg-amber-100'} disabled:opacity-50`}
              >
                {d.status === 'PAUSED' ? <><Play size={12} weight="fill" /> Resume</> : <><Pause size={12} weight="fill" /> Pause</>}
              </button>
              <button
                type="button"
                onClick={() => window.open(`/master-admin?tenant=${d.tenant_id}`, '_blank')}
                data-testid={`deployment-manage-${d.tenant_id}`}
                className="inline-flex items-center gap-1 px-3 py-2 rounded-lg text-[11px] font-bold text-violet-700 hover:bg-violet-50"
              >
                Manage <ArrowRight size={11} weight="bold" />
              </button>
            </div>
          </div>
        ))}
        {data.deployments.length === 0 && (
          <div className="col-span-full bg-white border border-dashed border-slate-300 rounded-2xl p-12 text-center" data-testid="deployments-empty">
            <Sparkle size={28} className="text-violet-600 mx-auto mb-2" weight="duotone" />
            <p className="text-sm text-slate-700">No deployments yet. Click <strong>+ New deployment</strong> to onboard your first client.</p>
          </div>
        )}
      </div>

      {wizardOpen && (
        <OnboardingWizard
          onClose={() => setWizardOpen(false)}
          onLaunched={async () => { setWizardOpen(false); await load(); }}
        />
      )}
    </div>
  );
}

function Chip({ on, icon: Icon, label }) {
  return (
    <div
      title={`${label}: ${on ? 'configured' : 'not configured'}`}
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${on ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-slate-50 text-slate-400 border border-slate-200'}`}
    >
      <Icon size={9} weight="bold" /> {label}
    </div>
  );
}
