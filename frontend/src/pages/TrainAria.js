import React, { useEffect, useState } from 'react';
import { Robot, CheckCircle, GraduationCap, Buildings, Target, ChatCircle, ShieldCheck, CalendarBlank } from '@phosphor-icons/react';
import api from '../config/api';
import PageHeader from '../components/PageHeader';
import TrainingCompletionCard from '../components/TrainingCompletionCard';
import AriaSpotlight from '../components/AriaSpotlight';

const TONE_OPTIONS = [
  { id: 'founder_like', label: 'Founder-like' },
  { id: 'warm_consultative', label: 'Warm and consultative' },
  { id: 'sharp_direct', label: 'Sharp and direct' },
  { id: 'premium_polished', label: 'Premium and polished' },
  { id: 'friendly_startup', label: 'Friendly startup tone' },
  { id: 'enterprise_pro', label: 'Enterprise professional' },
  { id: 'witty_respectful', label: 'Witty but respectful' },
  { id: 'custom', label: 'Custom tone' },
];

const Field = ({ label, value, onChange, placeholder, multiline = false, testid }) => (
  <div>
    <label className="block text-xs font-bold uppercase tracking-[0.15em] text-[#9B8AB0] mb-2" style={{ fontFamily: 'Plus Jakarta Sans' }}>{label}</label>
    {multiline ? (
      <textarea value={value || ''} onChange={onChange} placeholder={placeholder} rows={3}
        className="w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-3 py-2.5 rounded-xl text-sm focus:border-[#7C35DC] focus:ring-2 focus:ring-[#7C35DC]/15 outline-none transition resize-y"
        data-testid={testid} />
    ) : (
      <input type="text" value={value || ''} onChange={onChange} placeholder={placeholder}
        className="w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-3 py-2.5 rounded-xl text-sm focus:border-[#7C35DC] focus:ring-2 focus:ring-[#7C35DC]/15 outline-none transition"
        data-testid={testid} />
    )}
  </div>
);

const SectionCard = ({ icon: Icon, title, subtitle, children, testid }) => (
  <div className="bg-white border border-[#E8E0F5] rounded-2xl overflow-hidden" style={{ boxShadow: 'var(--shadow-card)' }} data-testid={testid}>
    <div className="px-6 py-5 border-b border-[#F0ECF9] flex items-start gap-3">
      <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: 'var(--gradient-brand)' }}>
        <Icon size={18} weight="fill" className="text-white" />
      </div>
      <div>
        <h3 className="text-lg font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{title}</h3>
        <p className="text-xs text-[#5A4A7A] mt-0.5">{subtitle}</p>
      </div>
    </div>
    <div className="p-6 space-y-4">{children}</div>
  </div>
);

const TrainAria = () => {
  const [data, setData] = useState(null);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState(null);

  useEffect(() => {
    api.get('/api/aria-agent/training').then(r => setData(r.data)).catch(() => setData({}));
  }, []);

  const update = (key) => (e) => setData(prev => ({ ...prev, [key]: e.target.value }));

  const save = async () => {
    setSaving(true);
    try {
      const res = await api.put('/api/aria-agent/training', data);
      setSavedAt(res.data.trained_at);
    } catch (err) {
      alert(err?.response?.data?.detail || 'Failed to save training');
    } finally { setSaving(false); }
  };

  if (!data) return <div className="text-sm text-[#9B8AB0] p-6">Loading ARIA training…</div>;

  return (
    <div className="space-y-6 max-w-[1100px]" data-testid="train-aria-page">
      <PageHeader
        eyebrow="ARIA · AI Sales Hire"
        title="Train Your AI Sales Agent"
        subtitle="Train ARIA the way you'd onboard a new sales hire. The more context you give, the more personalised every reply, follow-up, and brief becomes."
      />

      <TrainingCompletionCard data={data} />
      <AriaSpotlight
        id="train-aria-completion-v1"
        anchorSelector='[data-testid="training-completion-card"]'
        placement="bottom"
        title="Aim for 80%+"
        body="The more context you give, the sharper every Aria reply. Fill the highlighted sections first — most founders finish this in 15 minutes."
      />

      {savedAt && (
        <div className="rounded-2xl px-5 py-4 flex items-center gap-3 border" style={{ background: 'linear-gradient(135deg, rgba(22,163,74,0.08) 0%, rgba(124,53,220,0.06) 100%)', borderColor: 'rgba(22,163,74,0.25)' }} data-testid="train-aria-success">
          <CheckCircle size={18} weight="fill" className="text-[#16A34A]" />
          <div>
            <div className="text-sm font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>ARIA is trained and ready to handle leads more personally.</div>
            <div className="text-xs text-[#5A4A7A]">Last trained {new Date(savedAt).toLocaleString()}</div>
          </div>
        </div>
      )}

      <SectionCard icon={Buildings} title="Business Context" subtitle="Help ARIA speak about your business the way you would." testid="train-section-business">
        <Field label="What do you sell?" value={data.what_you_sell} onChange={update('what_you_sell')} multiline placeholder="e.g. AI sales agent for startups that automates lead response, qualification, follow-ups, and call booking." testid="train-input-what-you-sell" />
        <Field label="Who do you sell to?" value={data.who_you_sell_to} onChange={update('who_you_sell_to')} multiline placeholder="Founders of B2B SaaS, agencies, consultants, services businesses doing $50K–$2M ARR." testid="train-input-who-you-sell-to" />
        <Field label="What problem do you solve?" value={data.problem_you_solve} onChange={update('problem_you_solve')} multiline placeholder="Founders are still doing follow-ups manually. Leads slip through the cracks." testid="train-input-problem" />
        <Field label="What makes your offer different?" value={data.differentiator} onChange={update('differentiator')} multiline placeholder="ARIA isn't a chatbot or another CRM. It's a full AI sales hire." testid="train-input-differentiator" />
        <Field label="Main services or products" value={data.main_offerings} onChange={update('main_offerings')} multiline placeholder="ARIA Starter, Growth, Pro, Custom" testid="train-input-offerings" />
      </SectionCard>

      <SectionCard icon={Target} title="Ideal Customer Profile" subtitle="ARIA uses this to score every new lead and decide what action to take." testid="train-section-icp">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="Target industries" value={data.target_industries} onChange={update('target_industries')} placeholder="B2B SaaS, agencies, consultants" testid="train-input-industries" />
          <Field label="Target roles" value={data.target_roles} onChange={update('target_roles')} placeholder="Founder, CEO, Head of Growth" testid="train-input-roles" />
          <Field label="Company size" value={data.company_size} onChange={update('company_size')} placeholder="2–50 employees" testid="train-input-company-size" />
          <Field label="Geography" value={data.geography} onChange={update('geography')} placeholder="India, USA, UK, EU, MENA" testid="train-input-geography" />
          <Field label="Budget range" value={data.budget_range} onChange={update('budget_range')} placeholder="$500–$5,000 / month" testid="train-input-budget" />
          <Field label="High-intent signals" value={data.intent_signals} onChange={update('intent_signals')} placeholder="Asks for pricing, mentions deadline, asks 'how does it work'" testid="train-input-intent" />
        </div>
        <Field label="Disqualification signals" value={data.disqualification_signals} onChange={update('disqualification_signals')} multiline placeholder="Free-tier seekers, students, agencies reselling under their brand" testid="train-input-disqual" />
      </SectionCard>

      <SectionCard icon={GraduationCap} title="Qualification Logic" subtitle="What does ARIA ask, and what makes someone worth a founder's time?" testid="train-section-qualification">
        <Field label="What questions should ARIA ask?" value={data.qualifying_questions} onChange={update('qualifying_questions')} multiline placeholder="1. What does your current sales motion look like?  2. How many leads come in per week?  3. Who follows up today?" testid="train-input-questions" />
        <Field label="What makes a lead qualified?" value={data.qualified_definition} onChange={update('qualified_definition')} multiline placeholder="ICP fit + budget signal + decision-making authority" testid="train-input-qualified" />
        <Field label="What makes a lead low-priority?" value={data.low_priority_definition} onChange={update('low_priority_definition')} multiline placeholder="Pre-revenue, just exploring, no founder authority" testid="train-input-low-priority" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="When should ARIA book a call?" value={data.when_to_book_call} onChange={update('when_to_book_call')} multiline placeholder="High-intent reply + ICP fit + budget signal" testid="train-input-when-book" />
          <Field label="When should ARIA alert a human?" value={data.when_to_alert_human} onChange={update('when_to_alert_human')} multiline placeholder="Pricing mentioned, custom solution requested, lead asks for founder" testid="train-input-when-alert" />
        </div>
      </SectionCard>

      <SectionCard icon={ChatCircle} title="Brand Voice" subtitle="Choose how ARIA should sound. You can override anytime." testid="train-section-voice">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {TONE_OPTIONS.map(t => (
            <button key={t.id} type="button" onClick={() => setData(prev => ({ ...prev, tone: t.id }))}
              className={`px-3 py-2.5 rounded-xl text-xs font-bold uppercase tracking-[0.1em] transition-colors border text-left ${data.tone === t.id ? 'bg-[#7C35DC] text-white border-[#7C35DC]' : 'bg-white text-[#5A4A7A] border-[#E8E0F5] hover:border-[#7C35DC]/40 hover:text-[#7C35DC]'}`}
              style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid={`train-tone-${t.id}`}>
              {t.label}
            </button>
          ))}
        </div>
        <Field label="Write like the founder would write" value={data.custom_voice} onChange={update('custom_voice')} multiline placeholder="Paste 3–5 messages or emails the founder has written. ARIA will match that voice." testid="train-input-custom-voice" />
      </SectionCard>

      <SectionCard icon={ShieldCheck} title="Objection Handling" subtitle="Pre-load ARIA so it never freezes on tough questions." testid="train-section-objections">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="Common pricing objections" value={data.pricing_objections} onChange={update('pricing_objections')} multiline placeholder="'It's too expensive' → reframe to opportunity cost" testid="train-input-pricing-obj" />
          <Field label="Common timing objections" value={data.timing_objections} onChange={update('timing_objections')} multiline placeholder="'Not right now' → frame next 30 days revenue at risk" testid="train-input-timing-obj" />
          <Field label="Trust concerns" value={data.trust_concerns} onChange={update('trust_concerns')} multiline placeholder="'Will it sound like a bot?' → show actual conversation samples" testid="train-input-trust" />
          <Field label="Competitor comparisons" value={data.competitor_responses} onChange={update('competitor_responses')} multiline placeholder="vs CRM → 'CRM stores. ARIA works.'" testid="train-input-competitor" />
        </div>
        <Field label="Custom FAQ answers" value={data.custom_faq} onChange={update('custom_faq')} multiline placeholder="Q: How long does setup take?  A: 30 minutes of training, then ARIA goes live." testid="train-input-faq" />
      </SectionCard>

      <SectionCard icon={CalendarBlank} title="Booking Rules" subtitle="When and how should ARIA book calls on your calendar?" testid="train-section-booking">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="Calendar link" value={data.calendar_link} onChange={update('calendar_link')} placeholder="https://calendly.com/yourname/30min" testid="train-input-calendar" />
          <Field label="Booking criteria" value={data.booking_criteria} onChange={update('booking_criteria')} multiline placeholder="ICP fit + budget signal + decision authority" testid="train-input-booking-criteria" />
        </div>
        <Field label="Pre-call questions" value={data.pre_call_questions} onChange={update('pre_call_questions')} multiline placeholder="What's your biggest sales bottleneck right now?" testid="train-input-pre-call" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="Reminder timing" value={data.reminder_timing} onChange={update('reminder_timing')} placeholder="24h, 2h, 15m" testid="train-input-reminder-timing" />
          <Field label="No-show recovery message" value={data.no_show_message} onChange={update('no_show_message')} multiline placeholder="Hey {first_name}, looks like the call slipped. Want to rebook for tomorrow?" testid="train-input-noshow" />
        </div>
      </SectionCard>

      <div className="sticky bottom-0 z-10 bg-gradient-to-t from-white via-white to-transparent pt-6 pb-2">
        <div className="bg-white border border-[#E8E0F5] rounded-2xl p-4 flex flex-wrap items-center justify-between gap-3" style={{ boxShadow: 'var(--shadow-card)' }}>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: 'var(--gradient-brand)' }}>
              <Robot size={18} weight="fill" className="text-white" />
            </div>
            <div>
              <div className="text-sm font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Ready to train ARIA?</div>
              <p className="text-xs text-[#5A4A7A]">ARIA will use this context on every reply, follow-up, and founder brief from now on.</p>
            </div>
          </div>
          <button onClick={save} disabled={saving} className="btn-gradient px-6 py-2.5 rounded-xl text-sm font-extrabold uppercase tracking-[0.1em] disabled:opacity-50" style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid="train-aria-save-btn">
            {saving ? 'Training…' : 'Save ARIA Training'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default TrainAria;
