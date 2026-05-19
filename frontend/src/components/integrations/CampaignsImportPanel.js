/**
 * CampaignsImportPanel — pull-based Saleshandy + Lemlist lead import.
 *
 * Rendered inside the Integration Hub Manage modal when a tenant opens
 * Saleshandy or Lemlist. Lets them:
 *   1. Test that the pasted API key actually authenticates.
 *   2. Fetch campaigns (or "sequences" in Saleshandy speak).
 *   3. Pick specific campaigns + trigger an import run.
 *   4. Review the latest 5 import logs (fetched / imported / updated / failed).
 *
 * The backend lives in /app/backend/routes/outreach_import.py.
 */
import React, { useEffect, useState } from 'react';
import api from '../../config/api';
import { toast } from 'sonner';
import {
  ArrowsClockwise, CheckCircle, Warning, DownloadSimple, ListChecks,
  PlayCircle, ClockCounterClockwise, Lightning,
} from '@phosphor-icons/react';

const STATUS_COLOR = {
  active: '#16A34A', running: '#16A34A', scheduled: '#0055FF',
  paused: '#D97706', draft: '#9B8AB0', completed: '#5A4A7A', unknown: '#9B8AB0',
};

const fmtDate = (iso) => {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' }); }
  catch { return '—'; }
};

export default function CampaignsImportPanel({ tool, isConnected }) {
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [campaigns, setCampaigns] = useState(null); // null = never fetched, [] = empty
  const [fetching, setFetching] = useState(false);
  const [selected, setSelected] = useState(() => new Set());
  const [importing, setImporting] = useState(false);
  const [logs, setLogs] = useState([]);
  const [showAllLogs, setShowAllLogs] = useState(false);

  const TOOL_LABEL = tool === 'saleshandy' ? 'Saleshandy' : 'Lemlist';

  const loadLogs = async () => {
    try {
      const r = await api.get('/api/integrations/import-logs', { params: { tool, limit: 20 } });
      setLogs(r.data?.logs || []);
    } catch { /* non-fatal */ }
  };

  useEffect(() => { if (isConnected) loadLogs(); /* eslint-disable-next-line */ }, [tool]);

  const testConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const r = await api.post(`/api/integrations/${tool}/test-connection`);
      setTestResult(r.data);
      if (r.data?.ok) {
        toast.success(`${TOOL_LABEL} connection verified — ${r.data.campaigns_found} campaigns found`);
      } else {
        toast.error(r.data?.error || `${TOOL_LABEL} connection failed`);
      }
    } catch (e) {
      setTestResult({ ok: false, error: e?.response?.data?.detail || 'Test failed' });
      toast.error(e?.response?.data?.detail || 'Test failed');
    } finally {
      setTesting(false);
    }
  };

  const fetchCampaigns = async () => {
    setFetching(true);
    try {
      const r = await api.get(`/api/integrations/${tool}/campaigns`);
      const rows = r.data?.campaigns || [];
      setCampaigns(rows);
      setSelected(new Set());
      if (rows.length === 0) {
        toast.info('No campaigns found in this account.');
      } else {
        toast.success(`Fetched ${rows.length} campaigns from ${TOOL_LABEL}`);
      }
    } catch (e) {
      const detail = e?.response?.data?.detail || 'Could not fetch campaigns';
      toast.error(detail);
      setCampaigns([]);
    } finally {
      setFetching(false);
    }
  };

  const toggleSelected = (id) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const selectAll = () => {
    if (!campaigns) return;
    setSelected(new Set(campaigns.map((c) => c.id)));
  };
  const clearSelection = () => setSelected(new Set());

  const runImport = async (mode = 'selected') => {
    if (mode === 'selected' && selected.size === 0) {
      toast.error('Pick at least one campaign or use "Import all active"');
      return;
    }
    setImporting(true);
    try {
      const body = {
        campaign_ids: mode === 'selected' ? Array.from(selected) : [],
        import_mode: mode,
      };
      const r = await api.post(`/api/integrations/${tool}/import-leads`, body);
      const log = r.data?.log || {};
      const t = log.totals || {};
      const fetched = t.fetched || 0;
      const imported = t.imported || 0;
      const updated = t.updated || 0;
      const failed = t.failed || 0;
      const dups = t.duplicates_merged || 0;

      if (fetched === 0) {
        // Either auth got us campaigns but no leads, OR the leads endpoint
        // didn't exist on this Lemlist plan. Either way, the user shouldn't
        // see a generic "0 imported" — call out the real cause.
        const firstFail = (log.failures || [])[0];
        toast.error(
          `${TOOL_LABEL} returned 0 leads for the selected campaigns. ${firstFail?.error || 'Check that the campaign actually contains contacts and that your API key has lead-read scope.'}`,
          { duration: 8000 },
        );
      } else if (imported === 0 && updated === 0) {
        const firstFail = (log.failures || [])[0];
        toast.error(
          `${TOOL_LABEL} fetched ${fetched} leads but couldn't import any. ${firstFail?.error || 'Check the import log for details.'}`,
          { duration: 8000 },
        );
      } else {
        toast.success(
          `${TOOL_LABEL} import complete — fetched ${fetched} · imported ${imported} new · ${updated} updated · ${dups} dupes merged · ${failed} failed`,
          { duration: 7000 },
        );
      }
      loadLogs();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Import failed');
    } finally {
      setImporting(false);
    }
  };

  if (!isConnected) {
    return (
      <div className="p-4 rounded-xl bg-[#FEF3C7] border border-[#D97706]/30 text-xs text-[#92400E]" data-testid="import-panel-not-connected">
        Paste your {TOOL_LABEL} API key above and click <strong>Connect</strong> first — then you can fetch campaigns and import leads.
      </div>
    );
  }

  const visibleLogs = showAllLogs ? logs : logs.slice(0, 3);

  return (
    <div className="space-y-4" data-testid={`campaigns-import-panel-${tool}`}>
      {/* Connection test + fetch */}
      <div className="p-4 rounded-xl border border-[#E0D4F7] bg-[#FAF7FF]">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#7C35DC] flex items-center gap-1.5">
              <Lightning size={11} weight="fill" /> Campaign import
            </div>
            <div className="text-xs text-[#5A4A7A] mt-1">
              Pull campaigns from {TOOL_LABEL}, pick which ones to import, and Aria will normalize + dedupe leads into your workspace.
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={testConnection}
              disabled={testing}
              data-testid={`btn-test-${tool}`}
              className="inline-flex items-center gap-1 px-3 py-1.5 bg-white border border-[#7C35DC]/30 text-[#7C35DC] rounded-lg text-[11px] font-bold hover:bg-[#F4F0FF] disabled:opacity-40"
            >
              <CheckCircle size={11} weight="bold" /> {testing ? 'Testing…' : 'Test connection'}
            </button>
            <button
              type="button"
              onClick={fetchCampaigns}
              disabled={fetching}
              data-testid={`btn-fetch-${tool}`}
              className="inline-flex items-center gap-1 px-3 py-1.5 bg-violet-600 text-white rounded-lg text-[11px] font-bold disabled:opacity-40"
            >
              <ArrowsClockwise size={11} weight="bold" className={fetching ? 'animate-spin' : ''} />
              {fetching ? 'Fetching…' : 'Fetch campaigns'}
            </button>
          </div>
        </div>

        {testResult && (
          <div className={`mt-3 px-3 py-2 rounded-md text-xs ${testResult.ok ? 'bg-[#DCFCE7] border border-[#16A34A]/30 text-[#15803D]' : 'bg-[#FEE2E2] border border-[#DC2626]/30 text-[#DC2626]'}`} data-testid={`test-result-${tool}`}>
            {testResult.ok
              ? <>Connection OK · <strong>{testResult.campaigns_found}</strong> campaigns visible.</>
              : <>Connection failed: {testResult.error}</>
            }
          </div>
        )}
      </div>

      {/* Campaigns table */}
      {campaigns && campaigns.length > 0 && (
        <div className="border border-[#E8E0F5] rounded-xl overflow-hidden" data-testid={`campaigns-table-${tool}`}>
          <div className="flex items-center justify-between px-3 py-2 bg-[#FAF7FF] border-b border-[#E8E0F5]">
            <div className="text-[10px] font-bold uppercase tracking-wider text-[#5A4A7A]">
              {campaigns.length} campaigns · {selected.size} selected
            </div>
            <div className="flex items-center gap-1.5">
              <button type="button" onClick={selectAll} className="text-[10px] font-bold text-[#7C35DC] hover:underline">Select all</button>
              <button type="button" onClick={clearSelection} className="text-[10px] font-bold text-[#9B8AB0] hover:underline">Clear</button>
            </div>
          </div>
          <div className="max-h-72 overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="bg-white sticky top-0">
                <tr className="text-left text-[10px] font-bold uppercase tracking-wider text-[#9B8AB0]">
                  <th className="px-3 py-2 w-8"></th>
                  <th className="px-3 py-2">Campaign</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2 text-right">Leads</th>
                  <th className="px-3 py-2 text-right">Opens</th>
                  <th className="px-3 py-2 text-right">Replies</th>
                </tr>
              </thead>
              <tbody>
                {campaigns.map((c) => {
                  const isSel = selected.has(c.id);
                  const statusColor = STATUS_COLOR[c.status] || '#9B8AB0';
                  return (
                    <tr
                      key={c.id}
                      onClick={() => toggleSelected(c.id)}
                      className={`border-t border-[#F0ECF9] cursor-pointer ${isSel ? 'bg-[#F4F0FF]' : 'hover:bg-[#FAFAFA]'}`}
                      data-testid={`campaign-row-${c.id}`}
                    >
                      <td className="px-3 py-2">
                        <input
                          type="checkbox"
                          checked={isSel}
                          onChange={() => toggleSelected(c.id)}
                          onClick={(e) => e.stopPropagation()}
                          data-testid={`campaign-checkbox-${c.id}`}
                          className="accent-violet-600"
                        />
                      </td>
                      <td className="px-3 py-2">
                        <div className="font-semibold text-[#1A0A2E] truncate max-w-[220px]">{c.name}</div>
                        <div className="text-[9px] font-mono text-[#9B8AB0]">{c.id}</div>
                      </td>
                      <td className="px-3 py-2">
                        <span className="text-[10px] font-bold uppercase" style={{ color: statusColor }}>{c.status}</span>
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-[#1A0A2E]">{c.leads}</td>
                      <td className="px-3 py-2 text-right font-mono text-[#5A4A7A]">{c.opens}</td>
                      <td className="px-3 py-2 text-right font-mono text-[#16A34A]">{c.replies}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="px-3 py-2 bg-[#FAFAFA] border-t border-[#E8E0F5] flex items-center justify-end gap-2 flex-wrap">
            <button
              type="button"
              onClick={() => runImport('active_only')}
              disabled={importing}
              data-testid={`btn-import-active-${tool}`}
              className="inline-flex items-center gap-1 px-3 py-1.5 bg-white border border-[#E8E0F5] text-[#5A4A7A] rounded-lg text-[11px] font-bold disabled:opacity-40"
            >
              <PlayCircle size={11} weight="fill" /> Import all active
            </button>
            <button
              type="button"
              onClick={() => runImport('selected')}
              disabled={importing || selected.size === 0}
              data-testid={`btn-import-selected-${tool}`}
              className="inline-flex items-center gap-1 px-3 py-1.5 bg-violet-600 text-white rounded-lg text-[11px] font-bold disabled:opacity-40"
            >
              <DownloadSimple size={11} weight="bold" className={importing ? 'animate-bounce' : ''} />
              {importing ? 'Importing…' : `Import ${selected.size || ''} selected`}
            </button>
          </div>
        </div>
      )}

      {campaigns && campaigns.length === 0 && (
        <div className="p-4 rounded-xl bg-[#FEF3C7] border border-[#D97706]/30 text-xs text-[#92400E] flex items-center gap-2" data-testid={`no-campaigns-${tool}`}>
          <Warning size={14} weight="fill" />
          <div>
            No campaigns found in this {TOOL_LABEL} account. If you expected campaigns, double-check the API key has the right workspace/permissions.
          </div>
        </div>
      )}

      {/* Import logs */}
      {logs.length > 0 && (
        <div className="border border-[#E8E0F5] rounded-xl overflow-hidden" data-testid={`import-logs-${tool}`}>
          <div className="flex items-center justify-between px-3 py-2 bg-[#FAF7FF] border-b border-[#E8E0F5]">
            <div className="text-[10px] font-bold uppercase tracking-wider text-[#5A4A7A] flex items-center gap-1.5">
              <ClockCounterClockwise size={11} weight="fill" /> Recent imports
            </div>
            {logs.length > 3 && (
              <button type="button" onClick={() => setShowAllLogs(!showAllLogs)} className="text-[10px] font-bold text-[#7C35DC] hover:underline">
                {showAllLogs ? 'Show less' : `Show all ${logs.length}`}
              </button>
            )}
          </div>
          <div className="divide-y divide-[#F0ECF9]">
            {visibleLogs.map((log) => {
              const t = log.totals || {};
              const statusBadge = log.status === 'completed'
                ? { color: '#16A34A', bg: '#DCFCE7', label: 'OK' }
                : log.status === 'partial'
                ? { color: '#D97706', bg: '#FEF3C7', label: 'Partial' }
                : { color: '#DC2626', bg: '#FEE2E2', label: 'Failed' };
              return (
                <div key={log.id} className="px-3 py-2.5" data-testid={`import-log-${log.id}`}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span
                          className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded"
                          style={{ color: statusBadge.color, background: statusBadge.bg }}
                        >
                          {statusBadge.label}
                        </span>
                        <span className="text-xs font-semibold text-[#1A0A2E]">
                          {log.campaigns_selected} campaign{log.campaigns_selected === 1 ? '' : 's'} · {log.import_mode}
                        </span>
                      </div>
                      <div className="text-[10px] text-[#5A4A7A] mt-1 font-mono">
                        fetched <strong>{t.fetched || 0}</strong> · imported <strong className="text-[#16A34A]">{t.imported || 0}</strong> · updated <strong className="text-[#0055FF]">{t.updated || 0}</strong> · duplicates <strong>{t.duplicates_merged || 0}</strong> · failed <strong className="text-[#DC2626]">{t.failed || 0}</strong>
                      </div>
                      <div className="text-[10px] text-[#9B8AB0] mt-0.5">{fmtDate(log.created_at)}</div>
                      {/* Show the first failure reason inline so users don't need to ping support. */}
                      {(log.failures || []).length > 0 && (
                        <div className="mt-1.5 text-[10px] text-rose-700 bg-rose-50 border border-rose-200 rounded px-2 py-1" data-testid={`import-log-failure-${log.id}`}>
                          <strong>First failure:</strong> {log.failures[0]?.error || 'unknown'}
                          {log.failures.length > 1 && <> (+{log.failures.length - 1} more)</>}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {logs.length === 0 && isConnected && (
        <div className="text-[11px] text-[#9B8AB0] italic flex items-center gap-1.5" data-testid={`no-logs-${tool}`}>
          <ListChecks size={11} /> No imports yet — fetch campaigns above and pick which ones to pull in.
        </div>
      )}
    </div>
  );
}
