/**
 * VoiceTraining — iter131
 *
 * Route: /app/voice-training
 *
 * Founders paste 3–10 of their best past WhatsApps / emails / LinkedIn DMs.
 * Active seeds are stitched into the compose_message system prompt as
 * TONE EXAMPLES so every "Draft with ARIA" press sounds like the founder
 * instead of generic ARIA.
 *
 * Backend wiring lives in /app/backend/routes/voice_seeds.py.
 */
import { useEffect, useState, useCallback } from 'react';
import {
  Sparkle, ChatCircleText, EnvelopeSimple, LinkedinLogo, Lightning,
  Plus, TrashSimple, FloppyDisk, Eye, EyeSlash,
} from '@phosphor-icons/react';
import { toast } from 'sonner';
import api from '../../config/api';

const CHANNEL_OPTIONS = [
  { id: 'any',      label: 'Any channel', Icon: Lightning },
  { id: 'whatsapp', label: 'WhatsApp',    Icon: ChatCircleText },
  { id: 'email',    label: 'Email',       Icon: EnvelopeSimple },
  { id: 'linkedin', label: 'LinkedIn',    Icon: LinkedinLogo },
];

const VoiceTraining = () => {
  const [seeds, setSeeds] = useState([]);
  const [maxSeeds, setMaxSeeds] = useState(10);
  const [loading, setLoading] = useState(true);
  const [showPreview, setShowPreview] = useState(false);
  const [previewBlock, setPreviewBlock] = useState('');
  const [previewChannel, setPreviewChannel] = useState('any');

  // Draft new-seed state
  const [newChannel, setNewChannel] = useState('any');
  const [newText, setNewText] = useState('');
  const [newLabel, setNewLabel] = useState('');
  const [adding, setAdding] = useState(false);

  const fetchSeeds = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get('/api/voice-seeds');
      setSeeds(r.data?.seeds || []);
      setMaxSeeds(r.data?.max_seeds || 10);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Could not load seeds');
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchSeeds(); }, [fetchSeeds]);

  const addSeed = async () => {
    if (newText.trim().length < 10) {
      toast.error('Paste at least 10 characters');
      return;
    }
    setAdding(true);
    try {
      await api.post('/api/voice-seeds', {
        channel: newChannel,
        text: newText.trim(),
        label: newLabel.trim() || null,
        active: true,
      });
      toast.success('Voice sample saved — ARIA will use this on the next draft');
      setNewText('');
      setNewLabel('');
      setNewChannel('any');
      fetchSeeds();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Could not save sample');
    } finally { setAdding(false); }
  };

  const toggleActive = async (seed) => {
    try {
      await api.patch(`/api/voice-seeds/${seed.id}`, { active: !seed.active });
      setSeeds((rows) => rows.map((r) => (r.id === seed.id ? { ...r, active: !seed.active } : r)));
    } catch (e) {
      toast.error('Toggle failed');
    }
  };

  const deleteSeed = async (seed) => {
    if (!window.confirm('Delete this voice sample? ARIA will stop using it.')) return;
    try {
      await api.delete(`/api/voice-seeds/${seed.id}`);
      setSeeds((rows) => rows.filter((r) => r.id !== seed.id));
      toast.success('Removed');
    } catch (e) {
      toast.error('Delete failed');
    }
  };

  const loadPreview = async (channel) => {
    setPreviewChannel(channel);
    try {
      const r = await api.get('/api/voice-seeds/preview', { params: { channel } });
      setPreviewBlock(r.data?.tone_block || '(no active seeds for this channel — ARIA falls back to default voice)');
      setShowPreview(true);
    } catch (e) {
      toast.error('Preview failed');
    }
  };

  const atCap = seeds.length >= maxSeeds;
  const activeCount = seeds.filter((s) => s.active).length;

  return (
    <div className="space-y-5 max-w-[1200px] mx-auto" data-testid="voice-training-page" style={{ color: 'var(--theme-text)' }}>
      {/* Header */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold leading-tight" style={{ fontFamily: 'Space Grotesk, Inter', letterSpacing: '-0.02em' }}>
            <Sparkle size={20} weight="fill" className="inline-block mr-2" style={{ color: '#7C35DC' }} />
            Voice Training
          </h1>
          <p className="text-sm mt-1" style={{ color: 'var(--theme-text-muted)' }}>
            Paste 3–10 of your best past messages. ARIA will adopt their cadence, openers, and sign-offs the next time you press <b>Draft with ARIA</b>.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span
            data-testid="voice-training-seed-count"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-bold border"
            style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border-strong)', color: 'var(--theme-text-muted)' }}
          >
            <Sparkle size={11} weight="duotone" /> {activeCount} active · {seeds.length}/{maxSeeds} saved
          </span>
          <button
            onClick={() => loadPreview(previewChannel)}
            data-testid="voice-training-preview-btn"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-bold border"
            style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-purple)', color: 'var(--theme-purple-light)' }}
          >
            {showPreview ? <EyeSlash size={11} weight="duotone" /> : <Eye size={11} weight="duotone" />}
            {showPreview ? 'Hide preview' : 'Preview ARIA prompt'}
          </button>
        </div>
      </div>

      {/* Preview panel */}
      {showPreview && (
        <div
          className="rounded-xl border p-4"
          style={{ background: 'var(--theme-surface2)', borderColor: 'var(--theme-border-strong)' }}
          data-testid="voice-training-preview-panel"
        >
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <span className="text-[10px] font-extrabold uppercase tracking-[0.18em]" style={{ color: 'var(--theme-text-muted)' }}>
              Tone block injected into ARIA's prompt
            </span>
            <div className="ml-auto inline-flex rounded-md border overflow-hidden" style={{ borderColor: 'var(--theme-border-strong)' }}>
              {CHANNEL_OPTIONS.map((c) => (
                <button
                  key={c.id}
                  onClick={() => loadPreview(c.id)}
                  data-testid={`voice-training-preview-channel-${c.id}`}
                  className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold"
                  style={{
                    background: previewChannel === c.id ? '#7C35DC' : 'transparent',
                    color:     previewChannel === c.id ? '#fff'    : 'var(--theme-text-muted)',
                  }}
                >
                  {c.label}
                </button>
              ))}
            </div>
          </div>
          <pre
            className="whitespace-pre-wrap text-xs leading-relaxed"
            style={{ color: 'var(--theme-text)', fontFamily: 'ui-monospace, SF Mono, Menlo, monospace' }}
            data-testid="voice-training-preview-text"
          >
            {previewBlock}
          </pre>
        </div>
      )}

      {/* Add new */}
      <section
        className="rounded-2xl border p-4 space-y-3"
        style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)' }}
        data-testid="voice-training-add-form"
      >
        <h2 className="text-[10px] font-extrabold uppercase tracking-[0.18em]" style={{ color: 'var(--theme-text-muted)' }}>
          Add a voice sample
        </h2>
        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded-md border overflow-hidden" style={{ borderColor: 'var(--theme-border-strong)' }} data-testid="voice-training-channel-group">
            {CHANNEL_OPTIONS.map((c) => {
              const Icon = c.Icon;
              const active = newChannel === c.id;
              return (
                <button
                  key={c.id}
                  onClick={() => setNewChannel(c.id)}
                  data-testid={`voice-training-channel-${c.id}`}
                  className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-semibold"
                  style={{
                    background: active ? '#7C35DC' : 'var(--theme-surface)',
                    color:     active ? '#fff'    : 'var(--theme-text-muted)',
                  }}
                >
                  <Icon size={11} weight="duotone" /> {c.label}
                </button>
              );
            })}
          </div>
          <input
            type="text"
            value={newLabel}
            onChange={(e) => setNewLabel(e.target.value)}
            placeholder="Optional label (e.g. 'My usual WA opener')"
            data-testid="voice-training-label-input"
            maxLength={80}
            className="flex-1 min-w-[200px] px-3 py-1.5 text-xs rounded-md border outline-none"
            style={{ background: 'var(--theme-surface2)', borderColor: 'var(--theme-border)', color: 'var(--theme-text)' }}
          />
        </div>
        <textarea
          value={newText}
          onChange={(e) => setNewText(e.target.value)}
          rows={4}
          maxLength={1200}
          placeholder="Paste one of your best past messages here — exactly as you sent it. ARIA will mimic the cadence, not the content."
          data-testid="voice-training-text-input"
          className="w-full px-3 py-2 text-sm rounded-md border outline-none resize-y"
          style={{ background: 'var(--theme-surface2)', borderColor: 'var(--theme-border)', color: 'var(--theme-text)' }}
        />
        <div className="flex items-center justify-between gap-2">
          <span className="text-[10px]" style={{ color: 'var(--theme-text-muted)' }}>
            {newText.length}/1200 characters
          </span>
          <button
            onClick={addSeed}
            disabled={adding || atCap || newText.trim().length < 10}
            data-testid="voice-training-add-btn"
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-xs font-bold text-white disabled:opacity-50"
            style={{ background: 'linear-gradient(135deg, #4C1D95 0%, #7C35DC 100%)' }}
          >
            <Plus size={12} weight="bold" /> {adding ? 'Saving…' : atCap ? `Max ${maxSeeds} reached` : 'Save voice sample'}
          </button>
        </div>
      </section>

      {/* Saved seeds */}
      <section data-testid="voice-training-seeds">
        <h2 className="text-[10px] font-extrabold uppercase tracking-[0.18em] mb-2" style={{ color: 'var(--theme-text-muted)' }}>
          Saved samples
        </h2>
        {loading ? (
          <div className="text-xs" style={{ color: 'var(--theme-text-muted)' }} data-testid="voice-training-loading">Loading…</div>
        ) : seeds.length === 0 ? (
          <div
            className="rounded-xl border border-dashed p-6 text-center text-sm"
            style={{ borderColor: 'var(--theme-border-strong)', color: 'var(--theme-text-muted)' }}
            data-testid="voice-training-empty"
          >
            No samples yet. Paste your first one above — even one short message helps ARIA adopt your voice.
          </div>
        ) : (
          <ul className="space-y-2">
            {seeds.map((s) => {
              const ch = CHANNEL_OPTIONS.find((c) => c.id === s.channel) || CHANNEL_OPTIONS[0];
              const ChannelIcon = ch.Icon;
              return (
                <li
                  key={s.id}
                  className="rounded-xl border p-3 flex flex-wrap gap-3"
                  style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)', opacity: s.active ? 1 : 0.55 }}
                  data-testid={`voice-training-seed-${s.id}`}
                >
                  <div className="flex flex-col gap-1 min-w-[120px]">
                    <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider" style={{ color: '#7C35DC' }}>
                      <ChannelIcon size={11} weight="duotone" /> {ch.label}
                    </span>
                    {s.label && <span className="text-xs font-semibold" style={{ color: 'var(--theme-text)' }}>{s.label}</span>}
                  </div>
                  <div className="flex-1 min-w-[280px] text-sm whitespace-pre-wrap" style={{ color: 'var(--theme-text)' }}>
                    {s.text}
                  </div>
                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={() => toggleActive(s)}
                      data-testid={`voice-training-toggle-${s.id}`}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider border"
                      style={{
                        borderColor: s.active ? '#16A34A' : '#94A3B8',
                        color:        s.active ? '#16A34A' : '#94A3B8',
                        background:   s.active ? 'rgba(22,163,74,0.08)' : 'transparent',
                      }}
                    >
                      {s.active ? 'Active' : 'Inactive'}
                    </button>
                    <button
                      onClick={() => deleteSeed(s)}
                      data-testid={`voice-training-delete-${s.id}`}
                      className="inline-flex items-center justify-center p-1.5 rounded-md border"
                      style={{ borderColor: 'var(--theme-border-strong)', color: '#DC2626' }}
                      aria-label="Delete"
                    >
                      <TrashSimple size={12} weight="bold" />
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
};

export default VoiceTraining;
