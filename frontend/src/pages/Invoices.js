import React, { useEffect, useState } from 'react';
import { FileText, DownloadSimple, Receipt, FileCsv } from '@phosphor-icons/react';
import { toast } from 'sonner';
import api from '../config/api';

export default function Invoices() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    api.get('/api/billing/invoices')
      .then((r) => setRows(r.data?.invoices || []))
      .catch(() => toast.error('Could not load invoices'))
      .finally(() => setLoading(false));
  }, []);

  const download = async (inv) => {
    try {
      const r = await api.get(`/api/billing/invoices/${inv.id}/pdf`, { responseType: 'blob' });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${inv.invoice_no.replace(/\//g, '-')}.pdf`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      toast.error('Could not download invoice');
    }
  };

  const exportCsv = async () => {
    setExporting(true);
    try {
      const r = await api.get('/api/billing/invoices/export.csv', { responseType: 'blob' });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `genleadai-invoices-${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
      toast.success('Invoice CSV exported');
    } catch (e) {
      toast.error('Could not export CSV');
    } finally {
      setExporting(false);
    }
  };

  return (
    <div data-testid="invoices-page" className="max-w-5xl mx-auto px-6 py-8">
      <div className="mb-6 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-violet-600 font-semibold mb-2">Billing</p>
          <h1 className="text-3xl font-semibold text-slate-900 mb-1">Tax invoices</h1>
          <p className="text-slate-600 text-sm">GST-compliant PDFs for every plan upgrade. Download any time for filing.</p>
        </div>
        {rows.length > 0 && (
          <button
            type="button"
            onClick={exportCsv}
            disabled={exporting}
            data-testid="invoices-export-csv"
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg border border-slate-200 bg-white text-slate-700 text-xs font-semibold hover:bg-slate-50 hover:border-slate-300 disabled:opacity-50"
          >
            <FileCsv size={14} weight="duotone" /> {exporting ? 'Exporting…' : 'Export all (CSV)'}
          </button>
        )}
      </div>

      {loading ? (
        <div className="text-center py-16 text-slate-400">Loading invoices…</div>
      ) : rows.length === 0 ? (
        <div data-testid="invoices-empty" className="bg-white/70 backdrop-blur-md border border-slate-200 rounded-3xl p-12 text-center">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-violet-50 text-violet-600 mb-4">
            <Receipt size={28} weight="duotone" />
          </div>
          <h3 className="text-lg font-semibold text-slate-900 mb-1">No invoices yet</h3>
          <p className="text-slate-600 text-sm max-w-md mx-auto">As soon as you upgrade your plan, your tax invoice will land here automatically — and in your email.</p>
        </div>
      ) : (
        <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-[10px] uppercase tracking-wider text-slate-500 font-semibold">
              <tr>
                <th className="px-4 py-3 text-left">Invoice #</th>
                <th className="px-4 py-3 text-left">Date</th>
                <th className="px-4 py-3 text-left">Description</th>
                <th className="px-4 py-3 text-right">Total</th>
                <th className="px-4 py-3 text-right">GST</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((inv) => (
                <tr key={inv.id} data-testid={`invoice-row-${inv.id}`} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-3 font-mono text-xs text-slate-900">{inv.invoice_no}</td>
                  <td className="px-4 py-3 text-xs text-slate-700">{inv.issued_at_human}</td>
                  <td className="px-4 py-3 text-xs text-slate-700">{inv.item_description}</td>
                  <td className="px-4 py-3 text-right text-sm font-semibold text-slate-900">₹ {inv.total.toFixed(2)}</td>
                  <td className="px-4 py-3 text-right text-xs text-slate-500">
                    {inv.igst > 0 ? `IGST ₹${inv.igst.toFixed(2)}` : `CGST+SGST ₹${(inv.cgst + inv.sgst).toFixed(2)}`}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      type="button"
                      onClick={() => download(inv)}
                      data-testid={`invoice-download-${inv.id}`}
                      className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-slate-900 text-white text-[11px] font-medium hover:bg-slate-800"
                    >
                      <DownloadSimple size={11} weight="bold" /> PDF
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
