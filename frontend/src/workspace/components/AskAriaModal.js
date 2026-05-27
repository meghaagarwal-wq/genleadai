import { useEffect, useState } from 'react';
import { X, Sparkle, Copy, CheckCircle, ArrowClockwise, PaperPlaneTilt, WhatsappLogo, EnvelopeSimple, LinkedinLogo, Phone } from '@phosphor-icons/react';
import { toast } from 'sonner';
import { ptApi } from '../shared';

const CHANNELS = [
  { id: 'linkedin', label: 'LinkedIn', icon: LinkedinLogo },
  { id: 'email', label: 'Email', icon: EnvelopeSimple },
  { id: 'whatsapp', label: 'WhatsApp', icon: WhatsappLogo },
  { id: 'call_script', label: 'Call', icon: Phone },
];

const TONES = [
  { id: 'founder_led', label: 'Founder-led' },
  { id: 'consultative', label: 'Consultative' },
  { id: 'direct', label: 'Direct' },
  { id: 'soft_nurture', label: 'Soft Nurture' },
  { id: 'sharp_closer', label: 'Sharp Closer' },
];

const AskAriaModal = ({ leadId, leadName, onClose, paused = false }) => {
  const [channel, setChannel] = useState('linkedin');
  const [tone, setTone] = useState('founder_led');
  const [userNote, setUserNote] = useState('');
  const [reply, setReply] = useState('');
  const [loading, setLoading] = useState(false);
  const [aiPowered, setAiPowered] = useState(false);
  const [copied, setCopied] = useState(false);
  const [edited, setEdited] = useState(false);

  const generate = async () => {
    setLoading(true);
    setEdited(false);
    try {
      const res = await ptApi.post(`/api/pt/leads/${leadId}/ask-aria`, { channel, tone, user_note: userNote });
      setReply(res.data?.message || '');
      setAiPowered(!!res.data?.ai_powered);
      if (!res.data?.ai_powered && res.data?.ai_error) {
        toast.error(`Heuristic fallback: ${res.data.ai_error.slice(0, 80)}`);
      }
    } catch (err) {
      setReply('Aria could not draft this reply right now. Please try again.');
      setAiPowered(false);
      toast.error(err.response?.data?.detail || 'Failed to generate');
    } finally {
      setLoading(false);
    }
  };

  // Auto-generate on first open
  useEffect(() => { generate(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);

  const copyReply = () => {
    if (!reply) return;
    navigator.clipboard.writeText(reply);
    setCopied(true);
    toast.success('Copied');
    setTimeout(() => setCopied(false), 1800);
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4" data-testid="pt-ask-aria-modal">
      <div className="absolute inset-0 bg-[#0F172A]/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-[580px] max-h-[92vh] overflow-y-auto rounded-2xl bg-white border border-[#E2E8F0]" style={{ boxShadow: '0 24px 64px -12px rgba(15,23,42,0.35)' }}>
        {/* Header */}
        <div className="relative px-6 py-5 border-b border-[#E2E8F0]" style={{ background: 'linear-gradient(135deg, #1A0A2E 0%, #4C1D95 55%, #7C35DC 100%)' }}>
          <button onClick={onClose} data-testid="pt-ask-aria-close"
            className="absolute top-4 right-4 p-1.5 rounded-md bg-white/10 hover:bg-white/20 text-white border border-white/20 transition-colors">
            <X size={14} />
          </button>
          <div className="flex items-center gap-2 mb-1">
            <Sparkle size={11} weight="fill" className="text-[#C9B6FF]" />
            <span className="text-[10px] font-bold uppercase tracking-[0.22em] text-[#C9B6FF]">ARIA · ASK FOR REPLY</span>
            {aiPowered && <span className="px-1.5 py-0.5 rounded text-[9px] font-extrabold uppercase tracking-[0.16em] bg-[#DCFCE7] text-[#15803D] border border-[#15803D]/30">AI-POWERED</span>}
            {paused && <span className="px-1.5 py-0.5 rounded text-[9px] font-extrabold uppercase tracking-[0.16em] bg-[#FEF2F2] text-[#B91C1C] border border-[#B91C1C]/30">ACCOUNT PAUSED</span>}
          </div>
          <div className="text-xl font-bold text-white leading-tight" style={{ fontFamily: 'Space Grotesk, Inter' }}>Reply to {leadName}</div>
          <div className="text-xs text-[#C9B6FF] mt-1">Aria drafts using the full timeline + account context. You approve.</div>
        </div>

        {/* Controls */}
        <div className="px-6 pt-4 space-y-4">
          {/* Channel */}
          <div>
            <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#64748B] mb-2">CHANNEL</div>
            <div className="grid grid-cols-4 gap-1.5">
              {CHANNELS.map((c) => {
                const Icon = c.icon;
                const active = channel === c.id;
                return (
                  <button
                    key={c.id}
                    onClick={() => setChannel(c.id)}
                    data-testid={`pt-ask-aria-channel-${c.id}`}
                    className={`flex flex-col items-center gap-1 py-2.5 rounded-md text-[10px] font-bold uppercase tracking-[0.12em] border transition-all ${
                      active ? 'bg-[#7C35DC] text-white border-[#7C35DC]' : 'bg-white text-[#475569] border-[#E2E8F0] hover:border-[#7C35DC]/40'
                    }`}
                  >
                    <Icon size={14} weight="fill" />
                    {c.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Tone */}
          <div>
            <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#64748B] mb-2">TONE</div>
            <div className="flex flex-wrap gap-1.5">
              {TONES.map((t) => {
                const active = tone === t.id;
                return (
                  <button
                    key={t.id}
                    onClick={() => setTone(t.id)}
                    data-testid={`pt-ask-aria-tone-${t.id}`}
                    className={`px-3 py-1.5 rounded-md text-[10px] font-bold uppercase tracking-[0.12em] border transition-all ${
                      active ? 'bg-[#7C35DC] text-white border-[#7C35DC]' : 'bg-white text-[#475569] border-[#E2E8F0] hover:border-[#7C35DC]/40'
                    }`}
                  >
                    {t.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Reply */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#7C35DC]">ARIA'S DRAFT</div>
              <button
                onClick={generate}
                disabled={loading}
                data-testid="pt-ask-aria-regenerate"
                className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-[0.14em] text-[#7C35DC] hover:underline disabled:opacity-50"
              >
                <ArrowClockwise size={11} weight="bold" className={loading ? 'animate-spin' : ''} />
                {loading ? 'Writing…' : 'Regenerate'}
              </button>
            </div>
            <textarea
              value={reply}
              onChange={(e) => { setReply(e.target.value); setEdited(true); }}
              rows={8}
              data-testid="pt-ask-aria-textarea"
              className="w-full bg-white border border-[#E2E8F0] rounded-md px-3 py-2.5 text-sm text-[#0F172A] leading-relaxed focus:border-[#7C35DC] focus:ring-2 focus:ring-[#7C35DC]/15 outline-none transition resize-y"
              placeholder={loading ? 'Aria is drafting using the timeline…' : "Aria will draft a reply here."}
            />
            {edited && <div className="text-[10px] text-[#94A3B8] mt-1">Edited from Aria's draft</div>}
          </div>

          {/* User note */}
          <details className="group">
            <summary className="cursor-pointer text-[10px] font-bold uppercase tracking-[0.18em] text-[#64748B] hover:text-[#7C35DC] select-none">
              ADD CONTEXT FOR ARIA
            </summary>
            <textarea
              value={userNote}
              onChange={(e) => setUserNote(e.target.value)}
              rows={2}
              data-testid="pt-ask-aria-user-note"
              className="w-full mt-2 bg-white border border-[#E2E8F0] rounded-md px-3 py-2 text-sm text-[#0F172A] focus:border-[#7C35DC] focus:ring-2 focus:ring-[#7C35DC]/15 outline-none transition resize-y"
              placeholder="e.g. Mention the 3-month wellbeing pilot, or steer Aria toward a specific question."
            />
          </details>
        </div>

        {/* Actions */}
        <div className="sticky bottom-0 px-6 py-4 mt-4 bg-white border-t border-[#E2E8F0] flex flex-wrap gap-2">
          <button
            onClick={copyReply}
            disabled={!reply || loading}
            data-testid="pt-ask-aria-copy"
            className="flex-1 min-w-[120px] flex items-center justify-center gap-2 py-2.5 rounded-md bg-white border border-[#E2E8F0] text-[#475569] hover:bg-[#FAF7FF] hover:text-[#7C35DC] hover:border-[#7C35DC]/30 text-[10px] font-extrabold uppercase tracking-[0.16em] disabled:opacity-50"
          >
            {copied ? <CheckCircle size={12} weight="fill" /> : <Copy size={12} weight="fill" />}
            {copied ? 'Copied' : 'Copy draft'}
          </button>
          <button
            disabled={!reply || loading}
            onClick={copyReply}
            data-testid="pt-ask-aria-send"
            className="flex-1 min-w-[160px] flex items-center justify-center gap-2 py-2.5 rounded-md text-white text-[10px] font-extrabold uppercase tracking-[0.16em] disabled:opacity-50"
            style={{ background: '#7C35DC' }}
          >
            <PaperPlaneTilt size={12} weight="fill" />
            Copy & open {channel === 'whatsapp' ? 'WhatsApp' : channel === 'email' ? 'Email' : channel === 'linkedin' ? 'LinkedIn' : 'Call notes'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default AskAriaModal;
