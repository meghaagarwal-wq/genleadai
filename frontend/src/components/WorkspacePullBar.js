/**
 * WorkspacePullBar — top action bar shown on Command Center, Instinct,
 * and Automation pages.
 *
 * Reads /api/pt/integrations and renders a "Pull from <X>" outlined button
 * only for integrations the workspace has connected AND that support a
 * manual pull. Always shows "Aria rescore leads" as the trailing action.
 *
 * When no integrations are connected → single "Connect an integration →"
 * link to /app/integrations.
 *
 * Buttons that hit a route the backend doesn't implement yet show a
 * "Coming soon" toast (per spec choice 2b).
 */
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { Download, EnvelopeOpen, Lightning, Plugs, ArrowRight } from '@phosphor-icons/react';
import { ptApi } from '../workspace/shared';

// What manual-pull endpoint to call for each provider. If a provider has
// no entry here, the button still appears (when connected) but click
// shows a "Coming soon" toast.
const PULL_ENDPOINTS = {
  saleshandy: { url: '/api/pt/integrations/saleshandy/pull-leads', body: { max_prospects: 50, auto_score: true } },
  lemlist:    { url: '/api/pt/integrations/lemlist/pull-leads',    body: { max_campaigns: 5, max_per_campaign: 25, auto_score: true } },
};

const PROVIDER_LABEL = {
  saleshandy: 'Saleshandy', lemlist: 'Lemlist', instantly: 'Instantly', smartlead: 'Smartlead',
  meta_ads: 'Meta Ads', google_ads: 'Google Ads', linkedin_ads: 'LinkedIn Ads',
  gmail: 'Gmail', outlook: 'Outlook', apollo: 'Apollo',
};

const WorkspacePullBar = ({ onPullSuccess }) => {
  const [connected, setConnected] = useState(null);  // null = loading, [] = none
  const [busy, setBusy] = useState({});

  useEffect(() => {
    let alive = true;
    ptApi.get('/api/pt/integrations')
      .then((r) => {
        if (!alive) return;
        const all = [...(r.data.primary || []), ...(r.data.future || [])];
        setConnected(all.filter((x) => x.connected && PROVIDER_LABEL[x.name]));
      })
      .catch(() => { if (alive) setConnected([]); });
    return () => { alive = false; };
  }, []);

  const doPull = async (provider) => {
    const cfg = PULL_ENDPOINTS[provider];
    if (!cfg) {
      toast.info(`Pull from ${PROVIDER_LABEL[provider]} — coming soon`);
      return;
    }
    setBusy((b) => ({ ...b, [provider]: true }));
    try {
      const r = await ptApi.post(cfg.url, cfg.body);
      const d = r.data || {};
      toast.success(d.message || `Imported ${d.imported ?? 0} new lead(s) from ${PROVIDER_LABEL[provider]}`, { duration: 6000 });
      onPullSuccess?.();
    } catch (e) {
      toast.error(e.response?.data?.detail || `${PROVIDER_LABEL[provider]} pull failed`);
    } finally {
      setBusy((b) => ({ ...b, [provider]: false }));
    }
  };

  const rescore = async () => {
    setBusy((b) => ({ ...b, _rescore: true }));
    try {
      const r = await ptApi.post('/api/pt/leads/rescore', { max_leads: 100, only_stage: null, only_score_zero: false });
      const d = r.data || {};
      toast.success(`Aria rescored ${d.rescored ?? 0} leads — ${d.by_tier?.hot ?? 0} hot · ${d.by_tier?.warm ?? 0} warm · ${d.by_tier?.cold ?? 0} cold`, { duration: 7000 });
      onPullSuccess?.();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Rescore failed');
    } finally {
      setBusy((b) => ({ ...b, _rescore: false }));
    }
  };

  if (connected === null) return <div className="text-xs text-[#94A3B8]" data-testid="workspace-pullbar-loading">Loading integrations…</div>;
  if (connected.length === 0) {
    return (
      <Link
        to="/app/integrations"
        data-testid="workspace-pullbar-connect"
        className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-semibold border border-[#7C35DC] text-[#7C35DC] hover:bg-[#7C35DC]/8"
      >
        <Plugs size={14} weight="fill" /> Connect an integration <ArrowRight size={12} weight="bold" />
      </Link>
    );
  }
  return (
    <div className="flex items-center gap-2 flex-wrap" data-testid="workspace-pullbar">
      {connected.map((c) => {
        const Icon = c.name === 'saleshandy' ? EnvelopeOpen : Download;
        return (
          <button
            key={c.name}
            onClick={() => doPull(c.name)}
            disabled={busy[c.name]}
            data-testid={`workspace-pull-${c.name}`}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-semibold border border-[#7C35DC] text-[#7C35DC] hover:bg-[#7C35DC]/8 disabled:opacity-50"
          >
            <Icon size={14} weight="fill" /> {busy[c.name] ? 'Pulling…' : `Pull from ${PROVIDER_LABEL[c.name]}`}
          </button>
        );
      })}
      <button
        onClick={rescore}
        disabled={busy._rescore}
        data-testid="workspace-rescore"
        className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-semibold border border-[#16A34A] text-[#16A34A] hover:bg-[#16A34A]/8 disabled:opacity-50"
      >
        <Lightning size={14} weight="fill" /> {busy._rescore ? 'Scoring…' : 'Aria rescore leads'}
      </button>
    </div>
  );
};

export default WorkspacePullBar;
