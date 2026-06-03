import { useEffect, useState, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Plus, Upload, MagnifyingGlass, X, Brain, Sparkle } from '@phosphor-icons/react';
import { toast } from 'sonner';
import { ptApi, PageHeader, EmptyState, StageBadge, SOURCE_LABELS, fmtDate } from '../shared';
import api from '../../config/api';

const LeadFeed = ({ embedded = false }) => {
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ stage: '', source: '', q: '', score_min: '', score_max: '' });
  const [showAdd, setShowAdd] = useState(false);
  const [showCsv, setShowCsv] = useState(false);
  const [batchBusy, setBatchBusy] = useState(false);
  const [batchResult, setBatchResult] = useState(null);
  const navigate = useNavigate();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      Object.entries(filters).forEach(([k, v]) => { if (v !== '' && v != null) params[k] = v; });
      const r = await ptApi.get('/api/pt/leads', { params });
      setLeads(r.data.leads || []);
    } catch { toast.error('Could not load leads'); }
    finally { setLoading(false); }
  }, [filters]);

  useEffect(() => { load(); }, [load]);

  // iter103 — Real-time polling. Every 10s, fetch /realtime/since and bump
  // the live-badge count when new leads arrive. Auto-refreshes the table
  // so users don't have to manually reload.
  const [liveCursor, setLiveCursor] = useState(new Date().toISOString());
  const [newSinceLastSeen, setNewSinceLastSeen] = useState(0);
  useEffect(() => {
    let timer = null;
    const poll = async () => {
      try {
        const r = await ptApi.get('/api/realtime/since', { params: { ts: liveCursor } });
        const cnt = r.data.lead_count || 0;
        if (cnt > 0) {
          setNewSinceLastSeen(n => n + cnt);
          await load();  // refresh table
        }
        if (r.data.now) setLiveCursor(r.data.now);
      } catch { /* silent */ }
      timer = setTimeout(poll, 10000);
    };
    timer = setTimeout(poll, 10000);
    return () => { if (timer) clearTimeout(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [liveCursor]);
  const dismissLiveBadge = () => setNewSinceLastSeen(0);

  // iter126 — One-click "Scan all hot leads" — uses the new global
  // /api/intel/scan-hot endpoint which covers both leads + pt_leads, fires
  // crawls in the background, and returns the queued count instantly.
  // iter134 — also returns a batch_id we can poll for live progress so
  // the founder gets a "12/28 done" toast instead of radio silence.
  const runBatchIntel = async () => {
    setBatchBusy(true);
    setBatchResult(null);
    try {
      const r = await api.post('/api/intel/scan-hot', {
        min_icp_score: 15,
        refresh: false,
        max_leads: 50,
      });
      const queued = r.data.queued || 0;
      const batchId = r.data.batch_id;
      const normalised = {
        processed: queued,
        succeeded: queued,
        failed: 0,
        aborted: false,
        threshold: r.data.threshold,
        leads: r.data.leads || [],
        batch_id: batchId,
      };
      setBatchResult(normalised);
      if (queued === 0) {
        toast.info(r.data.message || 'No hot leads matched.');
        return;
      }
      // iter134 — sticky progress toast that polls every 4s until the
      // batch finishes. Sonner returns an id we use to update + dismiss.
      const tid = toast.loading(`Scanning ${queued} hot leads… (0/${queued})`, { duration: Infinity });
      const poll = async () => {
        try {
          const s = await api.get(`/api/intel/scan-hot/status/${batchId}`);
          const done = (s.data.completed || 0) + (s.data.failed || 0);
          const total = s.data.total || queued;
          if (s.data.is_finished) {
            const succeeded = s.data.completed || 0;
            const failed = s.data.failed || 0;
            toast.dismiss(tid);
            if (failed === 0) {
              toast.success(`Intel scan complete — ${succeeded}/${total} succeeded`);
            } else if (succeeded === 0) {
              toast.error(`Intel scan failed — ${failed}/${total} errored. Check RapidAPI subscription.`);
            } else {
              toast.warning(`Intel scan complete — ${succeeded} succeeded, ${failed} failed.`);
            }
            return;
          }
          toast.loading(`Scanning hot leads… (${done}/${total})`, { id: tid, duration: Infinity });
          setTimeout(poll, 4000);
        } catch {
          toast.dismiss(tid);
        }
      };
      // First poll runs after 2s so the user sees the initial spinner.
      setTimeout(poll, 2000);
    } catch (err) {
      const detail = err.response?.data?.detail || 'Batch intel failed';
      if (err.response?.status === 503) {
        toast.error('Connect RapidAPI or Serper on /app/integrations first');
        setBatchResult({ aborted: true, reason: detail });
      } else {
        toast.error(detail);
      }
    } finally {
      setBatchBusy(false);
    }
  };

  return (
    <div data-testid="pt-leadfeed-page">
      {!embedded && <PageHeader title="Lead Feed" subtitle="Real leads who have engaged. No samples."
        right={
          <div className="flex items-center gap-2">
            {newSinceLastSeen > 0 && (
              <button
                onClick={dismissLiveBadge}
                data-testid="pt-leadfeed-live-badge"
                className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.18em] text-emerald-700 bg-emerald-50 ring-1 ring-emerald-200 rounded-full px-2.5 py-1 animate-pulse"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                {newSinceLastSeen} new
              </button>
            )}
            <button onClick={runBatchIntel} disabled={batchBusy} data-testid="scan-all-hot-leads-btn"
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-semibold text-white disabled:opacity-50"
              style={{ background: 'linear-gradient(135deg, #4C1D95 0%, #7C35DC 100%)' }}>
              <Brain size={14} weight="duotone" /> {batchBusy ? 'Queuing scans…' : 'Scan engaged leads'}
            </button>
            <button onClick={() => setShowCsv(true)} data-testid="import-csv-btn"
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-semibold text-[#7C35DC] border border-[#7C35DC]/30 hover:bg-[#7C35DC]/5">
              <Upload size={14} weight="bold" /> Upload CSV
            </button>
            <button onClick={() => setShowAdd(true)} data-testid="pt-leadfeed-add-btn"
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-semibold text-white" style={{ background: '#7C35DC' }}>
              <Plus size={14} weight="bold" /> Add lead
            </button>
          </div>
        }
      />}

      {/* Filters */}
      <div className="bg-white border border-[#E2E8F0] rounded-lg p-3 flex items-center gap-2 flex-wrap mb-4" data-testid="pt-leadfeed-filters">
        <div className="relative flex-1 min-w-[200px]">
          <MagnifyingGlass size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#94A3B8]" />
          <input value={filters.q} onChange={(e) => setFilters({ ...filters, q: e.target.value })} placeholder="Search name, email, company"
            data-testid="pt-leadfeed-search"
            className="w-full pl-7 pr-3 py-1.5 text-sm border border-[#E2E8F0] rounded-md outline-none focus:ring-2 focus:ring-[#C044E0]/20" />
        </div>
        <select value={filters.stage} onChange={(e) => setFilters({ ...filters, stage: e.target.value })}
          data-testid="pt-leadfeed-filter-stage"
          className="text-sm border border-[#E2E8F0] rounded-md px-2 py-1.5 outline-none">
          <option value="">All stages</option>
          <option value="cold">Cold</option><option value="warm">Warm</option><option value="hot">Hot</option><option value="engaged">Engaged</option><option value="session_pilot">Session/Pilot</option>
        </select>
        <select value={filters.source} onChange={(e) => setFilters({ ...filters, source: e.target.value })}
          data-testid="pt-leadfeed-filter-source"
          className="text-sm border border-[#E2E8F0] rounded-md px-2 py-1.5 outline-none">
          <option value="">All sources</option>
          {Object.entries(SOURCE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <input type="number" value={filters.score_min} onChange={(e) => setFilters({ ...filters, score_min: e.target.value })} placeholder="Score min"
          className="w-24 text-sm border border-[#E2E8F0] rounded-md px-2 py-1.5 outline-none" />
        <input type="number" value={filters.score_max} onChange={(e) => setFilters({ ...filters, score_max: e.target.value })} placeholder="Score max"
          className="w-24 text-sm border border-[#E2E8F0] rounded-md px-2 py-1.5 outline-none" />
      </div>

      {/* iter114 Batch 4 — Batch intel result banner */}
      {batchResult && (
        <div className="mb-4 bg-white border border-[#7C35DC]/30 rounded-lg p-3" data-testid="pt-leadfeed-batch-result" style={{ background: '#FAF7FF' }}>
          <div className="flex items-center justify-between gap-2 mb-1.5">
            <div className="flex items-center gap-1.5">
              <Sparkle size={13} weight="fill" className="text-[#7C35DC]" />
              <span className="text-xs font-bold uppercase tracking-[0.16em] text-[#7C35DC]">Batch intel run</span>
            </div>
            <button onClick={() => setBatchResult(null)} className="text-[#94A3B8] hover:text-[#0F172A]" data-testid="pt-leadfeed-batch-dismiss">
              <X size={12} />
            </button>
          </div>
          {batchResult.aborted ? (
            <div className="text-sm text-[#DC2626]">Aborted: {batchResult.reason}</div>
          ) : (
            <div className="text-sm text-[#0F172A]">
              <span className="font-bold text-emerald-600">{batchResult.succeeded}</span> succeeded
              {batchResult.failed > 0 && <> · <span className="font-bold text-[#DC2626]">{batchResult.failed}</span> failed</>}
              {batchResult.processed === 0 && <> · all hot leads already enriched</>}
              {(batchResult.results || []).slice(0, 5).length > 0 && (
                <div className="mt-1.5 grid grid-cols-1 sm:grid-cols-2 gap-x-3 gap-y-0.5">
                  {batchResult.results.slice(0, 6).map((r, i) => (
                    <div key={i} className="text-xs flex items-center gap-1.5" data-testid={`pt-leadfeed-batch-row-${i}`}>
                      <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${r.status === 'ok' ? 'bg-emerald-500' : 'bg-[#DC2626]'}`} />
                      <span className="font-semibold truncate flex-1">{r.name}</span>
                      {r.status === 'ok' && <span className="text-[#7C35DC] font-bold">{r.fit_score}/100</span>}
                      {r.status !== 'ok' && <span className="text-[#DC2626] truncate">{r.reason || r.status}</span>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Table or empty */}
      {loading ? (
        <div className="text-sm text-[#64748B]">Loading…</div>
      ) : leads.length === 0 ? (
        <EmptyState
          title="No leads have interacted yet."
          message="Upload a CSV of real prospects, or wait for engagement events to flow in from Saleshandy / Lemlist / newsletter."
          cta={
            <div className="flex items-center justify-center gap-2">
              <button onClick={() => setShowCsv(true)} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-semibold text-white" style={{ background: '#7C35DC' }} data-testid="empty-cta-upload">Upload CSV</button>
              <Link to="/app/integrations" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-semibold text-[#7C35DC] border border-[#7C35DC]/30">Configure integrations</Link>
            </div>
          }
        />
      ) : (
        <div className="bg-white border border-[#E2E8F0] rounded-lg overflow-x-auto" data-testid="pt-leadfeed-table">
          <table className="w-full text-sm">
            <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0]">
              <tr>
                {['Lead', 'Company', 'Title', 'Source', 'Latest signal', 'Score', 'Stage', 'Owner', 'Last activity'].map(h => (
                  <th key={h} className="px-3 py-2 text-left text-[10px] font-bold uppercase tracking-[0.14em] text-[#64748B]">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {leads.map(l => (
                <tr key={l.id} onClick={() => navigate(`/app/leads/${l.id}`)}
                  data-testid={`lead-row-${l.id}`}
                  className="border-b border-[#F1F5F9] hover:bg-[#F8FAFC] cursor-pointer">
                  <td className="px-3 py-2.5">
                    <div className="font-semibold text-[#0F172A]">{l.first_name} {l.last_name}</div>
                    <div className="text-xs text-[#64748B]">{l.email}</div>
                  </td>
                  <td className="px-3 py-2.5 text-[#0F172A]">{l.company_name || '—'}</td>
                  <td className="px-3 py-2.5 text-[#475569]">{l.title || '—'}</td>
                  <td className="px-3 py-2.5 text-[#475569]">{SOURCE_LABELS[l.source] || l.source || '—'}</td>
                  <td className="px-3 py-2.5 text-[#475569]">{l.latest_signal || '—'}</td>
                  <td className="px-3 py-2.5 font-bold text-[#0F172A]">{l.score ?? 0}</td>
                  <td className="px-3 py-2.5"><StageBadge stage={l.stage} /></td>
                  <td className="px-3 py-2.5 text-[#475569]">{l.owner || '—'}</td>
                  <td className="px-3 py-2.5 text-[#64748B] text-xs">{fmtDate(l.last_activity_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showAdd && <AddLeadModal onClose={() => setShowAdd(false)} onSaved={() => { setShowAdd(false); load(); }} />}
      {showCsv && <CsvModal onClose={() => setShowCsv(false)} onDone={() => { setShowCsv(false); load(); }} />}
    </div>
  );
};

const AddLeadModal = ({ onClose, onSaved }) => {
  const [f, setF] = useState({ first_name: '', last_name: '', email: '', company_name: '', title: '', linkedin_url: '', source: 'manual', industry: '', employee_count: '', geography: '', icp_fit: 'match', owner: 'Content Vista' });
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    if (!f.first_name || !f.email) { toast.error('First name and email required'); return; }
    setBusy(true);
    try {
      const payload = { ...f };
      if (payload.employee_count === '') delete payload.employee_count;
      else payload.employee_count = parseInt(payload.employee_count, 10);
      await ptApi.post('/api/pt/leads', payload);
      toast.success('Lead added');
      onSaved();
    } catch (err) { toast.error(err.response?.data?.detail || 'Could not add'); }
    finally { setBusy(false); }
  };
  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={onClose} data-testid="pt-add-lead-modal">
      <div className="bg-white rounded-xl border border-[#E2E8F0] w-full max-w-lg" onClick={(e) => e.stopPropagation()}>
        <div className="px-5 py-4 border-b border-[#E2E8F0] flex items-center justify-between">
          <h3 className="text-base font-bold text-[#0F172A]" style={{ fontFamily: 'Space Grotesk, Inter' }}>Add lead</h3>
          <button onClick={onClose}><X size={16} className="text-[#64748B]" /></button>
        </div>
        <div className="p-5 grid grid-cols-2 gap-3">
          <Input label="First name *" value={f.first_name} onChange={(v) => setF({ ...f, first_name: v })} testid="add-firstname" />
          <Input label="Last name" value={f.last_name} onChange={(v) => setF({ ...f, last_name: v })} testid="add-lastname" />
          <Input label="Email *" value={f.email} onChange={(v) => setF({ ...f, email: v })} testid="add-email" full />
          <Input label="Company" value={f.company_name} onChange={(v) => setF({ ...f, company_name: v })} testid="add-company" />
          <Input label="Title" value={f.title} onChange={(v) => setF({ ...f, title: v })} testid="add-title" />
          <Input label="LinkedIn URL" value={f.linkedin_url} onChange={(v) => setF({ ...f, linkedin_url: v })} testid="add-linkedin" full />
          <Input label="Industry" value={f.industry} onChange={(v) => setF({ ...f, industry: v })} testid="add-industry" />
          <Input label="Employee count" value={f.employee_count} onChange={(v) => setF({ ...f, employee_count: v })} testid="add-employees" />
          <Input label="Geography" value={f.geography} onChange={(v) => setF({ ...f, geography: v })} testid="add-geo" />
          <div className="col-span-1">
            <label className="block text-[10px] font-bold uppercase tracking-[0.16em] text-[#64748B] mb-1">ICP fit</label>
            <select value={f.icp_fit} onChange={(e) => setF({ ...f, icp_fit: e.target.value })} className="w-full text-sm border border-[#E2E8F0] rounded-md px-2 py-1.5">
              <option value="match">Match</option><option value="partial">Partial</option><option value="outside">Outside</option>
            </select>
          </div>
        </div>
        <div className="px-5 py-3 border-t border-[#E2E8F0] flex justify-end gap-2 bg-[#F8FAFC]">
          <button onClick={onClose} className="px-3 py-1.5 text-sm font-semibold text-[#475569]">Cancel</button>
          <button onClick={submit} disabled={busy} data-testid="pt-add-lead-save"
            className="px-4 py-1.5 text-sm font-semibold text-white rounded-md disabled:opacity-50" style={{ background: '#7C35DC' }}>
            {busy ? 'Saving…' : 'Save lead'}
          </button>
        </div>
      </div>
    </div>
  );
};

const Input = ({ label, value, onChange, testid, full }) => (
  <div className={full ? 'col-span-2' : ''}>
    <label className="block text-[10px] font-bold uppercase tracking-[0.16em] text-[#64748B] mb-1">{label}</label>
    <input value={value} onChange={(e) => onChange(e.target.value)} data-testid={testid}
      className="w-full text-sm border border-[#E2E8F0] rounded-md px-2 py-1.5 outline-none focus:ring-2 focus:ring-[#C044E0]/20" />
  </div>
);

const CsvModal = ({ onClose, onDone }) => {
  const [parsing, setParsing] = useState(false);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);

  const onFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setParsing(true);
    try {
      const Papa = (await import('papaparse')).default;
      Papa.parse(file, {
        header: true, skipEmptyLines: true,
        complete: (res) => {
          setPreview(res.data);
          setParsing(false);
        },
        error: (err) => { toast.error('CSV parse error: ' + err.message); setParsing(false); },
      });
    } catch { setParsing(false); toast.error('Parser unavailable'); }
  };

  const submit = async () => {
    if (!preview || preview.length === 0) return;
    setBusy(true);
    try {
      const r = await ptApi.post('/api/pt/leads/bulk', { leads: preview });
      toast.success(`Imported ${r.data.created} leads · ${r.data.failed} skipped`);
      onDone();
    } catch (err) { toast.error(err.response?.data?.detail || 'Import failed'); }
    finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={onClose} data-testid="pt-csv-modal">
      <div className="bg-white rounded-xl border border-[#E2E8F0] w-full max-w-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="px-5 py-4 border-b border-[#E2E8F0] flex items-center justify-between">
          <h3 className="text-base font-bold text-[#0F172A]" style={{ fontFamily: 'Space Grotesk, Inter' }}>Upload leads CSV</h3>
          <button onClick={onClose}><X size={16} /></button>
        </div>
        <div className="p-5 space-y-3">
          <div className="text-xs text-[#64748B]">
            Required: <code>email</code>. Optional columns: <code>first_name, last_name, company, title, linkedin_url, industry, employee_count, geography, icp_fit, source, latest_signal, score, last_activity_date, notes, owner</code>.
          </div>
          <input type="file" accept=".csv" onChange={onFile} data-testid="pt-csv-input"
            className="block w-full text-sm border border-dashed border-[#CBD5E1] rounded-lg p-4 cursor-pointer" />
          {parsing && <div className="text-sm text-[#64748B]">Parsing…</div>}
          {preview && (
            <div className="border border-[#E2E8F0] rounded-md overflow-hidden">
              <div className="bg-[#F8FAFC] px-3 py-2 text-[10px] font-bold uppercase tracking-[0.14em] text-[#64748B] border-b border-[#E2E8F0]">Preview · {preview.length} rows</div>
              <div className="max-h-56 overflow-auto p-2 text-xs">
                {preview.slice(0, 5).map((row, i) => (
                  <div key={i} className="text-[#475569] py-1 border-b border-[#F1F5F9] last:border-0">
                    <span className="font-semibold text-[#0F172A]">{row.first_name} {row.last_name}</span>
                    <span className="text-[#94A3B8]"> · {row.email} · {row.company || row.company_name}</span>
                  </div>
                ))}
                {preview.length > 5 && <div className="text-[#94A3B8] text-[10px] mt-1">…and {preview.length - 5} more</div>}
              </div>
            </div>
          )}
        </div>
        <div className="px-5 py-3 border-t border-[#E2E8F0] flex justify-end gap-2 bg-[#F8FAFC]">
          <button onClick={onClose} className="px-3 py-1.5 text-sm font-semibold text-[#475569]">Cancel</button>
          <button onClick={submit} disabled={!preview || busy} data-testid="pt-csv-import-btn"
            className="px-4 py-1.5 text-sm font-semibold text-white rounded-md disabled:opacity-50" style={{ background: '#7C35DC' }}>
            {busy ? 'Importing…' : `Import ${preview?.length || 0} rows`}
          </button>
        </div>
      </div>
    </div>
  );
};

export default LeadFeed;
